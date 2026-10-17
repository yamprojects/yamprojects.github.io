"""Builds the site into public/ from projects.json, templates/, images/ and fonts/.

    python tools/build.py

Everything in public/ is generated and gets wiped on every build: edit the sources and run this
again. Screenshots in images/ are center-cropped to 16:10 (from the top with "crop": "top", or
fitted whole with "fit": "contain") and saved as WebP at two widths. A project without an image
gets a drawn SVG cover instead, chosen by its "art" field. The share image images/og.png comes
from tools/og.py.
"""

import datetime
import html
import json
import math
import random
import re
import shutil
import string
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
WIDTHS = (480, 960)
RATIO = 16 / 10
SIZES = "(min-width: 1180px) 360px, (min-width: 740px) 46vw, 100vw"
OG_IMAGE = ROOT / "images" / "og.png"
OG_SIZE = (1200, 630)


PREFIXED_LATIN = re.compile(
    r"(?<!\w)([א-ת]{1,3}-[A-Za-z0-9][\w.#+]*(?: [A-Za-z0-9][\w.#+]*)*)")


def esc(text):
    return html.escape(str(text), quote=True)


def prose(text):
    """Escapes body text and keeps a Hebrew prefix and the Latin word after it on one line."""
    return PREFIXED_LATIN.sub(r'<span class="nw">\1</span>', esc(text))


# ---------------------------------------------------------------- images

def render_image(project):
    """Writes the WebP sizes for a screenshot and returns (srcset, src, width, height)."""
    src = ROOT / "images" / project["image"]
    im = Image.open(src)
    im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
    contain = project.get("fit") == "contain"
    if not contain:
        w, h = im.size
        if w / h > RATIO:
            nw = round(h * RATIO)
            im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = round(w / RATIO)
            top = 0 if project.get("crop") == "top" else (h - nh) // 2
            im = im.crop((0, top, w, top + nh))
    out = []
    for width in WIDTHS:
        if contain:
            scaled = im.copy()
            scaled.thumbnail((width, round(width / RATIO)), Image.LANCZOS)
        else:
            scaled = im.resize((width, round(width / RATIO)), Image.LANCZOS)
        name = f"{project['slug']}-{width}.webp"
        scaled.save(PUBLIC / "img" / name, "WEBP", quality=80, method=6)
        out.append((name, scaled.size))
    srcset = ", ".join(f"img/{name} {size[0]}w" for name, size in out)
    name, (w, h) = out[-1]
    return srcset, f"img/{name}", w, h


def shade(hex_color, amount):
    """Mixes a #rrggbb color toward black (amount < 0) or white (amount > 0)."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    target = 255 if amount > 0 else 0
    a = abs(amount)
    return "#" + "".join(f"{round(c + (target - c) * a):02x}" for c in (r, g, b))


def art_rings(p, a2):
    rings = "".join(
        f'<circle cx="400" cy="250" r="{34 + i * 36}" fill="none" stroke="#fff" '
        f'stroke-width="{3 - i * 0.2:.1f}" opacity="{0.85 - i * 0.085:.2f}"/>'
        for i in range(10))
    return rings + '<circle cx="400" cy="250" r="16" fill="#fff"/>' \
                   '<circle cx="400" cy="250" r="60" fill="#fff" opacity=".12"/>'


def art_wave3d(p, a2):
    parts = []
    for xb in range(-1200, 2001, 100):
        x0 = 400 + (xb - 400) * 0.06
        parts.append(f'<line x1="{x0:.1f}" y1="300" x2="{xb}" y2="500"/>')
    for i in range(1, 9):
        y = 300 + 200 * (i / 8) ** 2
        parts.append(f'<line x1="0" y1="{y:.1f}" x2="800" y2="{y:.1f}"/>')
    grid = f'<g stroke="#fff" stroke-width="1.4" opacity=".28">{"".join(parts)}</g>'
    waves = []
    for k, (amp, op, sw) in enumerate(((58, 1, 4), (40, .45, 2.5), (24, .25, 2))):
        pts = " ".join(
            f"{x},{190 - k * 18 + amp * math.sin(x / 55 + k) * math.sin(math.pi * x / 800):.1f}"
            for x in range(0, 801, 8))
        waves.append(f'<polyline points="{pts}" fill="none" stroke="#a7f3e4" '
                     f'stroke-width="{sw}" opacity="{op}" stroke-linecap="round"/>')
    return grid + "".join(waves)


def art_voice(p, a2):
    bars = []
    n = 21
    for i in range(n):
        d = abs(i - n // 2)
        h = 36 + 210 * abs(math.sin(i * 0.9) * math.cos(d * 0.22)) * (1 - d / (n * 0.75))
        h = max(h, 26)
        x = 400 - (n * 24) / 2 + i * 24
        bars.append(f'<rect x="{x:.1f}" y="{250 - h / 2:.1f}" width="14" height="{h:.1f}" '
                     f'rx="7" fill="#fff" opacity="{0.95 - d * 0.06:.2f}"/>')
    return "".join(bars)


def art_agents(p, a2):
    cols = [(210, (150, 250, 350)), (400, (110, 200, 300, 390)), (590, (170, 330))]
    lines, nodes = [], []
    for (x1, ys1), (x2, ys2) in zip(cols, cols[1:]):
        for y1 in ys1:
            for y2 in ys2:
                lines.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>')
    hot = "210,250 400,200 590,170"
    for x, ys in cols:
        for y in ys:
            nodes.append(f'<circle cx="{x}" cy="{y}" r="17" fill="#fff"/>')
    return (f'<g stroke="#fff" stroke-width="2" opacity=".3">{"".join(lines)}</g>'
            f'<polyline points="{hot}" fill="none" stroke="#fff" stroke-width="6" '
            f'stroke-linecap="round" stroke-linejoin="round"/>' + "".join(nodes))


def art_timing(p, a2):
    rng = random.Random(p["slug"])
    ticks, x = [], 70
    while x < 740:
        ticks.append(x)
        x += rng.choice((40, 40, 60, 80, 20))
    marks = "".join(
        f'<line x1="{t}" y1="{232 if i % 4 else 214}" x2="{t}" y2="{268 if i % 4 else 286}" '
        f'stroke="#fff" stroke-width="{3 if i % 4 == 0 else 2}" opacity=".8"/>'
        for i, t in enumerate(ticks))
    return ('<line x1="50" y1="250" x2="750" y2="250" stroke="#fff" stroke-width="2" opacity=".5"/>'
            + marks
            + '<rect x="392" y="150" width="16" height="200" rx="8" fill="#fff"/>'
            '<circle cx="400" cy="250" r="34" fill="none" stroke="#fff" stroke-width="4"/>'
            '<text x="400" y="400" text-anchor="middle" fill="#fff" '
            'font-family="Consolas, Menlo, monospace" font-size="40" font-weight="700">±0 ms</text>')


def art_waveform(p, a2):
    pts = []
    for x in range(0, 801, 4):
        env = 0.35 + 0.65 * abs(math.sin(x / 140))
        y = 220 + env * (52 * math.sin(x / 9) + 30 * math.sin(x / 3.7) + 18 * math.sin(x / 1.9))
        pts.append(f"{x},{y:.1f}")
    notes = "".join(
        f'<rect x="{x}" y="380" width="{w}" height="26" rx="13" fill="#fff" opacity="{op}"/>'
        for x, w, op in ((90, 26, .9), (170, 26, .9), (230, 110, .7), (400, 26, .9),
                         (460, 26, .9), (520, 26, .9), (600, 150, .7)))
    return (f'<polyline points="{" ".join(pts)}" fill="none" stroke="#fff" stroke-width="2.4" '
            f'stroke-linejoin="round" opacity=".9"/>'
            '<line x1="40" y1="393" x2="760" y2="393" stroke="#fff" stroke-width="2" opacity=".35"/>'
            '<line x1="300" y1="350" x2="300" y2="436" stroke="#fff" stroke-width="4"/>' + notes)


def art_hex(p, a2):
    rng = random.Random(p["slug"])
    rows = []
    for r in range(11):
        y = 62 + r * 38
        addr = f"{0x7FF6A3C00000 + r * 16:012X}"
        data = " ".join(f"{rng.randrange(256):02X}" for _ in range(8))
        hot = r == 5
        if hot:
            rows.append(f'<rect x="36" y="{y - 28}" width="728" height="38" rx="6" fill="#fff" opacity=".14"/>')
        rows.append(
            f'<text x="56" y="{y}" fill="#fff" opacity="{1 if hot else .38}">'
            f'{addr}  {data if not hot else "4E 6F 6E 65 00 00 00 00"}'
            f'{"  None" if hot else ""}</text>')
    return ('<g font-family="Consolas, Menlo, monospace" font-size="25" '
            f'xml:space="preserve">{"".join(rows)}</g>')


def art_chip(p, a2):
    pins = []
    for i in range(7):
        o = 160 + i * 30
        pins += [f'<line x1="{o + 80}" y1="105" x2="{o + 80}" y2="135"/>',
                 f'<line x1="{o + 80}" y1="365" x2="{o + 80}" y2="395"/>',
                 f'<line x1="255" y1="{o - 10}" x2="285" y2="{o - 10}"/>',
                 f'<line x1="515" y1="{o - 10}" x2="545" y2="{o - 10}"/>']
    pulse = "300,250 350,250 372,250 388,190 404,318 420,212 432,262 446,250 500,250"
    return (f'<g stroke="#fff" stroke-width="6" stroke-linecap="round" opacity=".55">{"".join(pins)}</g>'
            '<rect x="285" y="135" width="230" height="230" rx="22" fill="none" stroke="#fff" stroke-width="5"/>'
            f'<polyline points="{pulse}" fill="none" stroke="{a2}" stroke-width="7" '
            'stroke-linecap="round" stroke-linejoin="round"/>')


def art_letters(p, a2):
    rng = random.Random(p["slug"])
    letters = []
    for ch in "אבגדהוזחטיכלמנסעפצקרשת":
        x, y = rng.randrange(30, 770), rng.randrange(60, 500)
        if 230 < x < 570 and 120 < y < 390:
            continue
        letters.append(
            f'<text x="{x}" y="{y}" font-size="{rng.randrange(40, 110)}" '
            f'opacity="{rng.uniform(.14, .34):.2f}" transform="rotate({rng.randrange(-18, 18)} {x} {y})">{ch}</text>')
    bubble = ("M300 140h200a40 40 0 0 1 40 40v110a40 40 0 0 1-40 40H390l-60 46v-46h-30"
              "a40 40 0 0 1-40-40V180a40 40 0 0 1 40-40z")
    return (f'<g fill="#fff" font-family="Arial, sans-serif" font-weight="700">{"".join(letters)}</g>'
            f'<path d="{bubble}" fill="#fff"/>'
            f'<text x="400" y="262" text-anchor="middle" fill="{shade(p["accent"], -0.35)}" '
            'font-family="Arial, sans-serif" font-weight="800" font-size="64">עברית</text>')


ARTS = {
    "rings": art_rings, "wave3d": art_wave3d, "voice": art_voice, "agents": art_agents,
    "timing": art_timing, "waveform": art_waveform, "hex": art_hex, "chip": art_chip,
    "letters": art_letters,
}


def render_art(project):
    """Writes a drawn SVG cover and returns its path."""
    accent = project["accent"]
    a2 = project.get("accent2") or shade(accent, -0.55)
    body = ARTS[project["art"]](project, a2)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{shade(accent, -0.45)}"/>'
        f'<stop offset="1" stop-color="{a2 if project.get("accent2") else accent}"/>'
        '</linearGradient>'
        '<radialGradient id="l" cx=".5" cy=".42" r=".6">'
        '<stop offset="0" stop-color="#fff" stop-opacity=".18"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient></defs>'
        '<rect width="800" height="500" fill="url(#g)"/>'
        '<rect width="800" height="500" fill="url(#l)"/>'
        f"{body}</svg>"
    )
    name = f"{project['slug']}.svg"
    (PUBLIC / "img" / name).write_text(svg, encoding="utf-8")
    return f"img/{name}"


def render_favicon():
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
           '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
           '<stop offset="0" stop-color="#6d7dff"/><stop offset="1" stop-color="#e0533d"/>'
           '</linearGradient></defs>'
           '<rect width="64" height="64" rx="16" fill="url(#g)"/>'
           '<text x="32" y="44" text-anchor="middle" font-family="Arial, sans-serif" '
           'font-weight="800" font-size="34" fill="#fff">ים</text></svg>')
    (PUBLIC / "favicon.svg").write_text(svg, encoding="utf-8")


# ---------------------------------------------------------------- html

def render_card(p, statuses):
    if p.get("image"):
        srcset, src, w, h = render_image(p)
        cover = (f'<img src="{src}" srcset="{srcset}" sizes="{SIZES}" width="{w}" height="{h}" '
                 f'alt="{esc(p.get("alt", p["name"]))}" loading="lazy" decoding="async">')
    else:
        cover = (f'<img src="{render_art(p)}" width="800" height="500" alt="" '
                 'loading="lazy" decoding="async">')
    fit = " cover--contain" if p.get("fit") == "contain" else ""

    status = f'<span class="status status--{p["status"]}">{esc(statuses[p["status"]])}</span>'
    version = f'<span class="version" dir="ltr">v{esc(p["version"])}</span>' if p.get("version") else ""
    subtitle = f'<span class="sub">{esc(p["subtitle"])}</span>' if p.get("subtitle") else ""
    tech = "".join(f'<li dir="ltr">{esc(t)}</li>' for t in p.get("tech", []))
    highlights = "".join(f"<li>{prose(h)}</li>" for h in p.get("highlights", []))
    details = (f'<details><summary>עוד פרטים</summary><ul class="highlights">{highlights}</ul></details>'
               if highlights else "")
    links = "".join(
        f'<a class="btn" href="{esc(link["url"])}" target="_blank" rel="noopener">'
        f'{esc(link["label"])} <span aria-hidden="true">←</span></a>'
        for link in p.get("links", []))
    links = f'<div class="links">{links}</div>' if links else ""

    return f"""
      <article class="card" id="{esc(p['slug'])}" style="--card-accent: {esc(p['accent'])}">
        <div class="cover{fit}">{cover}</div>
        <div class="card-body">
          <div class="meta">{status}{version}</div>
          <h3>{esc(p['name'])}{subtitle}</h3>
          <p class="summary">{prose(p['summary'])}</p>
          <ul class="tech" aria-label="טכנולוגיות">{tech}</ul>
          {details}
          {links}
        </div>
      </article>"""


def build():
    data = json.loads((ROOT / "projects.json").read_text(encoding="utf-8"))
    owner, cats, statuses, projects = (
        data["owner"], data["categories"], data["statuses"], data["projects"])

    known = {c["id"] for c in cats}
    for p in projects:
        if p["category"] not in known:
            raise SystemExit(f"{p['slug']}: unknown category {p['category']!r}")
        if p["status"] not in statuses:
            raise SystemExit(f"{p['slug']}: unknown status {p['status']!r}")
        if not p.get("image") and p.get("art") not in ARTS:
            raise SystemExit(f"{p['slug']}: needs an image or one of the arts {sorted(ARTS)}")

    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    (PUBLIC / "img").mkdir(parents=True)
    shutil.copytree(ROOT / "fonts", PUBLIC / "fonts")
    shutil.copy(ROOT / "templates" / "site.css", PUBLIC / "site.css")
    render_favicon()
    if OG_IMAGE.exists():
        shutil.copy(OG_IMAGE, PUBLIC / "og.png")

    nav, sections = [], []
    for c in cats:
        items = [p for p in projects if p["category"] == c["id"]]
        if not items:
            continue
        nav.append(f'<a href="#{c["id"]}">{esc(c["label"])} <span class="count">{len(items)}</span></a>')
        cards = "".join(render_card(p, statuses) for p in items)
        sections.append(f"""
    <section class="category" id="{c['id']}" aria-labelledby="h-{c['id']}">
      <div class="category-head">
        <h2 id="h-{c['id']}">{esc(c['label'])}</h2>
        <p>{prose(c['blurb'])}</p>
      </div>
      <div class="grid">{cards}
      </div>
    </section>""")

    released = sum(p["status"] == "released" for p in projects)
    soon = sum(p["status"] == "soon" for p in projects)
    stats = "".join(
        f'<div><dt>{label}</dt><dd>{n}</dd></div>'
        for n, label in ((len(projects), "פרויקטים"), (released, "שוחררו לציבור"), (soon, "בקרוב"))
        if n)

    # Share previews, the canonical link and the sitemap need absolute URLs, so they wait for
    # site_url (https://<account>.github.io/) to be filled in projects.json.
    base = owner.get("site_url", "").strip().rstrip("/")
    base = base + "/" if base else ""
    share = ""
    if base:
        share = (f'\n  <link rel="canonical" href="{esc(base)}">'
                 f'\n  <meta property="og:url" content="{esc(base)}">')
        if (PUBLIC / "og.png").exists():
            share += (f'\n  <meta property="og:image" content="{esc(base)}og.png">'
                      f'\n  <meta property="og:image:width" content="{OG_SIZE[0]}">'
                      f'\n  <meta property="og:image:height" content="{OG_SIZE[1]}">'
                      f'\n  <meta property="og:image:alt" content="{esc(owner["title"])}">')

    today = datetime.date.today()
    page = string.Template((ROOT / "templates" / "index.html").read_text(encoding="utf-8")).substitute(
        title=esc(owner["title"]),
        description=esc(owner["lead"]),
        eyebrow=esc(owner["eyebrow"]),
        lead=prose(owner["lead"]),
        share=share,
        stats=stats,
        nav="".join(nav),
        sections="".join(sections),
        updated=today.strftime("%d.%m.%Y"),
    )
    (PUBLIC / "index.html").write_text(page, encoding="utf-8")

    not_found = string.Template((ROOT / "templates" / "404.html").read_text(encoding="utf-8"))
    (PUBLIC / "404.html").write_text(not_found.substitute(title=esc(owner["title"])), encoding="utf-8")

    robots = "User-agent: *\nAllow: /\n"
    if base:
        robots += f"Sitemap: {base}sitemap.xml\n"
        (PUBLIC / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"  <url><loc>{esc(base)}</loc><lastmod>{today.isoformat()}</lastmod></url>\n"
            "</urlset>\n", encoding="utf-8")
    (PUBLIC / "robots.txt").write_text(robots, encoding="utf-8")

    if not base:
        print("site_url is empty in projects.json: no share image, canonical link or sitemap yet")
    if not OG_IMAGE.exists():
        print("images/og.png is missing: run tools/og.py")

    files = sum(1 for f in PUBLIC.rglob("*") if f.is_file())
    size = sum(f.stat().st_size for f in PUBLIC.rglob("*") if f.is_file())
    print(f"public/: {len(projects)} projects, {files} files, {size / 1024:.0f} KB")


if __name__ == "__main__":
    build()
