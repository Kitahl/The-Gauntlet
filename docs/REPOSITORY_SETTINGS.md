# Repository Settings Checklist

Some GitHub security and governance controls are repository settings rather than files. They should be enabled by an administrator for the professional research-software baseline.

## Required / recommended settings

### General

- Repository visibility: **Public**
- Default branch: **main**
- Issues: **Enabled**
- Repository description: **Evidence-governed research toolkit with Gauntlet process assurance and FOIL adaptive reasoning support.**
- Homepage: **https://kitahl.github.io/The-Gauntlet/**
- Suggested topics: `research-software`, `ai-assisted-research`, `verification`, `reproducibility`, `evaluation`, `foil`, `metareasoning`, `runtime-verification`
- Discussions: optional; enable only if there is enough external use to justify maintaining it

### Commit identity privacy

If a personal email address should not be public in future Git metadata, enable GitHub's **Keep my email addresses private** setting and configure local Git to use the account's GitHub `noreply` address before committing. Existing Git history is immutable unless deliberately rewritten; rewriting public history should be done only after evaluating clone/fork/tag consequences.

### Pull requests / branch protection

Protect `main` with a ruleset or branch protection requiring:

- pull request before merge;
- required status checks for Research software validation (`validate`), CodeQL (`analyze`), the three Security gates jobs, and the stable `Runtime portability gate`;
- branch up to date before merge;
- for a single-maintainer phase, PR review may use **0 required external approvals** while CI remains mandatory; increase approvals when regular maintainers/reviewers exist;
- conversation resolution before merge;
- no force pushes to `main`;
- no branch deletion of `main`.

The portability workflow intentionally runs on every pull request and exposes one stable `Runtime portability gate`, avoiding GitHub required-check deadlocks caused by workflow-level path filtering. These server-side settings are still the enforcement layer and must be enabled separately.

### Security and analysis

Enable:

- Dependency Graph;
- Dependabot alerts;
- Dependabot security updates;
- secret scanning and push protection;
- private vulnerability reporting;
- CodeQL / code scanning.

The tracked `Security gates` workflow adds a full-history Gitleaks scan and Python dependency audit. GitHub-native secret scanning/push protection should still be enabled because it can block credentials before they enter history.

After **Dependency Graph** is enabled, restore a blocking PR dependency-review workflow using `actions/dependency-review-action` pinned to an immutable full commit SHA.

### Pages

Publish from:

- branch: `main`
- folder: `/docs`

Expected URL: `https://kitahl.github.io/The-Gauntlet/`

### Releases / citation

- create signed or clearly attributed semantic-version tags for stable releases;
- publish a GitHub Release with the corresponding changelog section;
- archive the first evidence-bearing stable release with Zenodo or an equivalent archival service;
- add the minted DOI to `CITATION.cff`.

Do not create a stable tag until the exact candidate SHA has passed validation, CodeQL, security, and portability gates.

## Runtime boundary

The repository runtime is Gauntlet + FOIL and the documented public research modules. Mastermind implementation, packages, hooks, state, skills, and benchmark-control files are not part of this repository. Historical audit prose may name an external evaluation procedure without importing its implementation.

## Why these settings matter

The repository files can define reproducibility, security, and governance contracts, but settings are the enforcement layer. A professional research portfolio should not represent a file-based policy as enforced when the corresponding repository control is disabled.
