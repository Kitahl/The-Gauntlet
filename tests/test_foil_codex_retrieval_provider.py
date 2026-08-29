from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_codex_retrieval_provider import (  # noqa: E402
    RetrievalDiscoveryStatus,
    parse_retrieval_discovery,
)


SCHEMA = ROOT / "benchmarks" / "protocols" / "foil_codex_retrieval_provider_v1.schema.json"


class CodexRetrievalProviderTests(unittest.TestCase):
    def test_provider_schema_uses_supported_shape_and_host_owns_url_validation(self) -> None:
        raw = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(set(raw), {"type", "additionalProperties", "properties", "required"})
        self.assertNotIn("format", json.dumps(raw))
        self.assertEqual(raw["properties"]["sources"]["maxItems"], 2)

    def test_valid_found_output_is_accepted(self) -> None:
        parsed = parse_retrieval_discovery(
            {
                "status": "FOUND",
                "sources": [
                    {
                        "url": "https://docs.python.org/3/library/functions.html",
                        "title": "Built-in Functions",
                        "quote": "Print objects to the text stream file.",
                    }
                ],
            }
        )
        self.assertEqual(parsed.status, RetrievalDiscoveryStatus.FOUND)
        self.assertEqual(len(parsed.sources), 1)

    def test_url_semantics_fail_closed_after_provider_validation(self) -> None:
        for url in (
            "http://example.com/source",
            "https://user:secret@example.com/source",
            "https://example.com/source#fragment",
        ):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "credential-free HTTPS"):
                parse_retrieval_discovery(
                    {
                        "status": "FOUND",
                        "sources": [{"url": url, "title": "T", "quote": "Q"}],
                    }
                )

    def test_status_count_and_unknown_fields_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "FOUND requires"):
            parse_retrieval_discovery({"status": "FOUND", "sources": []})
        with self.assertRaisesRegex(ValueError, "UNRESOLVED cannot"):
            parse_retrieval_discovery(
                {
                    "status": "UNRESOLVED",
                    "sources": [{"url": "https://example.com/x", "title": "T", "quote": "Q"}],
                }
            )
        with self.assertRaisesRegex(ValueError, "unknown=.*gold"):
            parse_retrieval_discovery({"status": "UNRESOLVED", "sources": [], "gold": "x"})


if __name__ == "__main__":
    unittest.main()
