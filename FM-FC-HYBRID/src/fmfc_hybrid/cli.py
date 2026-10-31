"""Command-line entry point: ``python -m fmfc_hybrid <command>``.

Commands work against a local SQLite database. Only mock adapters exist today,
so ``demo`` is the end-to-end exercise; ``status``/``audit``/``ledger`` inspect
any database produced by the bridge.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .adapters.mock_fifa import MockFifa
from .adapters.mock_fm import MockFootballManager, SimulatedCrash
from .bridge.config import BridgeConfig
from .bridge.orchestrator import MatchOrchestrator
from .contracts.jsonschema import write_all
from .ledger.ledger import EventLedger
from .lifecycle.state_machine import MatchLifecycle
from .storage.db import Database


def _cmd_demo(args: argparse.Namespace) -> int:
    db = Database(args.db)
    fm, fifa = MockFootballManager(seed=args.seed), MockFifa(seed=args.seed)
    for fault in args.fm_fault or []:
        fm.faults.add(fault)
    for fault in args.fifa_fault or []:
        fifa.faults.add(fault)
    orch = MatchOrchestrator(db, fm, fifa, config=BridgeConfig.load(args.config) if args.config else None)
    for _ in range(args.matches):
        rec = orch.begin()
        if rec is None:
            print("no upcoming fixture")
            break
        try:
            outs = [orch.run(rec.match_id)]
        except SimulatedCrash as crash:
            # Imitate a bridge restart: fresh orchestrator, same database, same (mock) game state.
            print(f"simulated bridge crash: {crash}; restarting and recovering")
            orch = MatchOrchestrator(db, fm, fifa, config=orch.config)
            outs = orch.recover_all()
        for out in outs:
            print(json.dumps({"match_id": out.match_id, "state": out.state.value, "score": out.score,
                              "integration": out.integration_level.name if out.integration_level else None,
                              "message": out.message}))
    print("FM applied each fixture exactly once:",
          all(f.import_count <= 1 for f in fm.fixtures))
    print("league table:", json.dumps(fm.table))
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    db = Database(args.db)
    for row in db.query_all("SELECT match_id, fixture_id, state, attempt, updated_at FROM matches ORDER BY created_at"):
        print(f"{row['match_id']}  {row['fixture_id']}  {row['state']:<22} attempt={row['attempt']}  {row['updated_at']}")
    return 0


def _cmd_history(args: argparse.Namespace) -> int:
    lc = MatchLifecycle(Database(args.db))
    for t in lc.history(args.match_id):
        print(f"{t.ts}  {t.from_state.value if t.from_state else '-':<22} -> {t.to_state.value:<22} {t.reason}")
    return 0


def _cmd_ledger(args: argparse.Namespace) -> int:
    print(json.dumps(EventLedger(Database(args.db)).export(args.ledger_match_id), indent=2))
    return 0


def _cmd_schemas(args: argparse.Namespace) -> int:
    for path in write_all(Path(args.out)):
        print(path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fmfc-hybrid", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("demo", help="run mock fixtures end-to-end")
    d.add_argument("--db", default=":memory:")
    d.add_argument("--matches", type=int, default=1)
    d.add_argument("--seed", type=int, default=7)
    d.add_argument("--config")
    d.add_argument("--fm-fault", action="append", help="e.g. import_fail_once, capture_fail_once")
    d.add_argument("--fifa-fault", action="append", help="e.g. interrupt_once, capture_fail_once")
    d.set_defaults(fn=_cmd_demo)
    s = sub.add_parser("status", help="list matches")
    s.add_argument("--db", required=True)
    s.set_defaults(fn=_cmd_status)
    h = sub.add_parser("history", help="show a match's lifecycle transitions")
    h.add_argument("--db", required=True)
    h.add_argument("match_id")
    h.set_defaults(fn=_cmd_history)
    lg = sub.add_parser("ledger", help="export a ledger stream (match_id:attempt)")
    lg.add_argument("--db", required=True)
    lg.add_argument("ledger_match_id")
    lg.set_defaults(fn=_cmd_ledger)
    sc = sub.add_parser("schemas", help="write JSON Schemas for all contracts")
    sc.add_argument("--out", default="data/schemas")
    sc.set_defaults(fn=_cmd_schemas)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())
