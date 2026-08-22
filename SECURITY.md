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

## Scope

Security-relevant areas include code execution, dependency/supply-chain integrity, unsafe parsing or deserialization, path handling, secret exposure, workflow permissions, and misleading verification states that could cause unsafe automated action.

Research-quality or correctness disagreements that do not create a security exposure should use the normal issue templates instead.
