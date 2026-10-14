"""Independent, offline research commentary. No trading or file-loading API."""

from .foundation import (
    MockResearchProvider, ResearchProvider, ValidationError,
    approve_snapshot, analyze, validate_snapshot, validate_report,
)

__all__ = ["MockResearchProvider", "ResearchProvider", "ValidationError",
           "approve_snapshot", "analyze", "validate_snapshot", "validate_report"]
