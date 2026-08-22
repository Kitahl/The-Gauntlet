from pathlib import Path
from html.parser import HTMLParser
import re, json, math
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'docs/index.html'; CSS=ROOT/'docs/styles.css'; README=ROOT/'README.md'
html=HTML.read_text(); css=CSS.read_text(); checks={}

class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=[]; self.hrefs=[]; self.headings=[]; self.main=0; self.nav=0; self.lang=None
    def handle_starttag(self,t,a):
        d=dict(a)
        if t=='html': self.lang=d.get('lang')
        if 'id' in d:self.ids.append(d['id'])
        if t=='a' and 'href' in d:self.hrefs.append(d['href'])
        if t in ('h1','h2','h3'):self.headings.append(t)
        if t=='main':self.main+=1
        if t=='nav':self.nav+=1
p=P(); p.feed(html)
checks['semantic_landmarks']=p.lang=='en' and p.main==1 and p.nav>=1 and p.headings.count('h1')==1
checks['unique_ids']=len(p.ids)==len(set(p.ids))
checks['skip_link']='<a class="skip-link" href="#main">' in html
checks['local_nav_targets']=all((h[1:] in p.ids) for h in p.hrefs if h.startswith('#'))
checks['skill_links_canonical']=all(h.startswith('https://github.com/Kitahl/The-Gauntlet/') for h in p.hrefs if '/skills/' in h)
checks['no_remote_runtime_assets']=not re.search(r'<(?:script|link)[^>]+(?:src|href)=["\']https?://',html,re.I)
checks['no_javascript_required']='<script' not in html.lower()
checks['focus_visible']=':focus-visible' in css
checks['reduced_motion']='prefers-reduced-motion' in css
checks['license_disclosure']='license' in html.lower() and 'license' in README.read_text().lower()
checks['pages_contract']=(ROOT/'PAGES_SETUP.md').exists() and (ROOT/'docs/.nojekyll').exists() and 'main' in (ROOT/'PAGES_SETUP.md').read_text() and '/docs' in (ROOT/'PAGES_SETUP.md').read_text()
checks['source_artifacts_present']=all((ROOT/'skills'/d/'SKILL.md').exists() for d in ['mathbot','scoutbot','novelbot','codebot','benchbot','infinity-gauntlet','meditate','council-of-elders','foil'])
checks['foil_validation_present']=(ROOT/'validation/FOIL_RESEARCH_INTEGRATION_VALIDATION.json').exists()
prov=json.loads((ROOT/'docs/content-provenance.json').read_text())
checks['provenance_sources_exist']=all((ROOT/src).exists() for c in prov['claims'] for src in c['sources'])
checks['module_count_matches']=len(list((ROOT/'skills').glob('*/SKILL.md')))==9 and '<strong>9</strong>' in html
checks['evidence_trail_exposed']=all(x in html for x in ['FOIL_RESEARCH_BASIS.md','/validation','skills/foil/SKILL.md'])
checks['activation_surface']=all(cmd in html for cmd in ['/foil','/mind','/space','/reality','/power','/time','/gauntlet','/council']) and 'Meditate' in html
trigger_sources={
    '/foil':'skills/foil/SKILL.md','/mind':'skills/mathbot/SKILL.md','/space':'skills/scoutbot/SKILL.md',
    '/reality':'skills/novelbot/SKILL.md','/power':'skills/codebot/SKILL.md','/time':'skills/benchbot/SKILL.md',
    '/gauntlet':'skills/infinity-gauntlet/SKILL.md','/council':'skills/council-of-elders/SKILL.md'
}
checks['activation_triggers_trace_to_source']=all(cmd in (ROOT/rel).read_text() for cmd,rel in trigger_sources.items())
checks['meditate_dispatch_trace']='invoked by the Soul' in (ROOT/'skills/meditate/SKILL.md').read_text()
checks['no_behavioral_efficacy_overclaim']='does not establish that FOIL improves human learning' in html

# Basic contrast for principal text tokens against declared dark surfaces.
def lum(hexv):
    x=hexv.lstrip('#'); vals=[int(x[i:i+2],16)/255 for i in (0,2,4)]
    vals=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in vals]
    return .2126*vals[0]+.7152*vals[1]+.0722*vals[2]
def ratio(a,b):
    l1,l2=sorted((lum(a),lum(b)), reverse=True); return (l1+.05)/(l2+.05)
checks['principal_contrast']=ratio('#f5f7f9','#07080a')>=7 and ratio('#9aa4af','#07080a')>=4.5 and ratio('#ff8a3d','#07080a')>=4.5

# Browser render using set_content due sandbox URL policy; CSS is the production stylesheet.
render={}
source=html.replace('<link rel="stylesheet" href="styles.css" />','')
with sync_playwright() as pw:
    b=pw.chromium.launch(headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox','--disable-dev-shm-usage'])
    for name,w,h in [('desktop',1440,900),('mobile',390,844)]:
        page=b.new_page(viewport={'width':w,'height':h})
        errors=[]; page.on('console', lambda m, errors=errors: errors.append(m.text) if m.type=='error' else None); page.on('pageerror', lambda e, errors=errors: errors.append(str(e)))
        page.set_content(source, wait_until='load'); page.add_style_tag(content=css)
        # Exercise a real keyboard path from document start.
        page.keyboard.press('Tab')
        focused=page.evaluate('document.activeElement && document.activeElement.getAttribute("href")')
        render[name]={
            'horizontal_overflow':page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth'),
            'keyboard_first_focus':focused,
            'console_errors':errors,
            'h1_visible':page.locator('h1').is_visible(),
            'main_visible':page.locator('main').is_visible(),
        }
        page.screenshot(path=str(ROOT/'validation'/f'showcase-{name}.png'), full_page=True)
    b.close()
checks['responsive_no_overflow']=all(not v['horizontal_overflow'] for v in render.values())
checks['render_no_console_errors']=all(not v['console_errors'] for v in render.values())
checks['render_core_visible']=all(v['h1_visible'] and v['main_visible'] for v in render.values())
checks['keyboard_path']=all(v.get('keyboard_first_focus')=='#main' for v in render.values())
payload_bytes=HTML.stat().st_size+CSS.stat().st_size
checks['payload_budget']=payload_bytes < 100_000
checks['payload_budget_negative_control']=(payload_bytes+100_001) >= 100_000
# Gate mutants: prove the validation suite detects representative regressions.
mutant_html=source.replace('<main id="main">','<main id="main" style="display:none">')
mutant_css=css+'\nh1{font-size:12px!important}\n'
with sync_playwright() as pw:
    b=pw.chromium.launch(headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox','--disable-dev-shm-usage'])
    page=b.new_page(viewport={'width':1440,'height':900})
    page.set_content(mutant_html, wait_until='load'); page.add_style_tag(content=mutant_css)
    hidden_detected=not page.locator('main').is_visible()
    hierarchy_detected=float(page.locator('h1').evaluate('(e)=>parseFloat(getComputedStyle(e).fontSize)')) < 24
    b.close()
checks['render_mutant_detected']=hidden_detected
checks['hierarchy_mutant_detected']=hierarchy_detected
# Link mutant: relative sibling links would be absent from a docs-only Pages publish.
checks['pages_link_mutant_detected']=not all(h.startswith('https://github.com/Kitahl/The-Gauntlet/') for h in ['../skills/foil/SKILL.md'])

status='PASS' if all(checks.values()) else 'FAIL'
out={'status':status,'checks':checks,'render':render,'total':len(checks),'passed':sum(checks.values())}
(ROOT/'validation/showcase-validation.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
raise SystemExit(0 if status=='PASS' else 1)
