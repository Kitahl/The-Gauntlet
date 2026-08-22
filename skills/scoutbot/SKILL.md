---
name: scoutbot
description: Research Discovery module. Trigger: /space, /scoutbot, prior art, literature search, current facts, existing tools, repositories, standards, or "has this been done?". Finds and verifies reusable work before new design.
---

# Research Discovery

Search before novelty and before absence claims.

## Discovery protocol

1. Translate the request into mechanisms/capabilities, not only project vocabulary.
2. Search primary/official sources first when possible.
3. Expand with synonyms, neighboring fields, authors, citations, and implementation terms.
4. Prefer executable/open implementations when the task is engineering-oriented.
5. Inspect the source passage/repository, not only search snippets.
6. Record license, version/date, guarantee class, and transport limits.

## Source hierarchy

Prefer:

1. official specifications / primary papers / original repositories;
2. maintained documentation and archival records;
3. high-quality secondary synthesis;
4. community discussion for experience signals, clearly labeled.

A source count is not independence. Detect derivative citations and shared provenance.

## Absence / novelty claims

`NOT FOUND` means the stated search scope found nothing. It does not prove nonexistence.

Before novelty credit, provide:

- searched scope;
- nearest established class;
- concrete differentiator;
- whether the delta is mechanism, assumption, interface, guarantee, or merely packaging/renaming.

## Tooling

The optional public helper `tools/scout.py` performs a keyless OpenAlex lookup. Web/API tools may be used when available. No private account, email, path, or project index is assumed.
