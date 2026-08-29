"""Compatibility import for the canonical active FOIL v2 runtime.

New code may import :func:`run_foil` from either this historical module name or
``foil_runtime_active``.  Both names deliberately expose the same validated
adapter boundary.
"""

from foil_runtime_active import (
    FoilRuntimePolicyV2,
    FoilRuntimeReceiptV2,
    RuntimeOutcomeV2,
    run_foil,
)

__all__ = [
    "FoilRuntimePolicyV2",
    "FoilRuntimeReceiptV2",
    "RuntimeOutcomeV2",
    "run_foil",
]
