"""The sole production bridge from discovery envelopes to generated-spec admission."""

from __future__ import annotations

from foil_arithmetic_rule_bank import ArithmeticRuleBankEnvelope
from foil_formalization_admission import (
    AdmittedCompiledTaskSpec,
    FormalizationAdmissionReceipt,
    FormalizationRouteBinding,
    compile_admitted_task_spec,
)
from foil_obligation_discovery import DiscoveryEnvelope, DiscoveryStatus
from foil_obligation_discovery_v2 import DiscoveryEnvelopeV2

GeneratedDiscoveryEnvelope = (
    DiscoveryEnvelope | DiscoveryEnvelopeV2 | ArithmeticRuleBankEnvelope
)
_ENVELOPE_TYPES = (
    DiscoveryEnvelope,
    DiscoveryEnvelopeV2,
    ArithmeticRuleBankEnvelope,
)


def compile_admitted_discovery(
    envelope: GeneratedDiscoveryEnvelope,
    *,
    admission: FormalizationAdmissionReceipt,
    binding: FormalizationRouteBinding,
) -> AdmittedCompiledTaskSpec:
    """Compile a FOUND envelope only through an independent admitted receipt.

    This wrapper adds no calibration, authority, execution, repair, or routing.
    The benchmark intentionally does not call it because R1.6 has no admissible
    calibration evidence.
    """

    if not isinstance(envelope, _ENVELOPE_TYPES):
        raise TypeError("envelope must be a supported generated-spec envelope")
    if envelope.status is not DiscoveryStatus.FOUND or envelope.task_spec is None:
        raise ValueError("only a FOUND discovery envelope can request admission")
    if not isinstance(admission, FormalizationAdmissionReceipt):
        raise TypeError("admission must be FormalizationAdmissionReceipt")
    if not isinstance(binding, FormalizationRouteBinding):
        raise TypeError("binding must be FormalizationRouteBinding")
    if envelope.origin != "GENERATED_UNADMITTED":
        raise ValueError("generated origin must remain visible at admission")
    if not envelope.admission_required or envelope.execution_authorized:
        raise ValueError("discovery envelope authority flags are invalid")
    if binding.binding_digest != admission.route_binding_digest:
        raise ValueError("admission receipt does not match the supplied route binding")
    if binding.route_id != envelope.route:
        raise ValueError("route binding does not name the envelope route")
    if binding.task_regime_sha256 != envelope.route_binding_digest:
        raise ValueError("route binding does not bind the generator configuration")
    if binding.target_schema != envelope.task_spec.get("schema"):
        raise ValueError("route binding does not target the generated schema")
    if admission.source_text_sha256 != envelope.input_digest:
        raise ValueError("admission receipt does not bind the complete discovery input")
    if admission.generated_spec_sha256 != envelope.task_spec_digest:
        raise ValueError("admission receipt does not bind the envelope task spec")
    if envelope.task_spec.get("config_digest") != envelope.route_binding_digest:
        raise ValueError("generated spec does not bind the envelope configuration")
    return compile_admitted_task_spec(
        envelope.task_spec,
        observed_a0_digest=envelope.a0_digest,
        admission=admission,
    )
