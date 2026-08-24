from __future__ import annotations

import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "docs/index.html"
CSS = ROOT / "docs/styles.css"
JS = ROOT / "docs/system-field.js"
VISUAL_VERSION = ROOT / "docs/visuals/VERSION"
PROVENANCE = ROOT / "docs/visuals/visual-provenance.json"

html = HTML.read_text(encoding="utf-8")
css = CSS.read_text(encoding="utf-8")
js = JS.read_text(encoding="utf-8")
checks: dict[str, bool] = {}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.hrefs: list[str] = []
        self.links: list[dict[str, str]] = []
        self.scripts: list[dict[str, str]] = []
        self.meta: list[dict[str, str]] = []
        self.details = 0
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
        elif tag == "details" and "tool-entry" in data.get("class", "").split():
            self.details += 1
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "main":
            self.main_count += 1
        elif tag == "nav":
            self.nav_count += 1


parser = PageParser()
parser.feed(html)
checks["semantic_landmarks"] = parser.lang == "en" and parser.main_count == 1 and parser.nav_count >= 1 and parser.h1_count == 1
checks["unique_ids"] = len(parser.ids) == len(set(parser.ids))
checks["skip_link"] = '<a class="skip-link" href="#main">' in html
checks["local_nav_targets"] = all(href[1:] in parser.ids for href in parser.hrefs if href.startswith("#"))
checks["local_runtime_assets"] = (
    any("stylesheet" in link.get("rel", "").lower().split() and link.get("href") == "styles.css" for link in parser.links)
    and len(parser.scripts) == 1
    and parser.scripts[0].get("src") == "system-field.js"
    and not any("stylesheet" in link.get("rel", "").lower().split() and link.get("href", "").startswith(("http://", "https://")) for link in parser.links)
    and not any(script.get("src", "").startswith(("http://", "https://")) for script in parser.scripts)
)
checks["focus_visible"] = ":focus-visible" in css
checks["reduced_motion"] = "prefers-reduced-motion" in css and "prefers-reduced-motion" in js
checks["pages_contract"] = (ROOT / "PAGES_SETUP.md").exists() and (ROOT / "docs/.nojekyll").exists()

canonical = "https://kitahl.github.io/The-Gauntlet/"
checks["discovery_contract"] = (
    any("canonical" in link.get("rel", "").lower().split() and link.get("href") == canonical for link in parser.links)
    and any(meta.get("property") == "og:url" and meta.get("content") == canonical for meta in parser.meta)
    and any(meta.get("name") == "description" and len(meta.get("content", "")) >= 80 for meta in parser.meta)
    and (ROOT / "docs/robots.txt").exists()
    and (ROOT / "docs/sitemap.xml").exists()
)

release_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
version_text = VISUAL_VERSION.read_text(encoding="utf-8")
checks["showcase_revision"] = (
    "Showcase R19" in html
    and "showcase-revision=19" in version_text
    and "previous-showcase-revision=18" in version_text
    and f"research-software-version={release_version}" in version_text
)

scene_names = ("hero", "overview", "workflow", "gems", "mind", "space", "reality", "power", "time", "system", "quiet")
checks["semantic_system_field"] = (
    'id="system-field-canvas"' in html
    and all(f'data-scene="{scene}"' in html for scene in scene_names)
    and all(token in js for token in ("gemGeometry", "drawMind", "drawSpace", "drawReality", "drawPower", "drawTime", "drawSystem", "IntersectionObserver"))
    and "THREE." not in js
    and "cdnjs" not in js
    and "https://" not in js
)
checks["five_gem_scenes"] = html.count('class="gem-scene scene-section"') == 5
checks["professional_workflows"] = html.count("<article><div><span>") == 5
checks["public_tool_catalog"] = parser.details == 10 and html.count("<h3>Professional use</h3>") == 10 and html.count("<h3>How it works</h3>") == 10
checks["research_report_language_absent"] = all(token not in html.lower() for token in ("what remains unresolved", "current question", "next study", "success condition"))
checks["legacy_name_not_public"] = "mastermind" not in html.lower() and ">FOIL<" not in html
checks["benchmark_results_not_front_page"] = all(token not in html for token in ("94 / 94", "18 / 18", "HLE public", "ARC-AGI", "GPQA-Diamond", "BrowseComp four-way"))
checks["activation_surface"] = all(command in html for command in ("/soul", "/foil", "/mind", "/space", "/reality", "/power", "/time", "/gauntlet", "/council"))
checks["control_tools_visible"] = all(token in html for token in ("Soul · Research Orchestrator", "Mirror · Adaptive Reasoning Complement", "Gauntlet · Process Assurance", "Meditate · Decision Preflight", "Council · Evidence Review Panel"))
checks["implementation_directory_exposed"] = len([p for p in (ROOT / "tools").glob("*.py") if p.name != "__init__.py"]) == 40 and "https://github.com/Kitahl/The-Gauntlet/tree/main/tools" in html

skill_dirs = ["soul", "mathbot", "scoutbot", "novelbot", "codebot", "benchbot", "infinity-gauntlet", "meditate", "council-of-elders", "foil"]
checks["skill_downloads"] = all(f"https://raw.githubusercontent.com/Kitahl/The-Gauntlet/main/skills/{directory}/SKILL.md" in html for directory in skill_dirs)
checks["repository_download"] = "https://github.com/Kitahl/The-Gauntlet/archive/refs/heads/main.zip" in html
checks["source_surface"] = all(token in html for token in ("RESEARCH.md", "REPRODUCIBILITY.md", "SECURITY.md", "GOVERNANCE.md", "CITATION.cff", "docs/ARCHITECTURE.md"))

provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
checks["visual_provenance"] = (
    provenance.get("showcase_revision") == 19
    and provenance.get("research_software_version") == release_version
    and len(provenance.get("visuals", [])) == 1
    and provenance["visuals"][0].get("file") == "docs/system-field.js"
    and all((ROOT / source).exists() for source in provenance["visuals"][0].get("sources", []))
)

node = shutil.which("node")
if node:
    syntax = subprocess.run([node, "--check", str(JS)], capture_output=True, text=True, timeout=20)
    checks["javascript_syntax"] = syntax.returncode == 0
else:
    checks["javascript_syntax"] = True


def browser_kwargs() -> dict[str, object]:
    kwargs: dict[str, object] = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
    if Path("/usr/bin/chromium").exists():
        kwargs["executable_path"] = "/usr/bin/chromium"
    return kwargs


def render_source() -> str:
    return html.replace('<link rel="stylesheet" href="styles.css" />', "").replace('<script src="system-field.js" defer></script>', "")


def targets_ok(page: object) -> bool:
    sizes = page.locator(".site-nav a, .button, .download-all").evaluate_all("els => els.map(el => {const r=el.getBoundingClientRect(); return [r.width,r.height]})")
    return bool(sizes) and all(width >= 24 and height >= 24 for width, height in sizes)


def contained(page: object) -> bool:
    return not bool(page.evaluate("""() => {let n=0; document.querySelectorAll('.hero-copy,.inventory-row,.workflow-list article,.gem-copy,.tool-entry,.source-index a,.system-line').forEach(el=>{const r=el.getBoundingClientRect(); el.querySelectorAll('h1,h2,h3,p,span,strong,code,a,dt,dd').forEach(ch=>{const c=ch.getBoundingClientRect(); if(c.width && (c.right>innerWidth+2 || c.left<-2 || c.right>r.right+3 || c.left<r.left-3)) n++})}); return n}"""))


def scene_at(page: object, selector: str, expected: str) -> bool:
    page.locator(selector).evaluate("el => el.scrollIntoView({block:'center'})")
    page.wait_for_timeout(850)
    return page.evaluate("document.body.dataset.scene") == expected


render: dict[str, dict[str, object]] = {}
source = render_source()
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(**browser_kwargs())
    for name, width, height in (("desktop", 1440, 900), ("mobile", 390, 844)):
        page = browser.new_page(viewport={"width": width, "height": height})
        errors: list[str] = []
        page.on("console", lambda message, errors=errors: errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
        page.set_content(source, wait_until="load")
        page.add_style_tag(content=css)
        page.add_script_tag(content=js)
        page.wait_for_timeout(350)
        page.keyboard.press("Tab")
        first_focus = page.evaluate('document.activeElement && document.activeElement.getAttribute("href")')
        hero_scene = page.evaluate("document.body.dataset.scene") == "hero"
        scene_checks = []
        for selector, expected in (("#workflows", "workflow"), ("#mind", "mind"), ("#space", "space"), ("#reality", "reality"), ("#power", "power"), ("#time", "time"), ("#system", "system"), ("#tools", "quiet")):
            scene_checks.append(scene_at(page, selector, expected))
        render[name] = {
            "horizontal_overflow": page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"),
            "errors": errors,
            "core_visible": page.locator("h1").count() == 1 and page.locator("main").count() == 1 and page.locator("#system-field-canvas").count() == 1,
            "targets_ok": targets_ok(page),
            "contained": contained(page),
            "first_focus": first_focus,
            "scene_routing": hero_scene and all(scene_checks),
        }
        page.screenshot(path=str(ROOT / "validation" / f"showcase-{name}.png"), full_page=True)
    browser.close()

checks["responsive_no_overflow"] = all(not item["horizontal_overflow"] for item in render.values())
checks["render_no_console_errors"] = all(not item["errors"] for item in render.values())
checks["render_core_visible"] = all(item["core_visible"] for item in render.values())
checks["target_size_minimum"] = all(item["targets_ok"] for item in render.values())
checks["structural_text_contained"] = all(item["contained"] for item in render.values())
checks["keyboard_path"] = all(item["first_focus"] == "#main" for item in render.values())
checks["scene_routing"] = all(item["scene_routing"] for item in render.values())

payload_bytes = HTML.stat().st_size + CSS.stat().st_size + JS.stat().st_size
checks["payload_budget"] = payload_bytes < 90_000
status = "PASS" if all(checks.values()) else "FAIL"
output = {"status": status, "checks": checks, "render": render, "payload_bytes": payload_bytes, "total": len(checks), "passed": sum(checks.values())}
(ROOT / "validation/showcase-validation.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
print(json.dumps(output, indent=2))
raise SystemExit(0 if status == "PASS" else 1)
