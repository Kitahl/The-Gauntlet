# GitHub Pages setup

The showcase is a dependency-free static site in `docs/` and is ready for GitHub Pages branch publishing.

One repository setting must be enabled by an administrator because the connected GitHub tool used to build this release does not expose the Pages settings API:

1. Open **Settings → Pages** in `Kitahl/The-Gauntlet`.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Select branch **main** and folder **/docs**.
4. Save.

Once enabled, the expected project-site URL is:

`https://kitahl.github.io/The-Gauntlet/`

The site intentionally uses no build step, remote fonts, analytics, trackers, or required JavaScript. Skill links use canonical GitHub URLs so they remain valid when only `docs/` is published.
