from __future__ import annotations

import base64
import json
from html.parser import HTMLParser
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "docs/index.html"
CSS = ROOT / "docs/styles.css"
VISUAL_CSS = ROOT / "docs/visuals.css"
VISUAL_VERSION = ROOT / "docs/visuals/VERSION"
VISUAL_PATHS = (
    "docs/visuals/gauntlet-hero.svg",
    "docs/visuals/gauntlet-system-map.svg",
    "docs/visuals/foil-diagnostic-loop.svg",
    "docs/visuals/gem-mind.svg",
    "docs/visuals/gem-space.svg",
    "docs/visuals/gem-reality.svg",
    "docs/visuals/gem-power.svg",
    "docs/visuals/gem-time.svg",
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
        self.links: list[dict[str, str]] = []
        self.scripts: list[dict[str, str]] = []
        self.meta: list[dict[str, str]] = []
        self.images: list[dict[str, str]] = []
        self.h1_count = 0
        self.main_count = 0
        self.nav_count = 0
        self.lang: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key: value or "" for key, value in attrs}
        if tag == "html":
            self.lang = data.get("lang")
        if data.get("id"):
            self.ids.append(data["id"])
        if tag == "a" and data.get("href"):
            self.hrefs.append(data["href"])
        elif tag == "link":
            self.links.append(data)
        elif tag == "script":
            self.scripts.append(data)
        elif tag == "meta":
            self.meta.append(data)
        elif tag == "img":
            self.images.append(data)
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "main":
            self.main_count += 1
        elif tag == "nav":
            self.nav_count += 1


def parse_page(document: str) -> PageParser:
    parsed = PageParser()
    parsed.feed(document)
    return parsed


def no_remote_assets(parsed: PageParser) -> bool:
    if any(script.get("src", "").startswith(("http://", "https://")) for script in parsed.scripts):
        return False
    for link in parsed.links:
        if "stylesheet" in link.get("rel", "").lower().split() and link.get("href", "").startswith(("http://", "https://")):
            return False
    return not any(image.get("src", "").startswith(("http://", "https://")) for image in parsed.images)


def no_executable_js(parsed: PageParser) -> bool:
    return all(not script.get("src") and script.get("type", "").lower() == "application/ld+json" for script in parsed.scripts)


parser = parse_page(html)
checks["semantic_landmarks"] = parser.lang == "en" and parser.main_count == 1 and parser.nav_count >= 1 and parser.h1_count == 1
checks["unique_ids"] = len(parser.ids) == len(set(parser.ids))
checks["skip_link"] = '<a class="skip-link" href="#main">' in html
checks["local_nav_targets"] = all(href[1:] in parser.ids for href in parser.hrefs if href.startswith("#"))
checks["no_remote_runtime_assets"] = no_remote_assets(parser)
checks["no_javascript_required"] = no_executable_js(parser)
checks["focus_visible"] = ":focus-visible" in combined_css
checks["reduced_motion"] = "prefers-reduced-motion" in combined_css
checks["pages_contract"] = (ROOT / "PAGES_SETUP.md").exists() and (ROOT / "docs/.nojekyll").exists()

canonical = "https://kitahl.github.io/The-Gauntlet/"
checks["discovery_contract"] = (
    any("canonical" in link.get("rel", "").lower().split() and link.get("href") == canonical for link in parser.links)
    and any(meta.get("property") == "og:url" and meta.get("content") == canonical for meta in parser.meta)
    and any(meta.get("name") == "description" and len(meta.get("content", "")) >= 80 for meta in parser.meta)
    and (ROOT / "docs/robots.txt").exists()
    and (ROOT / "docs/sitemap.xml").exists()
)

visual_files = [ROOT / path for path in VISUAL_PATHS]
expected_srcs = {path.removeprefix("docs/") for path in VISUAL_PATHS}
actual_srcs = {image.get("src", "") for image in parser.images}
checks["visual_assets_present"] = all(path.exists() and path.stat().st_size > 500 for path in visual_files)
checks["visual_assets_referenced"] = expected_srcs <= actual_srcs
checks["visual_alt_and_dimensions"] = all(
    len(image.get("alt", "").strip()) >= 40
    and image.get("width", "").isdigit()
    and image.get("height", "").isdigit()
    for image in parser.images
    if image.get("src", "") in expected_srcs
)
checks["no_decorative_circle_nodes"] = "<circle" not in html.lower() and all("<circle" not in path.read_text(encoding="utf-8").lower() for path in visual_files)
checks["clean_visual_contract"] = all(token not in combined_css.lower() for token in ("linear-gradient(", "radial-gradient(", "box-shadow:"))

release_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
version_text = VISUAL_VERSION.read_text(encoding="utf-8")
checks["showcase_revision"] = (
    "Showcase R18" in html
    and "showcase-revision=18" in version_text
    and "previous-showcase-revision=17" in version_text
    and f"research-software-version={release_version}" in version_text
)

skill_dirs = ["soul", "mathbot", "scoutbot", "novelbot", "codebot", "benchbot", "infinity-gauntlet", "meditate", "council-of-elders", "foil"]
checks["skill_layout"] = all(
    (ROOT / "skills" / directory / "SKILL.md").exists()
    and {path.name for path in (ROOT / "skills" / directory).iterdir()} == {"SKILL.md"}
    for directory in skill_dirs
)
checks["professional_portfolio_contract"] = all(
    token in html
    for token in (
        "10 tools I built for research, engineering, verification, and review.",
        "01 / WHAT I BUILT",
        "02 / PROFESSIONAL WORKFLOWS",
        "03 / THE FIVE GEMS",
        "04 / HOW THE SYSTEM WORKS",
        "05 / COMPLETE TOOLKIT",
        "06 / SOURCE &amp; DOCUMENTATION",
    )
)
checks["professional_workflows"] = html.count('class="workflow-row"') == 5 and "END-TO-END EXAMPLE" in html
checks["public_tool_catalog"] = html.count('class="tool-entry"') == 10 and html.count("<h3>Professional use</h3>") == 10 and html.count("<h3>How it works</h3>") == 10
checks["research_report_language_absent"] = all(token not in html.lower() for token in ("what remains unresolved", "current question", "next study", "success condition"))
checks["legacy_name_not_public"] = "mastermind" not in html.lower() and ">FOIL<" not in html
checks["benchmark_results_not_front_page"] = all(token not in html for token in ("94 / 94", "18 / 18", "HLE public", "ARC-AGI", "GPQA-Diamond", "BrowseComp four-way"))
checks["activation_surface"] = all(command in html for command in ("/soul", "/foil", "/mind", "/space", "/reality", "/power", "/time", "/gauntlet", "/council"))
checks["control_tools_visible"] = "Decision Preflight Protocol" in html and "Evidence Review Panel" in html and "Mirror · Adaptive Reasoning Complement" in html
checks["implementation_directory_exposed"] = len([p for p in (ROOT / "tools").glob("*.py") if p.name != "__init__.py"]) == 40 and "https://github.com/Kitahl/The-Gauntlet/tree/main/tools" in html
checks["skill_downloads"] = all(f"https://raw.githubusercontent.com/Kitahl/The-Gauntlet/main/skills/{directory}/SKILL.md" in html for directory in skill_dirs)
checks["repository_download"] = "https://github.com/Kitahl/The-Gauntlet/archive/refs/heads/main.zip" in html
checks["source_surface"] = all(token in html for token in ("RESEARCH.md", "REPRODUCIBILITY.md", "SECURITY.md", "GOVERNANCE.md", "CITATION.cff", "docs/ARCHITECTURE.md"))

provenance = json.loads((ROOT / "docs/visuals/visual-provenance.json").read_text(encoding="utf-8"))
checks["visual_provenance"] = (
    provenance.get("showcase_revision") == 18
    and provenance.get("research_software_version") == release_version
    and {item.get("file") for item in provenance.get("visuals", [])} == set(VISUAL_PATHS)
    and all((ROOT / source).exists() for item in provenance.get("visuals", []) for source in item.get("sources", []))
)


def browser_kwargs() -> dict[str, object]:
    kwargs: dict[str, object] = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
    if Path("/usr/bin/chromium").exists():
        kwargs["executable_path"] = "/usr/bin/chromium"
    return kwargs


def source_with_visuals() -> str:
    source = html.replace('<link rel="stylesheet" href="styles.css" />', "").replace('<link rel="stylesheet" href="visuals.css" />', "")
    for relative in VISUAL_PATHS:
        encoded = base64.b64encode((ROOT / relative).read_bytes()).decode("ascii")
        source = source.replace(f'src="{relative.removeprefix("docs/")}"', f'src="data:image/svg+xml;base64,{encoded}"')
    return source


def targets_ok(page: object) -> bool:
    sizes = page.locator(".site-nav a, .button, .download-all").evaluate_all("els => els.map(el => {const r=el.getBoundingClientRect(); return [r.width,r.height]})")
    return bool(sizes) and all(width >= 24 and height >= 24 for width, height in sizes)


def contained(page: object) -> bool:
    return not bool(page.evaluate("""() => {let n=0; document.querySelectorAll('.inventory-row,.workflow-row,.gem,.tool-entry,.visual-card,.case-study').forEach(el=>{const r=el.getBoundingClientRect(); el.querySelectorAll('h1,h2,h3,p,span,strong,em,code,a,dt,dd').forEach(ch=>{const c=ch.getBoundingClientRect(); if(c.width && (c.right>r.right+2 || c.left<r.left-2)) n++})}); return n}"""))


render: dict[str, dict[str, object]] = {}
source = source_with_visuals()
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(**browser_kwargs())
    for name, width, height in (("desktop", 1440, 900), ("mobile", 390, 844)):
        page = browser.new_page(viewport={"width": width, "height": height})
        errors: list[str] = []
        page.on("console", lambda message, errors=errors: errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
        page.set_content(source, wait_until="load")
        page.add_style_tag(content=combined_css)
        page.wait_for_timeout(200)
        page.keyboard.press("Tab")
        render[name] = {
            "horizontal_overflow": page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"),
            "errors": errors,
            "core_visible": page.locator("h1").is_visible() and page.locator("main").is_visible() and page.locator(".site-nav").is_visible(),
            "targets_ok": targets_ok(page),
            "contained": contained(page),
            "first_focus": page.evaluate('document.activeElement && document.activeElement.getAttribute("href")'),
        }
        page.screenshot(path=str(ROOT / "validation" / f"showcase-{name}.png"), full_page=True)
    browser.close()

checks["responsive_no_overflow"] = all(not item["horizontal_overflow"] for item in render.values())
checks["render_no_console_errors"] = all(not item["errors"] for item in render.values())
checks["render_core_visible"] = all(item["core_visible"] for item in render.values())
checks["target_size_minimum"] = all(item["targets_ok"] for item in render.values())
checks["structural_text_contained"] = all(item["contained"] for item in render.values())
checks["keyboard_path"] = all(item["first_focus"] == "#main" for item in render.values())

payload_bytes = HTML.stat().st_size + CSS.stat().st_size + VISUAL_CSS.stat().st_size + sum(path.stat().st_size for path in visual_files)
checks["payload_budget"] = payload_bytes < 130_000
status = "PASS" if all(checks.values()) else "FAIL"
output = {"status": status, "checks": checks, "render": render, "payload_bytes": payload_bytes, "total": len(checks), "passed": sum(checks.values())}
(ROOT / "validation/showcase-validation.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
print(json.dumps(output, indent=2))
raise SystemExit(0 if status == "PASS" else 1)
