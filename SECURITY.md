# Security Policy

## Supported versions

Security fixes are applied to the latest public release and `main`.

## Reporting a vulnerability

Please do **not** publish exploitable vulnerability details in a public issue before maintainers have had a reasonable opportunity to assess them.

Preferred route:

1. Use GitHub's private vulnerability reporting / security-advisory interface when available for this repository.
2. If that interface is unavailable, open a minimal public issue stating that you have a security report and request a private contact path. Do not include exploit details or sensitive data.

A useful report includes:

- affected file/module and version/commit;
- threat model and prerequisites;
- reproducible steps or proof of concept;
- expected vs. observed behavior;
- impact and scope;
- suggested mitigation if known.

## Secret handling

- API keys and model credentials are environment-only; they are not read from repository keystores.
- `.env*`, common private-key/certificate formats, local credential JSON, FOIL onboarding outputs, and Gauntlet runtime state are gitignored.
- CI runs a full-history Gitleaks scan from a full-depth checkout.
- Stable release candidates must have a passing secret-history gate before promotion.
- Contributors should use a GitHub `noreply` commit email when they do not want a personal email address recorded permanently in Git history.

If a real credential is ever committed, assume it is compromised: revoke/rotate it first, then remove it from current content and, when appropriate, rewrite history. History rewriting is not a substitute for credential rotation.

## Local privacy boundary

FOIL profiles and Gauntlet state are stored outside tracked repository content. On POSIX systems, runtime directories are restricted to mode `0700` and state/profile files to `0600`; Windows relies on the user's normal profile/filesystem ACLs.

The turn-boundary evaluator persists only lossy similarity fingerprints of recent assistant messages. It does not persist the assistant-message text itself.

## External model/data boundary

Deterministic Gauntlet and FOIL monitoring requires no external model and does not transmit prompts to OpenRouter.

Optional OpenRouter-backed boundary judgment, independent red-team review, and SNAP **do transmit the supplied prompt/brief/target and generated review context to the configured external model provider**. Do not enable those optional paths for material that must not leave the local environment. Provider retention and privacy terms remain the provider's responsibility.

## Supply-chain controls

- GitHub Actions used by release workflows are pinned to immutable full commit SHAs.
- Python direct dependencies are exact-version pinned.
- CI runs `pip-audit` against runtime and development requirement sets.
- CodeQL runs on pushes, pull requests, and its scheduled cadence.
- Dependabot monitors both GitHub Actions and Python dependencies.

## Repository boundary

The public runtime is Gauntlet + FOIL and the documented research modules in this repository. Mastermind is **not** a runtime dependency and must not be added as a package, helper, skill, state directory, import, or benchmark-control source. CI contains an explicit regression gate for this boundary. Historical audit prose may name evaluation procedures without importing their implementation.

## Scope

Security-relevant areas include code execution, dependency/supply-chain integrity, unsafe parsing or deserialization, path handling, secret exposure, external data egress, local-profile privacy, workflow permissions, and misleading verification states that could cause unsafe automated action.

Research-quality or correctness disagreements that do not create a security exposure should use the normal issue templates instead.
