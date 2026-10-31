# Match Lifecycle

Implemented in `src/fmfc_hybrid/lifecycle/state_machine.py` and driven by
`src/fmfc_hybrid/bridge/orchestrator.py`. Tests: `tests/unit/test_lifecycle.py`,
`tests/integration/test_orchestrator.py`.

## States

```
FIXTURE_DETECTED ──► FM_STATE_CAPTURED ──► MATCH_PREPARED ──► MATCH_IN_PROGRESS ──► MATCH_DATA_CAPTURED
      │                    │    │               │                   │      │                 │
      ▼                    ▼    ▼               ▼                   ▼      ▼                 ▼
 CAPTURE_FAILED   MAPPING_INVALID  PREPARATION_  LAUNCH_FAILED  MATCH_      DATA_CAPTURE_  VALIDATION_FAILED
                                   FAILED                       INTERRUPTED FAILED
                                                                                             │
MATCH_VALIDATED ◄────────────────────────────────────────────────────────────────────────────┘ (on success)
      │
      ▼
FM_IMPORT_PENDING ──► FM_IMPORT_COMPLETED ──► FM_IMPORT_VERIFIED (terminal)
      │                     │
      ▼                     ▼
 IMPORT_FAILED      VERIFICATION_FAILED                       ABANDONED (terminal, from any non-terminal state*)
```

\* Abandoning from `FM_IMPORT_PENDING`, `FM_IMPORT_COMPLETED`, `IMPORT_FAILED` or `VERIFICATION_FAILED`
requires explicit confirmation that FM does not hold the result (`allow_unsafe_abandon`), because FM
may already have applied it.

## Recovery edges

| Failure | Automatic (if error is retryable, bounded by `max_automatic_retries`) | Operator |
|---|---|---|
| CAPTURE_FAILED | → FIXTURE_DETECTED | retry / abandon |
| MAPPING_INVALID | none (data must be fixed) | → FM_STATE_CAPTURED / abandon |
| PREPARATION_FAILED | → FM_STATE_CAPTURED | retry / abandon |
| LAUNCH_FAILED | → MATCH_PREPARED | replay / abandon |
| MATCH_INTERRUPTED | none (the user decides) | `replay` → FM_STATE_CAPTURED, new attempt / abandon |
| DATA_CAPTURE_FAILED | → MATCH_IN_PROGRESS (re-collect) | replay / abandon |
| VALIDATION_FAILED | none | replay / abandon |
| IMPORT_FAILED | → FM_IMPORT_PENDING (FM is queried first) | retry / confirmed abandon |
| VERIFICATION_FAILED | none (needs a human) | re-verify / confirmed abandon |

Re-entering `FM_STATE_CAPTURED` from a failure increments `attempt`. Each attempt writes its own ledger
stream (`<match_id>:<attempt>`), so a replayed match never mixes events with an interrupted one; the
partial stream stays for audit and is never finalized.

## Never processing a fixture twice

Layered guards, each tested:

1. **One live match per fixture**: partial unique index `uq_matches_live_fixture`; `begin()` returns
   the existing live match instead of creating a second.
2. **Imported fixtures cannot restart**: `MatchLifecycle.create` refuses a fixture whose import is
   completed or verified.
3. **Intent before action**: `ImportGuard.begin` and the `FM_IMPORT_PENDING` transition commit in one
   transaction *before* FM is touched.
4. **Ask FM first**: `_import` calls `FmAdapter.lookup_import` before `import_result`. If FM already
   holds this package (crash after FM applied it), the bridge records completion without re-applying.
   If FM holds a *different* result, the import fails as a conflict.
5. **Idempotency key** = SHA-256 of `career|fixture|finalized record hash` (corrections included).
6. **Ledger de-duplication**: `(match_id, source_event_id)` unique; identical re-delivery is ignored,
   conflicting re-delivery is an error.

Crash tests: `test_crash_after_fm_applied_result_never_double_imports` (FM applies, bridge dies before
recording; restart recovers with `import_count == 1`) and `test_crash_mid_match_resumes_collection`.

## Preservation and audit

Before any change, the FM pre-match state from the adapter is saved as an append-only snapshot with its
SHA-256. Every transition is stored with reason, payload and error; every action writes to `audit_log`.
`python -m fmfc_hybrid history --db <file> <match_id>` prints the trail.

## Mapping to FM's own lifecycle

FM's internal stages (from [FM_RESEARCH §5](FM_RESEARCH.md)) map onto ours as:
FM detects/schedules → `FIXTURE_DETECTED`; the hold before kick-off → `FM_STATE_CAPTURED` …
`MATCH_DATA_CAPTURED`; FM result representation and native processing → `FM_IMPORT_*`. How the FM side
implements "hold" and "import" (steering vs post-hoc edit) is the open research question; the lifecycle
does not change with that choice.
