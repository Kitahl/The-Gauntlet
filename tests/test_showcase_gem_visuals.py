from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEM_SCENES = ("mind", "space", "reality", "power", "time")
LEGACY_GEM_VISUALS = tuple(f"gem-{name}.svg" for name in GEM_SCENES)


class ShowcaseGemVisualTests(unittest.TestCase):
    def test_r19_gem_visuals_use_local_semantic_canvas(self) -> None:
        """R19 replaces the external Gem SVG stack with one local semantic field."""
        html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "docs" / "system-field.js").read_text(encoding="utf-8")

        self.assertIn('id="system-field-canvas"', html)
        self.assertIn('<script src="system-field.js" defer></script>', html)
        for scene in GEM_SCENES:
            with self.subTest(scene=scene):
                self.assertIn(f'data-scene="{scene}"', html)
                self.assertIn(f"draw{scene.title()}", js)

        # The old regression existed because external <img> SVGs cannot inherit
        # page CSS. R19 does not load those documents at all, so keeping hidden
        # references would preserve an obsolete implementation contract.
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
