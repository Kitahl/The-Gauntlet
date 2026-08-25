"""The sole production bridge from discovery envelopes to generated-spec admission."""

from __future__ import annotations

from foil_formalization_admission import (
    AdmittedCompiledTaskSpec,
    FormalizationAdmissionReceipt,
    compile_admitted_task_spec,
)
from foil_obligation_discovery import DiscoveryEnvelope, DiscoveryStatus


def compile_admitted_discovery(
    envelope: DiscoveryEnvelope,
    *,
    admission: FormalizationAdmissionReceipt,
) -> AdmittedCompiledTaskSpec:
    """Compile a FOUND envelope only through an independent admitted receipt.

    This wrapper adds no calibration, authority, execution, repair, or routing.
    The benchmark intentionally does not call it because R1.6 has no admissible
    calibration evidence.
    """

    if not isinstance(envelope, DiscoveryEnvelope):
        raise TypeError("envelope must be DiscoveryEnvelope")
    if envelope.status is not DiscoveryStatus.FOUND or envelope.task_spec is None:
        raise ValueError("only a FOUND discovery envelope can request admission")
    if not isinstance(admission, FormalizationAdmissionReceipt):
        raise TypeError("admission must be FormalizationAdmissionReceipt")
    return compile_admitted_task_spec(
        envelope.task_spec,
        observed_a0_digest=envelope.a0_digest,
        admission=admission,
    )
