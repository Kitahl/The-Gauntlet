# Repository Settings Checklist

Some GitHub security and governance controls are repository settings rather than files. They should be enabled by an administrator for the professional research-software baseline.

## Required / recommended settings

### General

- Repository visibility: **Public**
- Default branch: **main**
- Issues: **Enabled**
- Discussions: optional; enable only if there is enough external use to justify maintaining it

### Pull requests / branch protection

Protect `main` with a ruleset or branch protection requiring:

- pull request before merge;
- required status checks: **Research software validation** and **CodeQL**;
- branch up to date before merge when practical;
- conversation resolution before merge;
- no force pushes to `main`;
- no branch deletion of `main`.

### Security and analysis

Enable:

- Dependency Graph;
- Dependabot alerts;
- Dependabot security updates;
- secret scanning / push protection when available for the account/repository;
- private vulnerability reporting;
- CodeQL / code scanning.

After **Dependency Graph** is enabled, restore a blocking PR dependency-review workflow using `actions/dependency-review-action`.

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

## Why these settings matter

The repository files can define reproducibility, security, and governance contracts, but settings are the enforcement layer. A professional research portfolio should not represent a file-based policy as enforced when the corresponding repository control is disabled.
