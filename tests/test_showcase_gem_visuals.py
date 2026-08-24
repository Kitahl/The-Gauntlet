from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEM_VISUALS = (
    "gem-mind.svg",
    "gem-space.svg",
    "gem-reality.svg",
    "gem-power.svg",
    "gem-time.svg",
)


class ShowcaseGemVisualTests(unittest.TestCase):
    def test_external_gem_svgs_are_self_contained(self) -> None:
        """External SVG <img> documents cannot inherit the page stylesheet."""
        html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        for name in GEM_VISUALS:
            with self.subTest(name=name):
                self.assertIn(f'src="visuals/{name}"', html)
                text = (ROOT / "docs" / "visuals" / name).read_text(encoding="utf-8")
                self.assertIn("<style>", text)
                self.assertIn("fill:#", text)
                self.assertIn("stroke:#", text)
                self.assertIn("font:", text)
                self.assertNotIn("<circle", text.lower())


if __name__ == "__main__":
    unittest.main()
