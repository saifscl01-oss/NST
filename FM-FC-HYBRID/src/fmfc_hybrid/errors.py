"""Error hierarchy for the bridge.

Every error carries a machine-readable ``code`` so failures can be recorded in
the audit log and mapped to lifecycle failure states without string matching.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class HybridError(Exception):
    """Base class for all FM-FC Hybrid errors."""

    code = "HYBRID_ERROR"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


@dataclass(frozen=True)
class ValidationIssue:
    """A single validation problem. ``path`` is a dotted location in the payload."""

    code: str
    message: str
    path: str = ""
    severity: str = "error"  # "error" blocks processing, "warning" is recorded only

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "path": self.path, "severity": self.severity}


class ValidationError(HybridError):
    code = "VALIDATION_FAILED"

    def __init__(self, message: str, issues: list[ValidationIssue]) -> None:
        super().__init__(message, details={"issues": [i.to_dict() for i in issues]})
        self.issues = issues


class ContractError(HybridError):
    """Malformed or incompatible serialized contract."""

    code = "CONTRACT_ERROR"


class ContractVersionError(ContractError):
    code = "CONTRACT_VERSION_UNSUPPORTED"


class InvalidTransitionError(HybridError):
    code = "INVALID_TRANSITION"


class ConcurrencyError(HybridError):
    """Optimistic-concurrency check failed: someone else advanced the record."""

    code = "CONCURRENT_MODIFICATION"


class LedgerError(HybridError):
    code = "LEDGER_ERROR"


class LedgerFinalizedError(LedgerError):
    code = "LEDGER_FINALIZED"


class DuplicateEventError(LedgerError):
    code = "DUPLICATE_EVENT"


class DuplicateImportError(HybridError):
    code = "DUPLICATE_IMPORT"


class IdentityError(HybridError):
    code = "IDENTITY_ERROR"


class MappingError(HybridError):
    code = "MAPPING_ERROR"


class AdapterError(HybridError):
    """Raised by adapters. ``retryable`` tells the orchestrator whether a retry is safe."""

    code = "ADAPTER_ERROR"

    def __init__(self, message: str, *, retryable: bool = False, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details=details)
        self.retryable = retryable


class PreparationError(AdapterError):
    code = "PREPARATION_FAILED"


class LaunchError(AdapterError):
    code = "LAUNCH_FAILED"


class MatchInterruptedError(AdapterError):
    code = "MATCH_INTERRUPTED"


class DataCaptureError(AdapterError):
    code = "DATA_CAPTURE_FAILED"


class ImportFailedError(AdapterError):
    code = "IMPORT_FAILED"


class VerificationError(AdapterError):
    code = "VERIFICATION_FAILED"


@dataclass
class IssueCollector:
    """Accumulates validation issues so callers see every problem at once."""

    issues: list[ValidationIssue] = field(default_factory=list)

    def error(self, code: str, message: str, path: str = "") -> None:
        self.issues.append(ValidationIssue(code, message, path, "error"))

    def warning(self, code: str, message: str, path: str = "") -> None:
        self.issues.append(ValidationIssue(code, message, path, "warning"))

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def raise_if_errors(self, message: str) -> None:
        if self.errors:
            raise ValidationError(message, self.issues)
