"""Bridge orchestrator: drives one fixture through the match lifecycle.

Every step is a pure function of the persisted state, so the orchestrator is
crash-safe by construction: after a crash, :meth:`recover_all` simply resumes
each unfinished match from its stored state. Two rules make that safe:

1. The intent to import (``ImportGuard.begin`` + FM_IMPORT_PENDING) is committed
   *before* FM is touched.
2. Before applying anything to FM, the orchestrator asks FM whether the result
   is already there (``lookup_import``), so a lost acknowledgement never causes a
   second application.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any, Callable, Optional

from ..adapters.base import (
    FifaAdapter,
    FifaMatchRequest,
    FifaTeamSetup,
    FmAdapter,
    IntegrationLevel,
)
from ..adapters.ids import bind_fixture, stable_fixture_id
from ..contracts.models import ExternalMatchRecord, FifaLinkStatus, FmImportPackage, Side, TacticalPlan
from ..contracts.serialization import content_hash, from_primitive, to_primitive
from ..contracts.validation import validate_fixture, validate_match_record
from ..errors import (
    AdapterError,
    DataCaptureError,
    DuplicateImportError,
    HybridError,
    IdentityError,
    LedgerError,
    MappingError,
    MatchInterruptedError,
    ValidationError,
)
from ..identity.registry import FifaIdPolicy, PlayerRegistry
from ..ledger.ledger import EventLedger
from ..lifecycle.state_machine import MatchLifecycle, MatchRecord, MatchState
from ..player_mapper.attributes import AttributeMapper
from ..result_processor.processor import ImportGuard, RatingScale, ResultProcessor
from ..storage.db import Database, utc_now
from ..tactics.translator import TacticalTranslator
from .config import BridgeConfig

S = MatchState

#: Automatic recovery edges taken when the recorded error is retryable.
AUTO_RECOVERY: dict[MatchState, MatchState] = {
    S.CAPTURE_FAILED: S.FIXTURE_DETECTED,
    S.PREPARATION_FAILED: S.FM_STATE_CAPTURED,
    S.LAUNCH_FAILED: S.MATCH_PREPARED,
    S.DATA_CAPTURE_FAILED: S.MATCH_IN_PROGRESS,
    S.IMPORT_FAILED: S.FM_IMPORT_PENDING,
}


@dataclass(frozen=True)
class MatchOutcome:
    match_id: str
    state: MatchState
    integration_level: Optional[IntegrationLevel]
    score: Optional[tuple[int, int]]
    needs_operator: bool
    message: str

    @property
    def full_integration(self) -> bool:
        return self.state is S.FM_IMPORT_VERIFIED and bool(
            self.integration_level and self.integration_level.is_full_integration)


def _error(exc: BaseException) -> dict[str, Any]:
    if isinstance(exc, HybridError):
        body = exc.to_dict()
    else:
        body = {"code": type(exc).__name__, "message": str(exc), "details": {}}
    body["retryable"] = bool(getattr(exc, "retryable", False))
    return body


class MatchOrchestrator:
    def __init__(self, db: Database, fm: FmAdapter, fifa: FifaAdapter, *, config: BridgeConfig | None = None,
                 mapper: AttributeMapper | None = None, translator: TacticalTranslator | None = None,
                 actor: str = "bridge") -> None:
        self.db = db
        self.fm = fm
        self.fifa = fifa
        self.config = config or BridgeConfig()
        self.actor = actor
        self.lifecycle = MatchLifecycle(db)
        self.ledger = EventLedger(db)
        self.guard = ImportGuard(db)
        self.processor = ResultProcessor(RatingScale(self.config.rating_source_min, self.config.rating_source_max))
        self.mapper = mapper or AttributeMapper.from_file()
        self.translator = translator or TacticalTranslator.load(
            self.config.fifa_capability_profile, position_map=self.mapper.config["positions"])
        self._registries: dict[str, PlayerRegistry] = {}

    def registry(self, career_id: str) -> PlayerRegistry:
        if career_id not in self._registries:
            self._registries[career_id] = PlayerRegistry(
                self.db, career_id, FifaIdPolicy(self.config.fifa_id_range_start, self.config.fifa_id_range_end))
        return self._registries[career_id]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def begin(self) -> Optional[MatchRecord]:
        """Detect the managed club's next fixture and register it (idempotent)."""
        fixture = self.fm.detect_upcoming_fixture()
        if fixture is None:
            return None
        fixture = replace(fixture, fixture_id=stable_fixture_id(fixture.career_id, fixture.fm_fixture_ref))
        live = self.lifecycle.find_live(fixture.career_id, fixture.fixture_id)
        if live is not None:
            return live
        return self.lifecycle.create(fixture, actor=self.actor)

    def run(self, match_id: str, *, max_steps: int = 64) -> MatchOutcome:
        for _ in range(max_steps):
            rec = self.lifecycle.get(match_id)
            if rec.state.is_terminal:
                break
            if rec.state.is_failure:
                if not self._auto_recover(rec):
                    break
                continue
            self.step(match_id)
        return self.outcome(match_id)

    def step(self, match_id: str) -> MatchRecord:
        rec = self.lifecycle.get(match_id)
        handler: Callable[[MatchRecord], None] | None = {
            S.FIXTURE_DETECTED: self._capture,
            S.FM_STATE_CAPTURED: self._prepare,
            S.MATCH_PREPARED: self._launch,
            S.MATCH_IN_PROGRESS: self._collect,
            S.MATCH_DATA_CAPTURED: self._validate,
            S.MATCH_VALIDATED: self._begin_import,
            S.FM_IMPORT_PENDING: self._import,
            S.FM_IMPORT_COMPLETED: self._verify,
        }.get(rec.state)
        if handler is None:
            raise HybridError(f"no automatic step for state {rec.state.value}")
        handler(rec)
        return self.lifecycle.get(match_id)

    def recover_all(self) -> list[MatchOutcome]:
        """Resume every unfinished match after a restart."""
        outcomes = []
        for rec in self.lifecycle.unfinished():
            self.db.audit(self.actor, "recovery.resume", "match", rec.match_id, {"state": rec.state.value})
            outcomes.append(self.run(rec.match_id))
        return outcomes

    # -- operator decisions ----------------------------------------------
    def replay(self, match_id: str, reason: str) -> MatchRecord:
        """Start a fresh FIFA attempt after an interruption or invalid capture."""
        rec = self.lifecycle.get(match_id)
        return self.lifecycle.transition(match_id, S.FM_STATE_CAPTURED, expected_version=rec.version,
                                         reason=f"operator replay: {reason}", actor=self.actor)

    def retry(self, match_id: str, reason: str) -> MatchRecord:
        rec = self.lifecycle.get(match_id)
        target = AUTO_RECOVERY.get(rec.state)
        if target is None:
            raise HybridError(f"no retry edge from {rec.state.value}")
        return self.lifecycle.transition(match_id, target, expected_version=rec.version,
                                         reason=f"operator retry: {reason}", actor=self.actor)

    def abandon(self, match_id: str, reason: str, *, confirm_fm_untouched: bool = False) -> MatchRecord:
        rec = self.lifecycle.get(match_id)
        if confirm_fm_untouched and self.fm.lookup_import(rec.fm_fixture_ref) is not None:
            raise HybridError("FM already holds a result for this fixture; refusing to abandon")
        return self.lifecycle.transition(match_id, S.ABANDONED, expected_version=rec.version,
                                         reason=f"operator abandon: {reason}", actor=self.actor,
                                         allow_unsafe_abandon=confirm_fm_untouched)

    def outcome(self, match_id: str) -> MatchOutcome:
        rec = self.lifecycle.get(match_id)
        receipt = self.guard.receipt(rec.career_id, rec.fixture_id)
        level = IntegrationLevel(receipt["integration_level"]) if receipt else None
        pkg = self._snapshot(match_id, "fm_import_package")
        score = (pkg["home_goals"], pkg["away_goals"]) if pkg else None
        needs_operator = not rec.state.is_terminal
        if rec.state is S.FM_IMPORT_VERIFIED:
            msg = "verified; " + ("FULL integration" if level and level.is_full_integration
                                  else f"PARTIAL integration ({level.name if level else 'unknown'})")
        elif rec.state.is_failure:
            msg = f"stopped in {rec.state.value}: {(rec.last_error or {}).get('message', '')}"
        else:
            msg = rec.state.value
        msg += f" [FM adapter: {getattr(self.fm, 'name', '?')}, FIFA adapter: {getattr(self.fifa, 'name', '?')}]"
        return MatchOutcome(match_id, rec.state, level, score, needs_operator, msg)

    # ------------------------------------------------------------------
    # Snapshots (append-only preservation copies)
    # ------------------------------------------------------------------
    def _save_snapshot(self, match_id: str, kind: str, content: Any) -> str:
        text = json.dumps(to_primitive(content), sort_keys=True, ensure_ascii=False)
        digest = content_hash(content)
        self.db.execute("INSERT INTO state_snapshots(match_id, kind, sha256, content, ts) VALUES (?,?,?,?,?)",
                        (match_id, kind, digest, text, utc_now()))
        return digest

    def _snapshot(self, match_id: str, kind: str) -> Any:
        row = self.db.query_one(
            "SELECT content FROM state_snapshots WHERE match_id=? AND kind=? ORDER BY id DESC LIMIT 1",
            (match_id, kind))
        return json.loads(row["content"]) if row else None

    def _fail(self, rec: MatchRecord, state: MatchState, exc: BaseException, reason: str) -> None:
        self.lifecycle.transition(rec.match_id, state, expected_version=rec.version, reason=reason,
                                  error=_error(exc), actor=self.actor)

    def _auto_recover(self, rec: MatchRecord) -> bool:
        target = AUTO_RECOVERY.get(rec.state)
        err = rec.last_error or {}
        if target is None or not err.get("retryable"):
            return False
        retries = sum(1 for t in self.lifecycle.history(rec.match_id) if t.to_state is rec.state)
        if retries > self.config.max_automatic_retries:
            return False
        self.lifecycle.transition(rec.match_id, target, expected_version=rec.version,
                                  reason=f"automatic retry {retries}/{self.config.max_automatic_retries}",
                                  actor=self.actor)
        return True

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------
    def _capture(self, rec: MatchRecord) -> None:
        try:
            ctx = self.fm.capture_match_context(rec.fm_fixture_ref)
            # Preserve FM's state before the bridge changes anything.
            self._save_snapshot(rec.match_id, "fm_pre_match_state", {
                "raw_state": ctx.raw_state, "fixture": ctx.fixture,
                "tactics": ctx.tactics, "players": list(ctx.players)})
            caps = self.fm.capabilities()
            if caps.suppress_native_simulation:
                self.fm.suppress_native_simulation(rec.fm_fixture_ref)
            elif self.config.require_simulation_suppression:
                raise AdapterError("FM adapter cannot guarantee FM will not simulate this fixture itself",
                                   retryable=False)
            registry = self.registry(rec.career_id)
            records = registry.register_many(ctx.players, reason=f"capture:{rec.match_id}", actor=self.actor)
            hybrid_by_fm = {r.fm_player_id: r.hybrid_player_id for r in records}
            bound = bind_fixture(replace(ctx.fixture, fixture_id=rec.fixture_id), hybrid_by_fm)
            validate_fixture(bound).raise_if_errors("captured fixture is invalid")
            for side in (Side.HOME.value, Side.AWAY.value):
                if side not in ctx.tactics:
                    raise AdapterError(f"no tactical plan captured for {side}", retryable=False)
            self._save_snapshot(rec.match_id, "fm_tactics", ctx.tactics)
        except (AdapterError, ValidationError, IdentityError) as exc:
            self._fail(rec, S.CAPTURE_FAILED, exc, "FM state capture failed")
            return
        self.lifecycle.transition(rec.match_id, S.FM_STATE_CAPTURED, expected_version=rec.version,
                                  reason="FM state captured", fixture=bound, actor=self.actor,
                                  payload={"players": len(records)})

    def _prepare(self, rec: MatchRecord) -> None:
        fixture = rec.fixture
        registry = self.registry(rec.career_id)
        occupied = getattr(self.fifa, "is_fifa_id_occupied", None) or (lambda _id: False)
        try:
            tactics_raw = self._snapshot(rec.match_id, "fm_tactics")
            tactics = {k: from_primitive(TacticalPlan, v) for k, v in tactics_raw.items()}
            specs, reports = [], []
            for pid in fixture.home.all_player_ids() + fixture.away.all_player_ids():
                prec = registry.get(pid)
                if prec.fifa_player_id is None:
                    prec = registry.allocate_fifa_id(pid, occupied=occupied, actor=self.actor)
                must_create = prec.fifa_link_status is FifaLinkStatus.CREATED and prec.last_fifa_sync_at is None
                spec, report = self.mapper.to_fifa_spec(pid, prec.fifa_player_id, prec.profile,
                                                        must_create=must_create)
                specs.append(spec)
                reports.append(report)
            setups, fidelity = {}, {}
            for side in (Side.HOME, Side.AWAY):
                squad = fixture.squad(side)
                translation = self.translator.translate(tactics[side.value])
                slot_to_pid = {s.slot: s.hybrid_player_id for s in squad.starters}
                setups[side] = FifaTeamSetup(
                    side=side, hybrid_club_id=squad.club.hybrid_club_id,
                    starters=tuple((s.hybrid_player_id, self.mapper.fifa_position(s.position))
                                   for s in sorted(squad.starters, key=lambda s: s.slot)),
                    bench=squad.bench, team_settings=translation.team_settings,
                    player_instructions={slot_to_pid[slot]: pi for slot, pi in translation.player_instructions.items()
                                         if slot in slot_to_pid},
                    captain_id=squad.captain_id)
                fidelity[side.value] = {"summary": translation.summary(),
                                        "overall": translation.overall_fidelity().value,
                                        "elements": [to_primitive(e) for e in translation.elements]}
            request = FifaMatchRequest(rec.ledger_match_id, fixture, tuple(specs), setups[Side.HOME],
                                       setups[Side.AWAY], self.config.control_mode,
                                       self.config.fifa_half_length_minutes)
            self._save_snapshot(rec.match_id, "tactical_translation", fidelity)
            self._save_snapshot(rec.match_id, "conversion_reports", reports)
            self._save_snapshot(rec.match_id, "fifa_match_request", request)
        except (MappingError, IdentityError) as exc:
            self._fail(rec, S.MAPPING_INVALID, exc, "player/tactic mapping failed")
            return
        try:
            receipt = self.fifa.prepare_match(request)
        except AdapterError as exc:
            self._fail(rec, S.PREPARATION_FAILED, exc, "FIFA preparation failed")
            return
        for spec in specs:
            registry.mark_fifa_synced(spec.hybrid_player_id, actor=self.actor)
        self.lifecycle.transition(rec.match_id, S.MATCH_PREPARED, expected_version=rec.version,
                                  reason="FIFA match prepared", actor=self.actor,
                                  payload={"created": len(receipt.created_players),
                                           "updated": len(receipt.updated_players),
                                           "tactical_fidelity": {k: v["overall"] for k, v in fidelity.items()}})

    def _launch(self, rec: MatchRecord) -> None:
        try:
            self.fifa.launch_match(rec.ledger_match_id)
        except AdapterError as exc:
            self._fail(rec, S.LAUNCH_FAILED, exc, "FIFA launch failed")
            return
        self.lifecycle.transition(rec.match_id, S.MATCH_IN_PROGRESS, expected_version=rec.version,
                                  reason="FIFA match launched", actor=self.actor,
                                  payload={"control_mode": self.config.control_mode.value})

    def _collect(self, rec: MatchRecord) -> None:
        lid = rec.ledger_match_id
        try:
            head = self.ledger.events(lid)
            after = head[-1].sequence if head else 0
            self.ledger.append(self.fifa.poll_events(lid, after), actor=self.actor)
            record = self.fifa.collect_result(lid)
            if record.match_id != lid or record.fixture_id != rec.fixture_id:
                raise DataCaptureError("FIFA returned a record for a different match", retryable=False)
            self.ledger.append(record.events, actor=self.actor)
        except MatchInterruptedError as exc:
            self._fail(rec, S.MATCH_INTERRUPTED, exc, "match interrupted")
            return
        except (AdapterError, LedgerError) as exc:
            self._fail(rec, S.DATA_CAPTURE_FAILED, exc, "match data capture failed")
            return
        self._save_snapshot(rec.match_id, "external_match_record", record)
        self.lifecycle.transition(rec.match_id, S.MATCH_DATA_CAPTURED, expected_version=rec.version,
                                  reason="match data captured", actor=self.actor,
                                  payload={"events": len(record.events), "source": record.source})

    def _validate(self, rec: MatchRecord) -> None:
        record = from_primitive(ExternalMatchRecord, self._snapshot(rec.match_id, "external_match_record"))
        issues, _ = validate_match_record(rec.fixture, record)
        ledger_ids = {e.source_event_id for e in self.ledger.events(rec.ledger_match_id)}
        record_ids = {e.source_event_id for e in record.events}
        if ledger_ids != record_ids:
            issues.error("LEDGER_RECORD_MISMATCH",
                         f"streamed events and final record differ ({len(ledger_ids ^ record_ids)} events)")
        if issues.errors:
            self._fail(rec, S.VALIDATION_FAILED, ValidationError("match record invalid", issues.issues),
                       "match validation failed")
            return
        try:
            fin = self.ledger.finalize(record, actor=self.actor)
        except LedgerError as exc:
            self._fail(rec, S.VALIDATION_FAILED, exc, "ledger finalization failed")
            return
        self.lifecycle.transition(rec.match_id, S.MATCH_VALIDATED, expected_version=rec.version,
                                  reason="validated and ledger finalized", actor=self.actor,
                                  payload={"record_sha256": fin.record_sha256, "head_hash": fin.head_hash,
                                           "warnings": [w.to_dict() for w in issues.warnings]})

    def _begin_import(self, rec: MatchRecord) -> None:
        record = self.ledger.finalized_record(rec.ledger_match_id)  # includes audited corrections
        registry = self.registry(rec.career_id)
        package = self.processor.build_package(rec.fixture, record, content_hash(record),
                                               lambda pid: registry.get(pid).fm_player_id)
        with self.db.transaction():
            self.guard.begin(package, rec.match_id)
            self._save_snapshot(rec.match_id, "fm_import_package", package)
            self.lifecycle.transition(rec.match_id, S.FM_IMPORT_PENDING, expected_version=rec.version,
                                      reason="import intent recorded", actor=self.actor,
                                      payload={"idempotency_key": package.idempotency_key})

    def _import(self, rec: MatchRecord) -> None:
        package = from_primitive(FmImportPackage, self._snapshot(rec.match_id, "fm_import_package"))
        try:
            existing = self.fm.lookup_import(rec.fm_fixture_ref)
            if existing is not None:
                if existing.idempotency_key != package.idempotency_key:
                    raise DuplicateImportError("FM holds a different result for this fixture",
                                               details={"fm_key": existing.idempotency_key})
                receipt, how = existing, "recovered: FM already applied this package"
            else:
                receipt, how = self.fm.import_result(package), "applied"
        except DuplicateImportError as exc:
            self.guard.failed(package.idempotency_key, exc)
            self._fail(rec, S.IMPORT_FAILED, exc, "FM import conflict")
            return
        except AdapterError as exc:
            self.guard.failed(package.idempotency_key, exc)
            self._fail(rec, S.IMPORT_FAILED, exc, "FM import failed")
            return
        with self.db.transaction():
            self.guard.complete(receipt)
            self.lifecycle.transition(rec.match_id, S.FM_IMPORT_COMPLETED, expected_version=rec.version,
                                      reason=how, actor=self.actor,
                                      payload={"integration_level": receipt.integration_level.name,
                                               "full_integration": receipt.integration_level.is_full_integration})

    def _verify(self, rec: MatchRecord) -> None:
        package = from_primitive(FmImportPackage, self._snapshot(rec.match_id, "fm_import_package"))
        try:
            report = self.fm.verify_import(package)
        except AdapterError as exc:
            self._fail(rec, S.VERIFICATION_FAILED, exc, "FM verification errored")
            return
        checks = [to_primitive(c) for c in report.checks]
        if not report.passed:
            self._fail(rec, S.VERIFICATION_FAILED,
                       HybridError("FM verification failed", details={"failures": [
                           to_primitive(c) for c in report.failures()]}), "FM verification failed")
            return
        with self.db.transaction():
            self.guard.verified(package.idempotency_key)
            self.lifecycle.transition(rec.match_id, S.FM_IMPORT_VERIFIED, expected_version=rec.version,
                                      reason="FM import verified", actor=self.actor, payload={"checks": checks})
