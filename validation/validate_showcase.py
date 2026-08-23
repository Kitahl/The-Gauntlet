from __future__ import annotations

import base64
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "docs/index.html"
CSS = ROOT / "docs/styles.css"
VISUAL_CSS = ROOT / "docs/visuals.css"
README = ROOT / "README.md"
VISUAL_VERSION = ROOT / "docs/visuals/VERSION"
VISUAL_PATHS = (
    "docs/visuals/gauntlet-hero.svg",
    "docs/visuals/gauntlet-system-map.svg",
    "docs/visuals/foil-diagnostic-loop.svg",
)

html = HTML.read_text(encoding="utf-8")
css = CSS.read_text(encoding="utf-8")
visual_css = VISUAL_CSS.read_text(encoding="utf-8")
combined_css = css + "\n" + visual_css
checks: dict[str, bool] = {}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.hrefs: list[str] = []
        self.headings: list[str] = []
        self.links: list[dict[str, str]] = []
        self.scripts: list[dict[str, str]] = []
        self.meta: list[dict[str, str]] = []
        self.images: list[dict[str, str]] = []
        self.main_count = 0
        self.nav_count = 0
        self.details_count = 0
        self.lang: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key: value or "" for key, value in attrs}
        if tag == "html":
            self.lang = data.get("lang")
        if data.get("id"):
            self.ids.append(data["id"])
        if tag == "a" and data.get("href"):
            self.hrefs.append(data["href"])
        if tag == "link":
            self.links.append(data)
        if tag == "script":
            self.scripts.append(data)
        if tag == "meta":
            self.meta.append(data)
        if tag == "img":
            self.images.append(data)
        if tag in ("h1", "h2", "h3"):
            self.headings.append(tag)
        if tag == "main":
            self.main_count += 1
        if tag == "nav":
            self.nav_count += 1
        if tag == "details":
            self.details_count += 1


def parse_page(document: str) -> PageParser:
    parsed = PageParser()
    parsed.feed(document)
    return parsed


def remote_runtime_assets_absent(parsed: PageParser) -> bool:
    for script in parsed.scripts:
        if script.get("src", "").startswith(("http://", "https://")):
            return False
    for link in parsed.links:
        rel = set(link.get("rel", "").lower().split())
        if "stylesheet" in rel and link.get("href", "").startswith(("http://", "https://")):
            return False
    for image in parsed.images:
        if image.get("src", "").startswith(("http://", "https://")):
            return False
    return True


def executable_javascript_absent(parsed: PageParser) -> bool:
    for script in parsed.scripts:
        if script.get("src"):
            return False
        if script.get("type", "").lower() != "application/ld+json":
            return False
    return True


parser = parse_page(html)
checks["semantic_landmarks"] = (
    parser.lang == "en"
    and parser.main_count == 1
    and parser.nav_count >= 1
    and parser.headings.count("h1") == 1
)
checks["unique_ids"] = len(parser.ids) == len(set(parser.ids))
checks["skip_link"] = '<a class="skip-link" href="#main">' in html
checks["local_nav_targets"] = all(href[1:] in parser.ids for href in parser.hrefs if href.startswith("#"))
checks["no_remote_runtime_assets"] = remote_runtime_assets_absent(parser)
checks["no_javascript_required"] = executable_javascript_absent(parser)
checks["focus_visible"] = ":focus-visible" in combined_css
checks["reduced_motion"] = "prefers-reduced-motion" in combined_css
checks["license_disclosure"] = "mit" in html.lower() and "license" in README.read_text(encoding="utf-8").lower()

canonical_url = "https://kitahl.github.io/The-Gauntlet/"
checks["discovery_contract"] = (
    any("canonical" in link.get("rel", "").lower().split() and link.get("href") == canonical_url for link in parser.links)
    and any(meta.get("property") == "og:url" and meta.get("content") == canonical_url for meta in parser.meta)
    and any(meta.get("name") == "description" and len(meta.get("content", "")) >= 80 for meta in parser.meta)
    and (ROOT / "docs/robots.txt").exists()
    and (ROOT / "docs/sitemap.xml").exists()
)
checks["pages_contract"] = (ROOT / "PAGES_SETUP.md").exists() and (ROOT / "docs/.nojekyll").exists()

visual_files = [ROOT / path for path in VISUAL_PATHS]
expected_visual_srcs = {path.removeprefix("docs/") for path in VISUAL_PATHS}
actual_visual_srcs = {image.get("src", "") for image in parser.images}
checks["visual_assets_present"] = VISUAL_CSS.exists() and all(path.exists() and path.stat().st_size > 500 for path in visual_files)
checks["visual_assets_referenced"] = expected_visual_srcs <= actual_visual_srcs
checks["visual_alt_text"] = all(
    len(image.get("alt", "").strip()) >= 40
    for image in parser.images
    if image.get("src", "") in expected_visual_srcs
)
checks["visual_dimensions_declared"] = all(
    image.get("width", "").isdigit() and image.get("height", "").isdigit()
    for image in parser.images
    if image.get("src", "") in expected_visual_srcs
)
checks["no_decorative_circle_nodes"] = all("<circle" not in path.read_text(encoding="utf-8").lower() for path in visual_files)

release_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
visual_version_text = VISUAL_VERSION.read_text(encoding="utf-8")
checks["showcase_revision_separate_from_software_version"] = (
    "Showcase R17" in html and f"v{release_version}" in html and "MIT" in html
)
checks["showcase_revision_file_consistent"] = (
    "showcase-revision=17" in visual_version_text
    and "previous-showcase-revision=16" in visual_version_text
    and f"research-software-version={release_version}" in visual_version_text
)
checks["clean_visual_contract"] = all(
    forbidden not in combined_css.lower()
    for forbidden in ("linear-gradient(", "radial-gradient(", "box-shadow:")
)

skill_dirs = [
    "soul", "mathbot", "scoutbot", "novelbot", "codebot", "benchbot",
    "infinity-gauntlet", "meditate", "council-of-elders", "foil",
]
checks["source_artifacts_present"] = all((ROOT / "skills" / directory / "SKILL.md").exists() for directory in skill_dirs)
checks["skill_directories_are_spec_only"] = all(
    {path.name for path in (ROOT / "skills" / directory).iterdir()} == {"SKILL.md"}
    for directory in skill_dirs
)
checks["public_tool_catalog_complete"] = (
    html.count('class="tool-entry"') == 10
    and len(list((ROOT / "skills").glob("*/SKILL.md"))) == 10
    and parser.details_count >= 15
)

public_names = (
    "The Gauntlet", "Research Orchestrator", "Formal Reasoning", "Research Discovery",
    "Method Synthesis", "Engineering Verification", "Evaluation &amp; Benchmarking",
    "Process Assurance Framework", "Decision Preflight Protocol", "Evidence Review Panel",
    "Mirror · Adaptive Reasoning Complement",
)
checks["professional_naming"] = all(token in html for token in public_names)
checks["legacy_name_not_public"] = "Mastermind" not in html and ">FOIL<" not in html

required_commands = ("/soul", "/foil", "/mind", "/space", "/reality", "/power", "/time", "/gauntlet", "/council")
checks["activation_surface"] = all(command in html for command in required_commands)
checks["meditate_visible"] = "Decision Preflight Protocol" in html and "skills/meditate/SKILL.md" in html
checks["council_visible"] = "Evidence Review Panel" in html and "skills/council-of-elders/SKILL.md" in html

runtime_tool_files = sorted(
    path.name for path in (ROOT / "tools").glob("*.py") if path.name != "__init__.py"
)
raw_prefix = "https://raw.githubusercontent.com/Kitahl/The-Gauntlet/main/tools/"
checks["implementation_index_complete"] = (
    len(runtime_tool_files) == 40
    and "All 40 Python tool files" in html
    and all(f"tools/{name}" in html and f'{raw_prefix}{name}' in html for name in runtime_tool_files)
)
checks["skill_downloads_complete"] = all(
    f"https://raw.githubusercontent.com/Kitahl/The-Gauntlet/main/skills/{directory}/SKILL.md" in html
    for directory in skill_dirs
)
checks["repository_download_present"] = "https://github.com/Kitahl/The-Gauntlet/archive/refs/heads/main.zip" in html

checks["research_metadata_present"] = all(
    (ROOT / path).exists()
    for path in ("RESEARCH.md", "REPRODUCIBILITY.md", "ROADMAP.md", "CITATION.cff", "LICENSE", "SECURITY.md", "GOVERNANCE.md")
)
checks["research_boundary_visible"] = (
    "What remains unresolved." in html
    and "General behavioral efficacy remains open." in html
    and "Passing software and specification checks establishes implementation properties." in html
)
checks["benchmark_results_not_front_page"] = all(
    token not in html
    for token in ("94 / 94", "18 / 18", "HLE public", "ARC-AGI", "GPQA-Diamond", "BrowseComp four-way")
)
checks["source_surface"] = all(token in html for token in ("RESEARCH.md", "REPRODUCIBILITY.md", "SECURITY.md", "GOVERNANCE.md", "CITATION.cff", "ROADMAP.md"))

visual_provenance = json.loads((ROOT / "docs/visuals/visual-provenance.json").read_text(encoding="utf-8"))
checks["visual_provenance_consistent"] = (
    visual_provenance.get("showcase_revision") == 17
    and visual_provenance.get("research_software_version") == release_version
    and {entry.get("file") for entry in visual_provenance.get("visuals", [])} == set(VISUAL_PATHS)
    and all((ROOT / source).exists() for entry in visual_provenance.get("visuals", []) for source in entry.get("sources", []))
)


def browser_launch_kwargs() -> dict[str, object]:
    kwargs: dict[str, object] = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
    if Path("/usr/bin/chromium").exists():
        kwargs["executable_path"] = "/usr/bin/chromium"
    return kwargs


def target_sizes_ok(page: object) -> bool:
    sizes = page.locator(".site-nav a, .button, .download-all").evaluate_all(
        "els => els.map(el => { const r = el.getBoundingClientRect(); return [r.width, r.height]; })"
    )
    return bool(sizes) and all(width >= 24 and height >= 24 for width, height in sizes)


def structural_overflow_absent(page: object) -> bool:
    return not bool(page.evaluate(
        """() => {
          const bad = [];
          document.querySelectorAll('.tool-entry,.runtime-group,.process-graphic,.visual-card').forEach(el => {
            const r = el.getBoundingClientRect();
            el.querySelectorAll('h1,h2,h3,p,span,strong,em,code,a,text').forEach(ch => {
              const c = ch.getBoundingClientRect?.();
              if (c && (c.right > r.right + 2 || c.left < r.left - 2)) bad.push(1);
            });
          });
          return bad.length;
        }"""
    ))


def browser_source() -> str:
    source = html.replace('<link rel="stylesheet" href="styles.css" />', "")
    source = source.replace('<link rel="stylesheet" href="visuals.css" />', "")
    for relative_path in VISUAL_PATHS:
        path = ROOT / relative_path
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        src = relative_path.removeprefix("docs/")
        source = source.replace(f'src="{src}"', f'src="data:image/svg+xml;base64,{encoded}"')
    return source


render: dict[str, dict[str, object]] = {}
source = browser_source()
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(**browser_launch_kwargs())
    for name, width, height in (("desktop", 1440, 900), ("mobile", 390, 844)):
        page = browser.new_page(viewport={"width": width, "height": height})
        errors: list[str] = []
        page.on("console", lambda message, errors=errors: errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
        page.set_content(source, wait_until="load")
        page.add_style_tag(content=combined_css)
        page.wait_for_timeout(200)
        page.keyboard.press("Tab")
        focused = page.evaluate('document.activeElement && document.activeElement.getAttribute("href")')
        render[name] = {
            "horizontal_overflow": page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"),
            "keyboard_first_focus": focused,
            "console_errors": errors,
            "h1_visible": page.locator("h1").is_visible(),
            "main_visible": page.locator("main").is_visible(),
            "primary_nav_visible": page.locator(".site-nav").is_visible(),
            "target_sizes_ok": target_sizes_ok(page),
            "structural_overflow_absent": structural_overflow_absent(page),
        }
        page.screenshot(path=str(ROOT / "validation" / f"showcase-{name}.png"), full_page=True)
    browser.close()

checks["responsive_no_overflow"] = all(not result["horizontal_overflow"] for result in render.values())
checks["render_no_console_errors"] = all(not result["console_errors"] for result in render.values())
checks["render_core_visible"] = all(result["h1_visible"] and result["main_visible"] and result["primary_nav_visible"] for result in render.values())
checks["target_size_minimum"] = all(result["target_sizes_ok"] for result in render.values())
checks["structural_text_contained"] = all(result["structural_overflow_absent"] for result in render.values())
checks["keyboard_path"] = all(result["keyboard_first_focus"] == "#main" for result in render.values())

payload_bytes = HTML.stat().st_size + CSS.stat().st_size + VISUAL_CSS.stat().st_size + sum(path.stat().st_size for path in visual_files)
checks["payload_budget"] = payload_bytes < 120_000

status = "PASS" if all(checks.values()) else "FAIL"
output = {"status": status, "checks": checks, "render": render, "payload_bytes": payload_bytes, "total": len(checks), "passed": sum(checks.values())}
(ROOT / "validation/showcase-validation.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
print(json.dumps(output, indent=2))
raise SystemExit(0 if status == "PASS" else 1)
