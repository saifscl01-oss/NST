"""Adapter protocols and mock implementations.

Real game adapters will live in their own modules (e.g. ``fm26_plugin``,
``fifa22_live_editor``) once the research gates confirm what they can do.
"""
from .base import (ControlMode, FifaAdapter, FifaCapabilities, FifaMatchRequest, FifaPlayerSpec, FifaTeamSetup,
                   FmAdapter, FmCapabilities, FmMatchContext, ImportReceipt, IntegrationLevel, PreparationReceipt,
                   VerificationCheck, VerificationReport)

__all__ = ["ControlMode", "FifaAdapter", "FifaCapabilities", "FifaMatchRequest", "FifaPlayerSpec", "FifaTeamSetup",
           "FmAdapter", "FmCapabilities", "FmMatchContext", "ImportReceipt", "IntegrationLevel",
           "PreparationReceipt", "VerificationCheck", "VerificationReport"]
