# GitHub Pages deployment

The Evidence-Governed Research Toolkit showcase is a dependency-free static site in `docs/`.

## Repository setting

1. Open **Settings → Pages** in `Kitahl/The-Gauntlet`.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Select branch **main** and folder **/docs**.
4. Save.

Expected project-site URL:

`https://kitahl.github.io/The-Gauntlet/`

## Deployment properties

- no build step;
- no required JavaScript;
- no remote fonts, analytics, or trackers;
- canonical GitHub links for repository artifacts;
- deterministic browser validation in CI;
- public content is research/portfolio material and follows the repository evidence boundary.

If the repository slug is renamed later, update the Pages URL, `CITATION.cff`, badges, canonical links, and deployment documentation in the same change.
