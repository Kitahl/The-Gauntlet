from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_claims import Applicability, Decidability, ImmutableBindings  # noqa: E402
from egrt_types import EvidenceClass  # noqa: E402
from foil_authority import (  # noqa: E402
    AuthorityAction,
    AuthorityCeiling,
    AuthorityContext,
    EvidenceSurface,
    SensorRegistration,
)
from foil_residual_scanner import DiagnosticCase, ResidualScanPlan, scan  # noqa: E402
from foil_residuals import (  # noqa: E402
    CalibrationContext,
    CalibrationState,
    SensorCalibration,
    check_calibration,
    map_to_authority,
)
from foil_v5_metrics import ResidualDiagnosticNeed  # noqa: E402


def bindings() -> ImmutableBindings:
    return ImmutableBindings(*[char * 64 for char in "abcde"])


def report():
    need = ResidualDiagnosticNeed(
        "need-1",
        "claim-1",
        "match",
        "builtin.exact_match",
        1,
        Decidability.DETERMINISTIC,
        Applicability.APPLICABLE,
        bindings(),
    )
    plan = ResidualScanPlan("claim-1", bindings().a0_digest, bindings(), (need,))
    return scan(
        plan,
        bindings().a0_digest,
        (DiagnosticCase("need-1", {"actual": "x", "expected": "y"}, {}),),
    )


def registration() -> SensorRegistration:
    return SensorRegistration(
        "sensor-1",
        EvidenceClass.MEASURED,
        EvidenceSurface.ANSWER,
        AuthorityCeiling.REPAIR_PROPOSAL_ALLOWED,
        "answer.code",
        "foil.sensor",
        "1",
    )


def context(now: datetime) -> CalibrationContext:
    return CalibrationContext(*[char * 64 for char in "f01234"], now)


def calibration(
    now: datetime, *, expiry: timedelta = timedelta(days=1), sensor_id: str = "sensor-1"
) -> SensorCalibration:
    return SensorCalibration(
        sensor_id, "cal-1", *[char * 64 for char in "f01234"], 100, 1, 40, 24, now + expiry
    )


class ResidualAuthorityTests(unittest.TestCase):
    def test_current_calibration_allows_only_registered_shadow_authority(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mapped = map_to_authority(
            report(),
            registration(),
            calibration(now),
            context(now),
            AuthorityContext(True, True, True),
        )
        self.assertEqual(mapped.calibration.state, CalibrationState.CURRENT)
        self.assertEqual(mapped.decision.action, AuthorityAction.PROPOSE_REPAIR_SHADOW)
        self.assertFalse(mapped.decision.execution_authorized)

    def test_calibration_context_digests_must_be_canonical_lowercase_sha256(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for invalid in ("A" * 64, "g" * 64, "a" * 63):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                CalibrationContext(invalid, *[char * 64 for char in "01234"], now)

    def test_stale_or_mismatched_calibration_fails_closed(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        stale = check_calibration(
            registration(), calibration(now, expiry=timedelta()), context(now)
        )
        mismatch = check_calibration(
            registration(), calibration(now, sensor_id="other"), context(now)
        )
        self.assertEqual(
            (stale.state, mismatch.state), (CalibrationState.STALE, CalibrationState.MISMATCH)
        )
        mapped = map_to_authority(
            report(),
            registration(),
            calibration(now, expiry=timedelta()),
            context(now),
            AuthorityContext(True, True, True),
        )
        self.assertEqual(mapped.decision.action, AuthorityAction.STAND_DOWN)


if __name__ == "__main__":
    unittest.main()
