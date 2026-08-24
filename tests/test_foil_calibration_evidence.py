from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_types import EvidenceClass  # noqa: E402
from foil_authority import (  # noqa: E402
    AuthorityCeiling,
    EvidenceSurface,
    SensorRegistration,
)
from foil_residuals import (  # noqa: E402
    CalibrationContext,
    CalibrationState,
    SensorCalibration,
    check_calibration,
)


class CalibrationEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 23, tzinfo=timezone.utc)
        self.registration = SensorRegistration(
            "sensor",
            EvidenceClass.MEASURED,
            EvidenceSurface.ANSWER,
            AuthorityCeiling.REPAIR_PROPOSAL_ALLOWED,
            "answer.scope",
            "foil.sensor",
            "1",
        )
        self.digests = tuple(char * 64 for char in "abcdef")

    def calibration(self, **overrides):
        values = dict(
            sensor_id="sensor",
            calibration_id="calibration",
            scope_digest=self.digests[0],
            model_digest=self.digests[1],
            config_digest=self.digests[2],
            protocol_digest=self.digests[3],
            evidence_digest=self.digests[4],
            thresholds_digest=self.digests[5],
            correct_outputs=100,
            false_flags=2,
            wrong_outputs=50,
            true_flags=30,
            expires_at=self.now + timedelta(days=1),
        )
        values.update(overrides)
        return SensorCalibration(**values)

    def context(self, thresholds_digest: str | None = None):
        return CalibrationContext(
            *self.digests[:5],
            thresholds_digest or self.digests[5],
            self.now,
        )

    def test_calibration_requires_both_classes_and_valid_counts(self):
        with self.assertRaises(ValueError):
            self.calibration(correct_outputs=0)
        with self.assertRaises(ValueError):
            self.calibration(wrong_outputs=0)
        with self.assertRaises(ValueError):
            self.calibration(false_flags=101)
        calibrated = self.calibration()
        self.assertEqual(calibrated.false_flag_rate, 0.02)
        self.assertEqual(calibrated.residual_recall, 0.6)

    def test_threshold_binding_is_required_for_current_status(self):
        good = check_calibration(self.registration, self.calibration(), self.context())
        mismatch = check_calibration(
            self.registration,
            self.calibration(),
            self.context("0" * 64),
        )
        self.assertEqual(good.state, CalibrationState.CURRENT)
        self.assertEqual(mismatch.state, CalibrationState.MISMATCH)


if __name__ == "__main__":
    unittest.main()
