from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECIALIST_SCENES = ("mind", "space", "reality", "power", "time")
LEGACY_GEM_VISUALS = tuple(f"gem-{name}.svg" for name in SPECIALIST_SCENES)


class ShowcaseSpecialistVisualTests(unittest.TestCase):
    def test_r20_specialist_visuals_use_local_semantic_canvas(self) -> None:
        """R20 retains one local semantic field while product display names change."""
        html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "docs" / "system-field.js").read_text(encoding="utf-8")

        self.assertIn('id="system-field-canvas"', html)
        self.assertIn('<script src="system-field.js" defer></script>', html)
        for scene in SPECIALIST_SCENES:
            with self.subTest(scene=scene):
                self.assertIn(f'data-scene="{scene}"', html)
                self.assertIn(f"draw{scene.title()}", js)

        # Legacy external SVGs remain unused; technical scene IDs stay stable so
        # the animation/runtime contract does not become a branding migration.
        for name in LEGACY_GEM_VISUALS:
            with self.subTest(legacy=name):
                self.assertNotIn(f'src="visuals/{name}"', html)

        self.assertIn("gemGeometry", js)
        self.assertIn("IntersectionObserver", js)
        self.assertNotIn("THREE.", js)
        self.assertNotIn("cdnjs", js)
        self.assertNotIn("https://", js)


if __name__ == "__main__":
    unittest.main()
