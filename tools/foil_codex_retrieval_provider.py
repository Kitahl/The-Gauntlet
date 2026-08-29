"""Closed validation for Codex structured retrieval discovery output.

Provider JSON Schema intentionally uses only the Structured Outputs subset.
URL semantics stay at this host boundary because JSON Schema ``format: uri``
is not supported by the provider and is not an authority check in any case.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping
from urllib.parse import urlparse


class RetrievalDiscoveryStatus(str, Enum):
    FOUND = "FOUND"
    UNRESOLVED = "UNRESOLVED"


def _closed(raw: Mapping[str, object], expected: frozenset[str], name: str) -> None:
    actual = frozenset(raw)
    if actual != expected:
        raise ValueError(
            f"closed {name} schema mismatch: missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _bounded_text(name: str, value: object, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be non-empty text of at most {maximum} characters")
    return value


def _public_https_shape(value: str) -> bool:
    parsed = urlparse(value)
    return bool(
        parsed.scheme == "https"
        and parsed.hostname
        and parsed.username is None
        and parsed.password is None
        and parsed.port in (None, 443)
        and not parsed.fragment
    )


@dataclass(frozen=True)
class RetrievalSource:
    url: str
    title: str
    quote: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "RetrievalSource":
        if not isinstance(raw, Mapping):
            raise TypeError("retrieval source must be a mapping")
        _closed(raw, frozenset({"url", "title", "quote"}), "retrieval-source")
        url = _bounded_text("url", raw["url"], 2_048)
        if not _public_https_shape(url):
            raise ValueError("url must be canonical credential-free HTTPS without a fragment")
        return cls(
            url,
            _bounded_text("title", raw["title"], 500),
            _bounded_text("quote", raw["quote"], 20_000),
        )


@dataclass(frozen=True)
class RetrievalDiscovery:
    status: RetrievalDiscoveryStatus
    sources: tuple[RetrievalSource, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "RetrievalDiscovery":
        if not isinstance(raw, Mapping):
            raise TypeError("retrieval discovery must be a mapping")
        _closed(raw, frozenset({"status", "sources"}), "retrieval-discovery")
        status = RetrievalDiscoveryStatus(raw["status"])
        rows = raw["sources"]
        if not isinstance(rows, list):
            raise TypeError("sources must be a list")
        if len(rows) > 2:
            raise ValueError("sources exceeds the two-source bound")
        sources = tuple(RetrievalSource.from_mapping(row) for row in rows)
        if status is RetrievalDiscoveryStatus.FOUND and not sources:
            raise ValueError("FOUND requires at least one source")
        if status is RetrievalDiscoveryStatus.UNRESOLVED and sources:
            raise ValueError("UNRESOLVED cannot carry sources")
        return cls(status, sources)


def parse_retrieval_discovery(raw: Mapping[str, object]) -> RetrievalDiscovery:
    """Validate provider output before any URL is resolved or fetched."""

    return RetrievalDiscovery.from_mapping(raw)


__all__ = [
    "RetrievalDiscovery",
    "RetrievalDiscoveryStatus",
    "RetrievalSource",
    "parse_retrieval_discovery",
]
