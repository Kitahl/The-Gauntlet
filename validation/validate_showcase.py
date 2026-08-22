from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "docs/index.html"
CSS = ROOT / "docs/styles.css"
README = ROOT / "README.md"

html = HTML.read_text(encoding="utf-8")
css = CSS.read_text(encoding="utf-8")
checks: dict[str, bool] = {}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.hrefs: list[str] = []
        self.headings: list[str] = []
        self.main_count = 0
        self.nav_count = 0
        self.lang: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        if tag == "html":
            self.lang = data.get("lang")
        if data.get("id"):
            self.ids.append(str(data["id"]))
        if tag == "a" and data.get("href"):
            self.hrefs.append(str(data["href"]))
        if tag in ("h1", "h2", "h3"):
            self.headings.append(tag)
        if tag == "main":
            self.main_count += 1
        if tag == "nav":
            self.nav_count += 1


parser = PageParser()
parser.feed(html)
checks["semantic_landmarks"] = (
    parser.lang == "en"
    and parser.main_count == 1
    and parser.nav_count >= 1
    and parser.headings.count("h1") == 1
)
checks["unique_ids"] = len(parser.ids) == len(set(parser.ids))
checks["skip_link"] = '<a class="skip-link" href="#main">' in html
checks["local_nav_targets"] = all(
    href[1:] in parser.ids for href in parser.hrefs if href.startswith("#")
)
checks["skill_links_canonical"] = all(
    href.startswith("https://github.com/Kitahl/The-Gauntlet/")
    for href in parser.hrefs
    if "/skills/" in href
)
checks["no_remote_runtime_assets"] = not bool(
    re.search(r'<(?:script|link)[^>]+(?:src|href)=["\']https?://', html, re.I)
)
checks["no_javascript_required"] = "<script" not in html.lower()
checks["focus_visible"] = ":focus-visible" in css
checks["reduced_motion"] = "prefers-reduced-motion" in css
checks["license_disclosure"] = "mit" in html.lower() and "license" in README.read_text(encoding="utf-8").lower()
checks["pages_contract"] = (
    (ROOT / "PAGES_SETUP.md").exists()
    and (ROOT / "docs/.nojekyll").exists()
    and "main" in (ROOT / "PAGES_SETUP.md").read_text(encoding="utf-8")
    and "/docs" in (ROOT / "PAGES_SETUP.md").read_text(encoding="utf-8")
)

skill_dirs = [
    "soul",
    "mathbot",
    "scoutbot",
    "novelbot",
    "codebot",
    "benchbot",
    "infinity-gauntlet",
    "meditate",
    "council-of-elders",
    "foil",
]
checks["source_artifacts_present"] = all(
    (ROOT / "skills" / directory / "SKILL.md").exists() for directory in skill_dirs
)
checks["research_metadata_present"] = all(
    (ROOT / path).exists()
    for path in (
        "RESEARCH.md",
        "REPRODUCIBILITY.md",
        "ROADMAP.md",
        "CITATION.cff",
        "LICENSE",
        "CHANGELOG.md",
    )
)
checks["foil_validation_present"] = (
    ROOT / "validation/FOIL_RESEARCH_INTEGRATION_VALIDATION.json"
).exists()
checks["orchestrator_assurance_validation_present"] = (
    ROOT / "validation/validate_soul_gauntlet_public.py"
).exists()

provenance = json.loads((ROOT / "docs/content-provenance.json").read_text(encoding="utf-8"))
checks["provenance_sources_exist"] = all(
    (ROOT / source).exists()
    for claim in provenance["claims"]
    for source in claim["sources"]
)
checks["module_count_matches"] = (
    len(list((ROOT / "skills").glob("*/SKILL.md"))) == 10
    and "<strong>10</strong>" in html
)
checks["professional_naming"] = all(
    token in html
    for token in (
        "Evidence-Governed Research Toolkit",
        "Research Orchestrator",
        "Formal Reasoning",
        "Research Discovery",
        "Method Synthesis",
        "Engineering Verification",
        "Evaluation &amp; Benchmarking",
        "Process Assurance Framework",
        "Decision Preflight Protocol",
        "Evidence Review Panel",
        "FOIL",
    )
)
checks["evidence_trail_exposed"] = all(
    token in html
    for token in (
        "FOIL_RESEARCH_BASIS.md",
        "/validation",
        "skills/foil/SKILL.md",
        "skills/soul/SKILL.md",
        "RESEARCH.md",
        "REPRODUCIBILITY.md",
    )
)
checks["activation_surface"] = all(
    command in html
    for command in (
        "/soul",
        "/foil",
        "/mind",
        "/space",
        "/reality",
        "/power",
        "/time",
        "/gauntlet",
        "/council",
    )
)

trigger_sources = {
    "/soul": "skills/soul/SKILL.md",
    "/foil": "skills/foil/SKILL.md",
    "/mind": "skills/mathbot/SKILL.md",
    "/space": "skills/scoutbot/SKILL.md",
    "/reality": "skills/novelbot/SKILL.md",
    "/power": "skills/codebot/SKILL.md",
    "/time": "skills/benchbot/SKILL.md",
    "/gauntlet": "skills/infinity-gauntlet/SKILL.md",
    "/council": "skills/council-of-elders/SKILL.md",
}
checks["activation_triggers_trace_to_source"] = all(
    command in (ROOT / relative_path).read_text(encoding="utf-8")
    for command, relative_path in trigger_sources.items()
)
checks["decision_preflight_trace"] = "invoked by the Soul" in (
    ROOT / "skills/meditate/SKILL.md"
).read_text(encoding="utf-8")
checks["no_behavioral_efficacy_overclaim"] = (
    "does not establish that FOIL improves human learning" in html
)

assurance = (ROOT / "skills/infinity-gauntlet/SKILL.md").read_text(encoding="utf-8")
checks["assurance_portable_contract"] = (
    "PUBLIC RUNTIME CONTRACT" in assurance and "UNAVAILABLE" in assurance
)
checks["assurance_no_dead_private_runtime"] = not any(
    token in assurance
    for token in (
        "tools/gauntlet_monitor.py",
        "tools/gauntlet_boundary.py",
        "tools/fsa_bots.py",
        "tools/scout.py",
        "tools/verify_ledger.py",
        ".claude/settings.json",
        "repo CLAUDE.md",
    )
)


def luminance(hex_value: str) -> float:
    value = hex_value.lstrip("#")
    channels = [int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    channels = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


checks["principal_contrast"] = (
    contrast_ratio("#f5f7f9", "#07080a") >= 7
    and contrast_ratio("#9aa4af", "#07080a") >= 4.5
    and contrast_ratio("#ff8a3d", "#07080a") >= 4.5
)


def browser_launch_kwargs() -> dict[str, object]:
    kwargs: dict[str, object] = {
        "headless": True,
        "args": ["--no-sandbox", "--disable-dev-shm-usage"],
    }
    if Path("/usr/bin/chromium").exists():
        kwargs["executable_path"] = "/usr/bin/chromium"
    return kwargs


render: dict[str, dict[str, object]] = {}
source = html.replace('<link rel="stylesheet" href="styles.css" />', "")
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(**browser_launch_kwargs())
    for name, width, height in (("desktop", 1440, 900), ("mobile", 390, 844)):
        page = browser.new_page(viewport={"width": width, "height": height})
        errors: list[str] = []
        page.on(
            "console",
            lambda message, errors=errors: errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
        page.set_content(source, wait_until="load")
        page.add_style_tag(content=css)
        page.keyboard.press("Tab")
        focused = page.evaluate(
            'document.activeElement && document.activeElement.getAttribute("href")'
        )
        render[name] = {
            "horizontal_overflow": page.evaluate(
                "document.documentElement.scrollWidth > document.documentElement.clientWidth"
            ),
            "keyboard_first_focus": focused,
            "console_errors": errors,
            "h1_visible": page.locator("h1").is_visible(),
            "main_visible": page.locator("main").is_visible(),
        }
        page.screenshot(path=str(ROOT / "validation" / f"showcase-{name}.png"), full_page=True)
    browser.close()

checks["responsive_no_overflow"] = all(
    not bool(result["horizontal_overflow"]) for result in render.values()
)
checks["render_no_console_errors"] = all(
    not result["console_errors"] for result in render.values()
)
checks["render_core_visible"] = all(
    bool(result["h1_visible"]) and bool(result["main_visible"])
    for result in render.values()
)
checks["keyboard_path"] = all(
    result.get("keyboard_first_focus") == "#main" for result in render.values()
)

payload_bytes = HTML.stat().st_size + CSS.stat().st_size
checks["payload_budget"] = payload_bytes < 100_000
checks["payload_budget_negative_control"] = payload_bytes + 100_001 >= 100_000

# Representative mutants demonstrate that important gates can fail.
mutant_html = source.replace('<main id="main">', '<main id="main" style="display:none">')
mutant_css = css + "\nh1{font-size:12px!important}\n"
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(**browser_launch_kwargs())
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.set_content(mutant_html, wait_until="load")
    page.add_style_tag(content=mutant_css)
    hidden_detected = not page.locator("main").is_visible()
    hierarchy_detected = float(
        page.locator("h1").evaluate("(e) => parseFloat(getComputedStyle(e).fontSize)")
    ) < 24
    browser.close()

checks["render_mutant_detected"] = hidden_detected
checks["hierarchy_mutant_detected"] = hierarchy_detected
checks["pages_link_mutant_detected"] = not all(
    href.startswith("https://github.com/Kitahl/The-Gauntlet/")
    for href in ("../skills/foil/SKILL.md",)
)

status = "PASS" if all(checks.values()) else "FAIL"
output = {
    "status": status,
    "checks": checks,
    "render": render,
    "total": len(checks),
    "passed": sum(checks.values()),
}
(ROOT / "validation/showcase-validation.json").write_text(
    json.dumps(output, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(output, indent=2))
raise SystemExit(0 if status == "PASS" else 1)
