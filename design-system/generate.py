#!/usr/bin/env python3
"""Generate the Maintain Media Design System page (design-system/index.html).

Reads the real assets under media/, renders lightweight preview thumbnails into
design-system/previews/ (fast page), and links every tile to the full-resolution
source file. Re-run after adding assets:  python design-system/generate.py
"""
import html
import re
from pathlib import Path
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
MEDIA = REPO / "media"
DS = REPO / "design-system"
PREV = DS / "previews"
OUT = DS / "index.html"
TK = "media/complete-toolkit/01 Visual Identity"


def rel(p: str) -> str:
    """Repo-relative path -> href from design-system/, spaces encoded."""
    return ("../" + p).replace(" ", "%20")


def humanize(name: str) -> str:
    s = re.sub(r"\.[^.]+$", "", name)
    s = re.sub(r"\s*\(\d+\)$", "", s)
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)
    s = s.replace("-", " ").replace("_", " ")
    return re.sub(r"\s+", " ", s).strip().title()


def listdir(rel_dir, exts):
    d = REPO / rel_dir
    return sorted([p for p in d.iterdir() if p.is_file() and p.suffix.lower() in exts],
                  key=lambda p: p.name.lower()) if d.is_dir() else []


_made = {}


def preview(relpath: str, maxdim: int) -> str:
    """Downscaled preview href (relative to design-system/). SVG -> source as-is."""
    ext = Path(relpath).suffix.lower()
    if ext == ".svg":
        return rel(relpath)
    if relpath in _made:
        return _made[relpath]
    slug = relpath.replace("media/complete-toolkit/01 Visual Identity/", "").replace("media/", "")
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", slug)
    outext = ".jpg" if ext in (".jpg", ".jpeg") else ".png"
    slug = re.sub(r"\.(png|jpg|jpeg)$", "", slug, flags=re.I) + outext
    out = PREV / slug
    try:
        im = Image.open(REPO / relpath)
        im.thumbnail((maxdim, maxdim))
        if outext == ".jpg":
            im.convert("RGB").save(out, quality=82, optimize=True)
        else:
            im.save(out, optimize=True)
        res = "previews/" + slug
    except Exception:
        res = rel(relpath)
    _made[relpath] = res
    return res


# ---- gather assets -------------------------------------------------------
line_icons = listdir(f"{TK}/Iconography", {".png"})

colored_dir = REPO / TK / "icons-colored"
colored = {}
if colored_dir.is_dir():
    for p in sorted(colored_dir.iterdir()):
        if p.suffix.lower() not in {".svg", ".png"}:
            continue
        base = re.sub(r"\s*\(\d+\)$", "", p.stem)
        if base not in colored or (p.suffix.lower() == ".svg" and not colored[base].endswith(".svg")):
            colored[base] = f"{TK}/icons-colored/{p.name}"
colored_icons = [(humanize(b), path) for b, path in sorted(colored.items(), key=lambda x: x[0].lower())]

canva_icons = [(humanize(p.name), f"media/complete-toolkit/04 Canva Assets/Icons/{p.name}")
               for p in listdir("media/complete-toolkit/04 Canva Assets/Icons", {".png"})]

GFRIENDLY = {
    "maintain-media-gradient-bg.png": "Brand gradient · hero", "gradient.png": "Purple gradient · glow",
    "orange-gradient.png": "Purple gradient · radial", "Gradient-pantone-1.png": "Purple gradient · tall",
    "blue-gradient.png": "Teal gradient", "blu-gradient.svg": "Teal gradient · vector",
    "gradient.jpg": "Dark gradient", "gradient-white.jpg": "White gradient",
    "white-gradient.png": "White gradient · radial", "white-lineargradient.png": "White gradient · linear",
    "white bg.jpg": "White background", "cover.jpg": "Cover background", "cover 2.jpg": "Cover background · alt",
    "section.jpg": "Section background", "mountain.svg": "Mountain graphic · vector",
    "mountain forms 2.png": "Mountain wireframe",
}
bg_sources, seen = [], set()
for relpath in ([f"media/backgrounds/{p.name}" for p in listdir("media/backgrounds", {".png", ".jpg", ".jpeg"})]
                + [f"{TK}/graphics/{p.name}" for p in listdir(f"{TK}/graphics", {".png", ".jpg", ".jpeg", ".svg"})]
                + [f"media/complete-toolkit/04 Canva Assets/Presentation Backgrounds/{p.name}"
                   for p in listdir("media/complete-toolkit/04 Canva Assets/Presentation Backgrounds", {".jpg", ".jpeg", ".png"})]):
    base = Path(relpath).name
    if base in seen:
        continue
    seen.add(base)
    bg_sources.append((GFRIENDLY.get(base, humanize(base)), relpath))

TYPO = f"{TK}/Typography"
albert, vela, aptos = f"{TYPO}/Albert Sans/static", f"{TYPO}/Vela Sans", f"{TYPO}/Microsoft Aptos Fonts"
n_icons = len(line_icons) + len(colored_icons) + len(canva_icons)

PREV.mkdir(parents=True, exist_ok=True)

FACES = "".join([
    f"@font-face{{font-family:'Albert Sans';font-weight:{w};font-style:normal;font-display:swap;"
    f"src:url('{rel(f'{albert}/AlbertSans-{n}.ttf')}') format('truetype');}}"
    for w, n in [(400, "Regular"), (500, "Medium"), (600, "SemiBold"), (700, "Bold"), (800, "ExtraBold")]
]) + "".join([
    f"@font-face{{font-family:'Vela Sans';font-weight:{w};font-style:normal;font-display:swap;"
    f"src:url('{rel(f'{vela}/VelaSans-{n}.otf')}') format('opentype');}}"
    for w, n in [(700, "Bold"), (800, "ExtraBold")]
]) + "".join([
    f"@font-face{{font-family:'Aptos';font-weight:{w};font-style:normal;font-display:swap;"
    f"src:url('{rel(f'{aptos}/{n}.ttf')}') format('truetype');}}"
    for w, n in [(400, "Aptos"), (700, "Aptos-Bold")]
])

CSS = r"""
:root{
  --bg:#061518; --surface:#0c2a30; --surface-2:#123a42; --border:rgba(255,255,255,.10);
  --ink:#fff; --ink-2:#cdd9db; --muted:#93a7aa;
  --purple:#a04dff; --purple-300:#c79bff; --purple-600:#8a34f0; --brand-dark:#08282d;
  --r-sm:8px; --r-md:14px; --r-lg:20px; --r-pill:999px;
  --maxw:1180px; --ease:cubic-bezier(.16,1,.3,1);
  --font:'Albert Sans',system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  --display:'Vela Sans','Albert Sans',system-ui,sans-serif;
}
*{box-sizing:border-box}
figure{margin:0}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink-2);font-family:var(--font);line-height:1.6;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;overflow-x:hidden}
body::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;
  background:radial-gradient(1100px 620px at 78% -8%,rgba(160,77,255,.26),transparent 60%),
             radial-gradient(900px 520px at 6% 2%,rgba(160,77,255,.10),transparent 55%)}
a{color:var(--purple-300);text-decoration:none}
a:hover{color:#fff}
img{max-width:100%;display:block}
h1,h2,h3{color:var(--ink);text-wrap:balance;letter-spacing:-.02em;line-height:1.05;margin:0}
:focus-visible{outline:2.5px solid var(--purple-300);outline-offset:3px;border-radius:6px}

.nav{position:sticky;top:0;z-index:100;display:flex;align-items:center;gap:24px;
  padding:14px clamp(16px,4vw,40px);background:rgba(6,21,24,.72);backdrop-filter:blur(14px);
  border-bottom:1px solid var(--border)}
.nav__logo{height:26px;width:auto}
.nav__links{display:flex;gap:6px;margin-left:auto;flex-wrap:wrap}
.nav__links a{color:var(--ink-2);font-size:.86rem;font-weight:500;padding:7px 12px;border-radius:var(--r-pill);
  transition:background .2s,color .2s}
.nav__links a:hover{background:var(--surface);color:#fff}
@media(max-width:720px){.nav__links{display:none}}

.wrap{max-width:var(--maxw);margin:0 auto;padding:0 clamp(16px,4vw,40px)}
section{padding:clamp(56px,8vw,104px) 0;border-top:1px solid var(--border)}
.sec-head{max-width:70ch;margin-bottom:clamp(28px,5vw,50px)}
.sec-head h2{font-family:var(--display);font-size:clamp(1.9rem,4.4vw,3rem);font-weight:800}
.sec-head p{color:var(--ink-2);font-size:1.05rem;margin:.8rem 0 0}
.sec-head .count{color:var(--purple-300);font-weight:600}

.hero{position:relative;min-height:86vh;display:flex;flex-direction:column;justify-content:center;
  padding:96px clamp(16px,4vw,40px) 72px;overflow:hidden}
.hero__grid{position:absolute;inset:0;z-index:-1;opacity:.6;
  background-image:linear-gradient(transparent 0 47px,rgba(160,77,255,.06) 47px 48px),
                   linear-gradient(90deg,transparent 0 47px,rgba(160,77,255,.06) 47px 48px);
  background-size:48px 48px;
  -webkit-mask-image:radial-gradient(120% 95% at 50% -12%,#000,transparent 72%);
          mask-image:radial-gradient(120% 95% at 50% -12%,#000,transparent 72%)}
.hero__inner{max-width:var(--maxw);margin:0 auto;width:100%}
.hero__logo{height:clamp(32px,5vw,48px);width:auto;margin-bottom:clamp(24px,5vw,40px)}
.hero h1{font-family:var(--display);font-weight:800;letter-spacing:-.035em;font-size:clamp(2.6rem,8vw,5.6rem);
  color:#fff;max-width:15ch}
.hero h1 em{font-style:normal;color:var(--purple)}
.hero__sub{font-size:clamp(1.05rem,2.2vw,1.3rem);color:var(--ink-2);max-width:60ch;margin:1.4rem 0 0}
.hero__sub code{color:var(--purple-300);background:rgba(160,77,255,.10);padding:1px 7px;border-radius:6px;font-size:.9em}
.hero__meta{display:flex;gap:10px;flex-wrap:wrap;margin-top:2.2rem}
.pill{display:inline-flex;align-items:center;gap:8px;font-size:.82rem;font-weight:600;color:var(--ink-2);
  background:var(--surface);border:1px solid var(--border);padding:8px 15px;border-radius:var(--r-pill)}
.pill .dot{width:9px;height:9px;border-radius:50%;background:var(--purple)}

.swatches{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:18px}
.sw{border:1px solid var(--border);border-radius:var(--r-lg);overflow:hidden;background:var(--surface)}
.sw__chip{height:170px;display:flex;align-items:flex-end;padding:16px}
.sw__chip .hx{font-weight:700;font-size:1.02rem}
.sw__body{padding:16px 18px 20px}
.sw__body .nm{color:#fff;font-weight:700;font-size:1.05rem}
.sw__body .use{font-size:.9rem;color:var(--ink-2);margin:.35rem 0 .8rem}
.sw__body .meta{font-size:.78rem;color:var(--muted);font-variant-numeric:tabular-nums;line-height:1.5}
.copy{cursor:pointer;font:inherit;font-size:.8rem;font-weight:600;color:#fff;background:rgba(255,255,255,.09);
  border:1px solid var(--border);padding:6px 12px;border-radius:var(--r-pill);transition:background .18s,transform .1s;margin-top:12px}
.copy:hover{background:rgba(255,255,255,.18)}
.copy:active{transform:scale(.96)}
.tokens{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin-top:22px}
.tok{display:flex;align-items:center;gap:12px;background:var(--surface);border:1px solid var(--border);
  border-radius:var(--r-md);padding:12px 14px}
.tok .box{width:34px;height:34px;border-radius:9px;border:1px solid rgba(255,255,255,.16);flex:none}
.tok .tk{font-size:.82rem}.tok .tk b{display:block;color:#fff;font-weight:600}
.tok .tk span{color:var(--muted);font-variant-numeric:tabular-nums}
.gradientbar{margin-top:24px;height:118px;border-radius:var(--r-lg);border:1px solid var(--border);
  background:linear-gradient(90deg,#a04dff 0%,#5b2fa3 45%,#08282d 100%);display:flex;align-items:flex-end;
  padding:14px 18px;color:#fff;font-weight:600;font-size:.85rem}
.gradientbar code{color:#fff}
.brandref{margin-top:24px;border:1px solid var(--border);border-radius:var(--r-lg);overflow:hidden;background:var(--surface)}
.brandref img{width:100%;display:block}
.brandref figcaption{padding:12px 16px;font-size:.82rem;color:var(--muted)}

.logos{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}
.logo-card{border:1px solid var(--border);border-radius:var(--r-lg);overflow:hidden;background:var(--surface)}
.logo-stage{height:188px;display:flex;align-items:center;justify-content:center;padding:34px}
.logo-stage img{max-height:72px;width:auto}
.logo-stage.on-dark{background:radial-gradient(120% 140% at 50% 0,#123a42,#08282d)}
.logo-stage.on-light{background:#f4f5f7}
.lc-body{padding:14px 18px 18px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.lc-body b{color:#fff;font-weight:600;font-size:.95rem}.lc-body span{color:var(--muted);font-size:.82rem}
.dl{font-size:.8rem;font-weight:600;color:var(--purple-300);border:1px solid var(--border);padding:6px 12px;
  border-radius:var(--r-pill);white-space:nowrap;transition:background .18s,color .18s}
.dl:hover{background:var(--surface-2);color:#fff}
.rules{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-top:22px}
.rule{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);padding:16px 18px}
.rule h4{margin:0 0 8px;color:#fff;font-size:.95rem;display:flex;align-items:center;gap:8px}
.rule.do h4::before{content:"✓";color:#39d98a;font-weight:800}
.rule.dont h4::before{content:"✕";color:#ff6b8a;font-weight:800}
.rule ul{margin:0;padding-left:18px;font-size:.9rem;color:var(--ink-2)}.rule li{margin:.3rem 0}

.typefam{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px}
.tf{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-lg);padding:24px}
.tf .aa{font-size:4.4rem;line-height:1;color:#fff;margin-bottom:6px}
.tf .fam{color:#fff;font-weight:700;font-size:1.1rem}
.tf .role{color:var(--muted);font-size:.85rem;margin:.2rem 0 1rem}
.tf .spec{font-size:1.5rem;color:var(--ink-2)}
.scale{margin-top:30px;display:flex;flex-direction:column;gap:14px}
.scale .row{display:flex;align-items:baseline;gap:18px;border-bottom:1px solid var(--border);padding-bottom:14px;flex-wrap:wrap}
.scale .row .lbl{color:var(--muted);font-size:.76rem;min-width:150px;font-variant-numeric:tabular-nums}
.scale .row .samp{color:#fff}
.weights{margin-top:26px;display:flex;flex-direction:column;gap:6px}
.weights .w{font-size:1.5rem;color:#fff}
.weights .w span{color:var(--muted);font-size:.8rem;font-family:var(--font);font-weight:500;margin-left:14px;vertical-align:middle}

.icongrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(104px,1fr));gap:12px}
.chip{background:#f4f5f7;border:1px solid var(--border);border-radius:var(--r-md);padding:16px 8px 10px;
  text-align:center;transition:transform .18s var(--ease),box-shadow .18s}
.chip:hover{transform:translateY(-3px);box-shadow:0 10px 26px rgba(0,0,0,.35)}
.chip--dark{background:var(--surface)}
.chip img{width:38px;height:38px;object-fit:contain;margin:0 auto 10px}
.chip figcaption{font-size:.72rem;color:#3a4a4d;line-height:1.25;overflow-wrap:break-word;hyphens:none}
.chip--dark figcaption{color:var(--ink-2)}
.subhead{font-family:var(--display);font-weight:700;color:#fff;font-size:1.15rem;margin:34px 0 14px;display:flex;
  align-items:center;gap:10px;flex-wrap:wrap}
.subhead .n{font-size:.78rem;color:var(--purple-300);background:var(--surface);border:1px solid var(--border);
  padding:3px 10px;border-radius:var(--r-pill);font-family:var(--font);font-weight:600}

.gfx{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px}
.gfx figure{margin:0;border:1px solid var(--border);border-radius:var(--r-lg);overflow:hidden;background:var(--surface)}
.gfx .ph{aspect-ratio:16/10;width:100%;object-fit:cover;background:#02090b;display:block}
.gfx figcaption{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:12px 14px;
  font-size:.85rem;color:#fff;font-weight:500}

.index{border:1px solid var(--border);border-radius:var(--r-lg);overflow:hidden;background:var(--surface)}
.index .ir{display:grid;grid-template-columns:1.1fr 2fr auto;gap:16px;align-items:center;padding:15px 20px;
  border-top:1px solid var(--border)}
.index .ir:first-child{border-top:0}
.index .ir b{color:#fff;font-weight:600;font-size:.95rem}
.index .ir .desc{color:var(--ink-2);font-size:.86rem}
@media(max-width:640px){.index .ir{grid-template-columns:1fr;gap:6px}}

footer{border-top:1px solid var(--border);padding:44px 0 60px;color:var(--muted);font-size:.85rem}
footer .fx{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;align-items:center}
footer strong{color:#fff}footer code{color:var(--purple-300)}
footer .fdots{display:flex;gap:8px}
footer .fdots i{width:22px;height:22px;border-radius:6px;border:1px solid var(--border)}

.toast{position:fixed;bottom:26px;left:50%;transform:translate(-50%,20px);opacity:0;pointer-events:none;
  background:#fff;color:#08282d;font-weight:600;font-size:.85rem;padding:10px 18px;border-radius:var(--r-pill);
  box-shadow:0 12px 40px rgba(0,0,0,.4);transition:opacity .25s,transform .25s;z-index:200}
.toast.show{opacity:1;transform:translate(-50%,0)}
.rise{opacity:0;transform:translateY(18px);animation:rise .7s var(--ease) forwards}
@keyframes rise{to{opacity:1;transform:none}}
@media(prefers-reduced-motion:reduce){
  *{animation:none!important;transition:none!important;scroll-behavior:auto!important}
  .rise{opacity:1;transform:none}
}
"""


def chip(label, path, dark=False):
    cls = "chip chip--dark" if dark else "chip"
    return (f'<figure class="{cls}"><img loading="lazy" src="{preview(path, 96)}" '
            f'alt="{html.escape(label)} icon" width="38" height="38">'
            f'<figcaption>{html.escape(label)}</figcaption></figure>')


line_grid = "".join(chip(humanize(p.name), f"{TK}/Iconography/{p.name}") for p in line_icons)
colored_grid = "".join(chip(lbl, path, dark=True) for lbl, path in colored_icons)
canva_grid = "".join(chip(lbl, path, dark=True) for lbl, path in canva_icons)

gfx_grid = "".join(
    f'<figure><a href="{rel(path)}" target="_blank" rel="noopener">'
    f'<img class="ph" loading="lazy" src="{preview(path, 640)}" alt="{html.escape(lbl)}"></a>'
    f'<figcaption><span>{html.escape(lbl)}</span>'
    f'<a class="dl" href="{rel(path)}" download>Open</a></figcaption></figure>'
    for lbl, path in bg_sources)

CORE = [
    ("Purple", "#a04dff", "oklch(0.59 0.25 295)", "160 77 255", "#ffffff", "Primary. Logo mark, accents, links, focus, key CTAs."),
    ("Dark", "#08282d", "oklch(0.26 0.03 210)", "8 40 45", "#ffffff", "Dark surfaces, deep backgrounds, text on light."),
    ("White", "#ffffff", "oklch(1 0 0)", "255 255 255", "#08282d", "Text on dark, negative space, light surfaces."),
]
core_html = "".join(
    f'<div class="sw"><div class="sw__chip" style="background:{hx}"><span class="hx" style="color:{txt}">{hx}</span></div>'
    f'<div class="sw__body"><div class="nm">{nm}</div><div class="use">{use}</div>'
    f'<div class="meta">OKLCH {ok}<br>RGB {rgb}</div>'
    f'<button class="copy" data-copy="{hx}">Copy {hx}</button></div></div>'
    for nm, hx, ok, rgb, txt, use in CORE)

TOKENS = [("--bg", "#061518"), ("--surface", "#0c2a30"), ("--surface-2", "#123a42"), ("--purple-300", "#c79bff"),
          ("--purple-600", "#8a34f0"), ("--ink-2", "#cdd9db"), ("--muted", "#93a7aa"), ("--border", "rgba(255,255,255,.10)")]
tokens_html = "".join(
    f'<div class="tok"><span class="box" style="background:{v}"></span>'
    f'<span class="tk"><b>{k}</b><span>{v}</span></span></div>' for k, v in TOKENS)

TYPEFAMS = [("Albert Sans", "'Albert Sans'", "Primary · UI, body, most headings", "700"),
            ("Vela Sans", "'Vela Sans'", "Display · large expressive headlines", "800"),
            ("Aptos", "'Aptos'", "Documents · Word, PowerPoint, email", "700")]
typefam_html = "".join(
    f'<div class="tf"><div class="aa" style="font-family:{fam};font-weight:{wt}">Aa</div>'
    f'<div class="fam">{nm}</div><div class="role">{role}</div>'
    f'<div class="spec" style="font-family:{fam}">Maintain Media</div></div>'
    for nm, fam, role, wt in TYPEFAMS)

SCALE = [
    ("Display · 800 · Vela Sans", "clamp 2.6–5.6rem", "var(--display)", "800", "3.4rem", "Maintain Media"),
    ("H1 · 700", "2.5rem / 40px", "var(--font)", "700", "2.5rem", "Design system"),
    ("H2 · 700", "2rem / 32px", "var(--font)", "700", "2rem", "Foundations"),
    ("H3 · 600", "1.5rem / 24px", "var(--font)", "600", "1.5rem", "Iconography"),
    ("Body · 400", "1.0625rem / 17px", "var(--font)", "400", "1.0625rem", "The single source of truth for the brand's visual identity."),
    ("Caption · 500", "0.82rem / 13px", "var(--font)", "500", "0.82rem", "Labels, metadata, captions"),
]
scale_html = "".join(
    f'<div class="row"><span class="lbl">{lbl}<br>{meta}</span>'
    f'<span class="samp" style="font-family:{fam};font-weight:{wt};font-size:{size}">{html.escape(samp)}</span></div>'
    for lbl, meta, fam, wt, size, samp in SCALE)

WEIGHTS = [("400", "Regular"), ("500", "Medium"), ("600", "SemiBold"), ("700", "Bold"), ("800", "ExtraBold")]
weights_html = "".join(
    f'<div class="w" style="font-weight:{w}">Maintain Media<span>Albert Sans {w} · {n}</span></div>'
    for w, n in WEIGHTS)

INDEX = [
    ("Logos", "SVG wordmark, dark & light backgrounds (+ raster fallbacks)", "media/logos/"),
    ("Colour reference", "Original brand-kit colour board", "media/brand/"),
    ("Line icons", f"{len(line_icons)} stroke icons (dark)", f"{TK}/Iconography/"),
    ("Colored icons", f"{len(colored_icons)} filled purple icons (SVG)", f"{TK}/icons-colored/"),
    ("Canva icons", f"{len(canva_icons)} Canva-optimised PNG icons", "media/complete-toolkit/04 Canva Assets/Icons/"),
    ("Graphics & backgrounds", "Gradients, wireframe, textures", f"{TK}/graphics/"),
    ("Backgrounds (hero)", "Brand gradient background", "media/backgrounds/"),
    ("Type — Albert Sans", "Primary UI/body family (variable + static)", f"{TYPO}/Albert Sans/"),
    ("Type — Vela Sans", "Display family", f"{TYPO}/Vela Sans/"),
    ("Type — Aptos", "Document/Office family", f"{TYPO}/Microsoft Aptos Fonts/"),
    ("Specifications", "Written visual spec (DESIGN.md) & strategy (PRODUCT.md)", "DESIGN.md"),
]
index_html = "".join(
    f'<div class="ir"><b>{nm}</b><span class="desc">{desc}</span>'
    f'<a class="dl" href="{rel(path)}" target="_blank" rel="noopener">Open&nbsp;→</a></div>'
    for nm, desc, path in INDEX)

logo_darkbg = rel("media/logos/maintain-media-logo-darkbg.svg")
logo_lightbg = rel("media/logos/maintain-media-logo-lightbg.svg")
brand_ref_path = "media/brand/maintain-media-brandkit-colors.png"
brand_ref_img = preview(brand_ref_path, 1100) if (REPO / brand_ref_path).exists() else ""
brand_ref_html = (f'<figure class="brandref"><a href="{rel(brand_ref_path)}" target="_blank" rel="noopener">'
                  f'<img loading="lazy" src="{brand_ref_img}" alt="Original Maintain Media brand-kit colour board"></a>'
                  f'<figcaption>Original brand-kit colour board · <code>media/brand/</code></figcaption></figure>'
                  ) if brand_ref_img else ""

DOC = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Maintain Media — Design System</title>
<meta name="description" content="The single source of truth for the Maintain Media brand: logos, colour, typography, iconography, and graphics — every asset shown and linked.">
<style>{FACES}{CSS}</style>
</head>
<body>
<nav class="nav">
  <img class="nav__logo" src="{logo_darkbg}" alt="Maintain Media">
  <div class="nav__links">
    <a href="#logo">Logo</a><a href="#color">Colour</a><a href="#type">Typography</a>
    <a href="#icons">Iconography</a><a href="#graphics">Graphics</a><a href="#assets">Assets</a>
  </div>
</nav>

<header class="hero">
  <span class="hero__grid"></span>
  <div class="hero__inner">
    <img class="hero__logo rise" src="{logo_darkbg}" alt="Maintain Media logo">
    <h1 class="rise" style="animation-delay:.06s">The Maintain&nbsp;Media <em>design system</em></h1>
    <p class="hero__sub rise" style="animation-delay:.12s">The single source of truth for the brand's visual identity —
      every logo, colour, typeface, icon, and graphic, shown in full and linked straight to the source files in <code>media/</code>.</p>
    <div class="hero__meta rise" style="animation-delay:.18s">
      <span class="pill"><span class="dot"></span>Purple #a04dff</span>
      <span class="pill">{n_icons} icons</span>
      <span class="pill">3 type families</span>
      <span class="pill">Brand · identity-preserving</span>
    </div>
  </div>
</header>

<main>
<section id="logo"><div class="wrap">
  <div class="sec-head"><h2>Logo</h2><p>The ascending “M” mountain mark with the Maintain Media wordmark.
    Prefer the vector SVGs; the light-background version carries dark text, the dark-background version white.</p></div>
  <div class="logos">
    <div class="logo-card"><div class="logo-stage on-dark"><img src="{logo_darkbg}" alt="Maintain Media logo, white, on dark"></div>
      <div class="lc-body"><div><b>Dark background</b><br><span>white wordmark · canonical vector</span></div>
      <a class="dl" href="{logo_darkbg}" download>SVG</a></div></div>
    <div class="logo-card"><div class="logo-stage on-light"><img src="{logo_lightbg}" alt="Maintain Media logo, dark, on light"></div>
      <div class="lc-body"><div><b>Light background</b><br><span>dark wordmark · canonical vector</span></div>
      <a class="dl" href="{logo_lightbg}" download>SVG</a></div></div>
  </div>
  <div class="rules">
    <div class="rule do"><h4>Do</h4><ul><li>Use the SVG vectors wherever possible.</li>
      <li>Keep clearspace ≥ the height of the “M” mark.</li>
      <li>Match the variant to the background.</li></ul></div>
    <div class="rule dont"><h4>Don't</h4><ul><li>Recolour the mark off-brand or add effects.</li>
      <li>Stretch, rotate, or crop the logo.</li>
      <li>Place the dark wordmark on a dark background.</li></ul></div>
  </div>
</div></section>

<section id="color"><div class="wrap">
  <div class="sec-head"><h2>Colour</h2><p>Three core brand colours — hex is the source of truth. The extended tokens
    below are derived for building interfaces (this page uses them).</p></div>
  <div class="swatches">{core_html}</div>
  <div class="gradientbar">Signature gradient · purple → deep teal — <code>#a04dff → #08282d</code></div>
  <div class="tokens">{tokens_html}</div>
  {brand_ref_html}
</div></section>

<section id="type"><div class="wrap">
  <div class="sec-head"><h2>Typography</h2><p>The brand type library — rendered here in the real font files.
    Pair on weight; don't mix the two geometric sans families in the same body copy.</p></div>
  <div class="typefam">{typefam_html}</div>
  <div class="scale">{scale_html}</div>
  <div class="weights">{weights_html}</div>
</div></section>

<section id="icons"><div class="wrap">
  <div class="sec-head"><h2>Iconography</h2><p><span class="count">{n_icons} icons</span> across two coherent sets.
    Pick one set per surface — don't mix line and filled in the same context.</p></div>
  <div class="subhead">Line icons <span class="n">{len(line_icons)} · dark #08282d</span></div>
  <div class="icongrid">{line_grid}</div>
  <div class="subhead">Colored icons <span class="n">{len(colored_icons)} · purple SVG</span></div>
  <div class="icongrid">{colored_grid}</div>
  <div class="subhead">Canva icon set <span class="n">{len(canva_icons)} · PNG exports</span></div>
  <div class="icongrid">{canva_grid}</div>
</div></section>

<section id="graphics"><div class="wrap">
  <div class="sec-head"><h2>Graphics &amp; Backgrounds</h2><p>Signature gradients, the mountain wireframe, and background
    textures. Thumbnails preview the assets; “Open” links to the full-resolution source.</p></div>
  <div class="gfx">{gfx_grid}</div>
</div></section>

<section id="assets"><div class="wrap">
  <div class="sec-head"><h2>Asset index</h2><p>Every folder in the library, linked. When building anything for
    Maintain Media, start here.</p></div>
  <div class="index">{index_html}</div>
</div></section>
</main>

<footer><div class="wrap"><div class="fx">
  <div><strong>Maintain Media</strong> — Design System · single source of truth<br>
    Generated from <code>media/</code> · re-run <code>design-system/generate.py</code> after adding assets.</div>
  <div class="fdots"><i style="background:#a04dff"></i><i style="background:#08282d"></i><i style="background:#fff"></i></div>
</div></div></footer>

<div class="toast" id="toast">Copied</div>
<script>
document.addEventListener('click',e=>{{
  const b=e.target.closest('.copy'); if(!b)return;
  navigator.clipboard?.writeText(b.dataset.copy).then(()=>{{
    const t=document.getElementById('toast'); t.textContent='Copied '+b.dataset.copy; t.classList.add('show');
    clearTimeout(window.__tt); window.__tt=setTimeout(()=>t.classList.remove('show'),1400);
  }});
}});
</script>
</body></html>"""

OUT.write_text(DOC, encoding="utf-8")
print(f"Wrote {OUT}  ({len(DOC)//1024} KB)")
print(f"  line:{len(line_icons)} colored:{len(colored_icons)} canva:{len(canva_icons)} graphics:{len(bg_sources)} previews:{len(_made)}")
