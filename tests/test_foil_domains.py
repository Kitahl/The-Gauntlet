from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_domains as fd  # noqa: E402


class FoilDomainTests(unittest.TestCase):
    def test_extended_domain_examples(self) -> None:
        cases = {
            "I design curriculum and assessment for a classroom": "education_learning",
            "I work on robotics and control systems": "robotics_control",
            "I do investigative journalism and fact checking": "journalism_media",
            "I model renewable energy and battery systems": "energy_power",
            "I build CAD models for mechanical engineering": "mechanical_engineering",
            "I work in healthcare and patient care workflows": "medicine_healthcare",
            "I study history and archival research": "humanities_history",
            "I run startup fundraising and product market fit experiments": "entrepreneurship",
            "I use Lean for theorem proving and formal verification": "formal_methods_theorem_proving",
            "I tune Postgres schemas and data warehouse ETL jobs": "databases_data_engineering",
            "I run Kubernetes and Terraform for platform engineering": "cloud_devops_platform",
            "I study protein structure prediction and sequence analysis": "bioinformatics_computational_biology",
            "I build image processing and rendering systems": "computer_vision_graphics",
            "I evaluate language models for AI safety and robustness": "ai_safety_evaluation",
            "I work on PCB circuit design and signal processing": "electrical_electronics",
            "I optimize integer programs and scheduling models": "optimization_operations_research",
            "I write API documentation for developers": "technical_writing_documentation",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertIn(expected, fd.infer_domains(text))

    def test_registry_is_broad_and_only_marks_relevance(self) -> None:
        self.assertGreaterEqual(len(fd.DOMAIN_KEYWORDS), 40)
        self.assertIsInstance(fd.DOMAIN_KEYWORDS, dict)
        self.assertNotIn("strength", " ".join(fd.DOMAIN_KEYWORDS).lower())
        self.assertNotIn("weakness", " ".join(fd.DOMAIN_KEYWORDS).lower())


if __name__ == "__main__":
    unittest.main()
