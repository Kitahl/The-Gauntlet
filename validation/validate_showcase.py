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
VISUAL_PATHS = (
    "docs/visuals/gauntlet-system-map.svg",
    "docs/visuals/foil-diagnostic-loop.svg",
    "docs/visuals/benchmark-evidence.svg",
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
        self.lang: str | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
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


def parse_page(document: str) -> PageParser:
    parsed = PageParser()
    parsed.feed(document)
    return parsed


def remote_runtime_assets_absent(parsed: PageParser) -> bool:
    for script in parsed.scripts:
        src = script.get("src", "")
        if src.startswith(("http://", "https://")):
            return False
    for link in parsed.links:
        rel = set(link.get("rel", "").lower().split())
        href = link.get("href", "")
        if "stylesheet" in rel and href.startswith(("http://", "https://")):
            return False
    for image in parsed.images:
        src = image.get("src", "")
        if src.startswith(("http://", "https://")):
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
checks["local_nav_targets"] = all(
    href[1:] in parser.ids for href in parser.hrefs if href.startswith("#")
)
checks["skill_links_canonical"] = all(
    href.startswith("https://github.com/Kitahl/The-Gauntlet/")
    for href in parser.hrefs
    if "/skills/" in href
)
checks["no_remote_runtime_assets"] = remote_runtime_assets_absent(parser)
checks["no_javascript_required"] = executable_javascript_absent(parser)
checks["focus_visible"] = ":focus-visible" in combined_css
checks["reduced_motion"] = "prefers-reduced-motion" in combined_css
checks["license_disclosure"] = (
    "mit" in html.lower() and "license" in README.read_text(encoding="utf-8").lower()
)
checks["pages_contract"] = (
    (ROOT / "PAGES_SETUP.md").exists()
    and (ROOT / "docs/.nojekyll").exists()
    and "main" in (ROOT / "PAGES_SETUP.md").read_text(encoding="utf-8")
    and "/docs" in (ROOT / "PAGES_SETUP.md").read_text(encoding="utf-8")
)

canonical_url = "https://kitahl.github.io/The-Gauntlet/"
canonical_link = any(
    "canonical" in link.get("rel", "").lower().split()
    and link.get("href") == canonical_url
    for link in parser.links
)
og_url = any(
    meta.get("property") == "og:url" and meta.get("content") == canonical_url
    for meta in parser.meta
)
description_present = any(
    meta.get("name") == "description" and len(meta.get("content", "")) >= 80
    for meta in parser.meta
)
robots_path = ROOT / "docs/robots.txt"
sitemap_path = ROOT / "docs/sitemap.xml"
robots_text = robots_path.read_text(encoding="utf-8") if robots_path.exists() else ""
sitemap_text = sitemap_path.read_text(encoding="utf-8") if sitemap_path.exists() else ""
checks["discovery_contract"] = (
    canonical_link
    and og_url
    and description_present
    and robots_path.exists()
    and sitemap_path.exists()
    and "Sitemap: https://kitahl.github.io/The-Gauntlet/sitemap.xml" in robots_text
    and f"<loc>{canonical_url}</loc>" in sitemap_text
)

visual_files = [ROOT / path for path in VISUAL_PATHS]
expected_visual_srcs = {path.removeprefix("docs/") for path in VISUAL_PATHS}
actual_visual_srcs = {image.get("src", "") for image in parser.images}
checks["visual_assets_present"] = VISUAL_CSS.exists() and all(
    path.exists() and path.stat().st_size > 500 for path in visual_files
)
checks["visual_assets_referenced"] = expected_visual_srcs <= actual_visual_srcs
checks["visual_alt_text"] = all(
    image.get("alt", "").strip() and len(image.get("alt", "").strip()) >= 40
    for image in parser.images
    if image.get("src", "") in expected_visual_srcs
)
checks["visual_dimensions_declared"] = all(
    image.get("width", "").isdigit() and image.get("height", "").isdigit()
    for image in parser.images
    if image.get("src", "") in expected_visual_srcs
)
checks["showcase_revision_separate_from_software_version"] = (
    "SHOWCASE R13" in html
    and "Research software" in html
    and "0.4.0" in html
    and "Showcase revision" in html
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
    (ROOT / "skills" / directory / "SKILL.md").exists()
    for directory in skill_dirs
)
checks["skill_directories_are_spec_only"] = all(
    {path.name for path in (ROOT / "skills" / directory).iterdir()} == {"SKILL.md"}
    for directory in skill_dirs
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
        "SECURITY.md",
        "GOVERNANCE.md",
        "CONTRIBUTING.md",
    )
)
checks["foil_validation_present"] = (
    ROOT / "validation/FOIL_RESEARCH_INTEGRATION_VALIDATION.json"
).exists()
checks["orchestrator_assurance_validation_present"] = (
    ROOT / "validation/validate_soul_gauntlet_public.py"
).exists()

provenance = json.loads(
    (ROOT / "docs/content-provenance.json").read_text(encoding="utf-8")
)
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
        "The Gauntlet",
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
checks["enterprise_trust_surface"] = all(
    token in html
    for token in (
        "SECURITY.md",
        "GOVERNANCE.md",
        "CONTRIBUTING.md",
        "CITATION.cff",
        "CHANGELOG.md",
        "ROADMAP.md",
    )
)
checks["reproducibility_surface"] = all(
    token in html
    for token in (
        "python validation/validate_soul_gauntlet_public.py",
        "python validation/validate_showcase.py",
        "python -m compileall -q validation",
        "REPRODUCIBILITY.md",
    )
)

citation_text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
checks["release_identity_consistent"] = all(
    token in citation_text
    for token in (
        'title: "Evidence-Governed Research Toolkit"',
        "version: 0.4.0",
        "license: MIT",
    )
) and all(token in html for token in ("v0.4.0", "MIT"))

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

preflight = (ROOT / "skills/meditate/SKILL.md").read_text(encoding="utf-8")
checks["decision_preflight_trace"] = (
    "Decision Preflight Protocol" in preflight
    and "Orchestrator-invoked" in preflight
    and "STILL → GROUND → ORIENT → WEIGH → RELEASE" in preflight
)

lower_html = html.lower()
checks["no_behavioral_efficacy_overclaim"] = (
    "behavioral efficacy remains a research question" in lower_html
    and "not official leaderboard submissions" in lower_html
    and "null result" in lower_html
    and "do not establish general efficacy" in lower_html
)

assurance = (ROOT / "skills/infinity-gauntlet/SKILL.md").read_text(encoding="utf-8")
required_runtime_paths = (
    ".claude/settings.json",
    ".gauntlet.json",
    "tools/gauntlet_boundary.py",
    "tools/gauntlet_monitor.py",
    "tools/gauntlet_hook.py",
    "tools/verify_ledger.py",
    "docs/RUNTIME_SETUP.md",
)
checks["assurance_portable_contract"] = (
    "## Runtime contract" in assurance
    and "UNAVAILABLE" in assurance
    and "no machine-specific path is assumed" in assurance
    and all((ROOT / path).exists() for path in required_runtime_paths)
    and all(
        path in assurance or path == "docs/RUNTIME_SETUP.md"
        for path in required_runtime_paths
    )
)
checks["assurance_no_machine_specific_runtime"] = not (
    re.search(r"[A-Za-z]:\\Users\\[^\\]+\\", assurance)
    or re.search(r"/Users/[^/]+/", assurance)
)
runtime_config = json.loads((ROOT / ".gauntlet.json").read_text(encoding="utf-8"))
state_dir = str(runtime_config.get("state_dir", "")).strip().rstrip("/")
gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
checks["runtime_state_is_not_git_metadata"] = (
    state_dir.startswith(".egrt/")
    and not state_dir.startswith(".git/")
    and ".egrt/" in gitignore
    and "state lives under the configured project runtime directory, not `.git/`"
    in assurance
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
    lighter, darker = sorted(
        (luminance(first), luminance(second)),
        reverse=True,
    )
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


def target_sizes_ok(page: object) -> bool:
    sizes = page.locator(".site-nav a, .button").evaluate_all(
        """
        els => els.map(el => {
          const r = el.getBoundingClientRect();
          return [r.width, r.height];
        })
        """
    )
    return bool(sizes) and all(width >= 24 and height >= 24 for width, height in sizes)


def visual_sizes_ok(page: object) -> bool:
    sizes = page.locator(".visual-card img").evaluate_all(
        """
        els => els.map(el => {
          const r = el.getBoundingClientRect();
          return [r.width, r.height, el.naturalWidth, el.naturalHeight];
        })
        """
    )
    return len(sizes) == len(VISUAL_PATHS) and all(
        width >= 300
        and height >= 150
        and natural_width > 0
        and natural_height > 0
        for width, height, natural_width, natural_height in sizes
    )


def browser_source() -> str:
    source = html.replace('<link rel="stylesheet" href="styles.css" />', "")
    source = source.replace('<link rel="stylesheet" href="visuals.css" />', "")
    for relative_path in VISUAL_PATHS:
        path = ROOT / relative_path
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        src = relative_path.removeprefix("docs/")
        source = source.replace(
            f'src="{src}"',
            f'src="data:image/svg+xml;base64,{encoded}"',
        )
    return source


render: dict[str, dict[str, object]] = {}
source = browser_source()
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
        page.add_style_tag(content=combined_css)
        page.locator(".visual-card img").evaluate_all(
            "els => els.forEach(el => { el.loading = 'eager'; })"
        )
        page.wait_for_timeout(250)
        page.keyboard.press("Tab")
        focused = page.evaluate(
            'document.activeElement && document.activeElement.getAttribute("href")'
        )
        render[name] = {
            "horizontal_overflow": page.evaluate(
                "document.documentElement.scrollWidth > "
                "document.documentElement.clientWidth"
            ),
            "keyboard_first_focus": focused,
            "console_errors": errors,
            "h1_visible": page.locator("h1").is_visible(),
            "main_visible": page.locator("main").is_visible(),
            "primary_nav_visible": page.locator(".site-nav").is_visible(),
            "target_sizes_ok": target_sizes_ok(page),
            "visuals_visible": visual_sizes_ok(page),
        }
        page.screenshot(
            path=str(ROOT / "validation" / f"showcase-{name}.png"),
            full_page=True,
        )
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
checks["primary_nav_visible_all_viewports"] = all(
    bool(result["primary_nav_visible"]) for result in render.values()
)
checks["target_size_minimum"] = all(
    bool(result["target_sizes_ok"]) for result in render.values()
)
checks["mechanism_visuals_rendered"] = all(
    bool(result["visuals_visible"]) for result in render.values()
)
checks["keyboard_path"] = all(
    result.get("keyboard_first_focus") == "#main" for result in render.values()
)

payload_bytes = HTML.stat().st_size + CSS.stat().st_size + VISUAL_CSS.stat().st_size
payload_bytes += sum(path.stat().st_size for path in visual_files)
checks["payload_budget"] = payload_bytes < 100_000
checks["payload_budget_negative_control"] = payload_bytes + 100_001 >= 100_000

mutant_html = source.replace(
    '<main id="main">',
    '<main id="main" style="display:none">',
)
mutant_css = combined_css + "\nh1{font-size:12px!important}\n"
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(**browser_launch_kwargs())
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.set_content(mutant_html, wait_until="load")
    page.add_style_tag(content=mutant_css)
    hidden_detected = not page.locator("main").is_visible()
    hierarchy_detected = float(
        page.locator("h1").evaluate(
            "(e) => parseFloat(getComputedStyle(e).fontSize)"
        )
    ) < 24

    target_page = browser.new_page(viewport={"width": 390, "height": 844})
    target_page.set_content(source, wait_until="load")
    target_page.add_style_tag(
        content=combined_css
        + "\n.button,.site-nav a{min-height:10px!important;height:10px!important;}"
    )
    target_mutant_detected = not target_sizes_ok(target_page)
    browser.close()

remote_asset_mutant = html.replace(
    "</head>",
    '<link rel="stylesheet" href="https://example.com/remote.css" /></head>',
)
visual_reference_mutant = html.replace(
    'src="visuals/gauntlet-system-map.svg"',
    'src="visuals/missing-system-map.svg"',
)
visual_mutant_parser = parse_page(visual_reference_mutant)
visual_mutant_srcs = {image.get("src", "") for image in visual_mutant_parser.images}
checks["render_mutant_detected"] = hidden_detected
checks["hierarchy_mutant_detected"] = hierarchy_detected
checks["target_size_mutant_detected"] = target_mutant_detected
checks["remote_asset_mutant_detected"] = not remote_runtime_assets_absent(
    parse_page(remote_asset_mutant)
)
checks["visual_reference_mutant_detected"] = not (
    expected_visual_srcs <= visual_mutant_srcs
)
checks["pages_link_mutant_detected"] = not all(
    href.startswith("https://github.com/Kitahl/The-Gauntlet/")
    for href in ("../skills/foil/SKILL.md",)
)
checks["trust_surface_mutant_detected"] = not all(
    token in html.replace("SECURITY.md", "SECURITY_REMOVED")
    for token in (
        "SECURITY.md",
        "GOVERNANCE.md",
        "CONTRIBUTING.md",
        "CITATION.cff",
        "CHANGELOG.md",
        "ROADMAP.md",
    )
)

status = "PASS" if all(checks.values()) else "FAIL"
output = {
    "status": status,
    "checks": checks,
    "render": render,
    "payload_bytes": payload_bytes,
    "total": len(checks),
    "passed": sum(checks.values()),
}
(ROOT / "validation/showcase-validation.json").write_text(
    json.dumps(output, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(output, indent=2))
raise SystemExit(0 if status == "PASS" else 1)
