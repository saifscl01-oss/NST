"""Central bridge service: orchestration and configuration."""
from .config import BridgeConfig
from .orchestrator import MatchOrchestrator, MatchOutcome

__all__ = ["BridgeConfig", "MatchOrchestrator", "MatchOutcome"]
