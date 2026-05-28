"""Live vehicle smoke-harness boundary.

LIVE VEHICLE CODE: use only after the operator checklist and Claude review.
"""

from autopulse.live.harness import (
    ADAPTER_FAILURE_EXIT,
    CONFIG_ERROR_EXIT,
    OK_EXIT,
    SAFETY_ABORT_EXIT,
    SmokeHarnessConfig,
    SmokeHarnessSummary,
    run_smoke_capture,
)

__all__ = [
    "ADAPTER_FAILURE_EXIT",
    "CONFIG_ERROR_EXIT",
    "OK_EXIT",
    "SAFETY_ABORT_EXIT",
    "SmokeHarnessConfig",
    "SmokeHarnessSummary",
    "run_smoke_capture",
]
