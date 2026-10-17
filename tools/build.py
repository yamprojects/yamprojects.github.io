"""Builds the site into public/ from projects.json, templates/, images/ and fonts/.

    python tools/build.py

Everything in public/ is generated and gets wiped on every build: edit the sources and run this
again. Two pages come out of the same templates: Hebrew at public/index.html (the default, /) and
English at public/en/index.html (/en/). Every text in projects.json can have an English version in
an "en" object next to it (owner.en, categories[].en, statuses_en, projects[].en); the texts of the
page itself (buttons, labels, footer, 404) are in projects.json under "ui".

A project with a "device" gets its screens shown inside drawn phones or a desktop window (saved as
WebP at two widths). A picture in "image" (a screenshot or key art) is cropped to 16:10 and shown in
a glass frame, on cards without a device. A project with neither gets a drawn SVG
cover, chosen by its "art" field. The share images images/og.jpg and images/og-en.jpg come from
tools/og.py.
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
SIZES = "(min-width: 960px) 620px, (min-width: 760px) 46vw, 92vw"
OG_SIZE = (1200, 630)
OG_IMAGES = {"he": ROOT / "images" / "og.jpg", "en": ROOT / "images" / "og-en.jpg"}
OG_IMAGE = OG_IMAGES["he"]

# The two pages. "root" leads from the page back to the site root, for the assets.
LANGS = {
    "he": {"dir": "rtl", "locale": "he_IL", "path": "", "root": "", "og": "og.jpg"},
    "en": {"dir": "ltr", "locale": "en_US", "path": "en/", "root": "../", "og": "og-en.jpg"},
}

# Device screens: widths of the WebP files, their quality, and how wide each frame is drawn.
SCREEN_WIDTHS = {"phone": (360, 720), "window": (480, 700)}
SCREEN_QUALITY = {"phone": 86, "window": 90}
SCREEN_SIZES = {
    ("front", "phone"): "(min-width: 960px) 260px, 31vw",
    ("back", "phone"): "(min-width: 960px) 210px, 26vw",
    ("front", "window"): "(min-width: 960px) 480px, 76vw",
    ("back", "window"): "(min-width: 960px) 300px, 44vw",
    ("hero", "phone"): "(min-width: 980px) 190px, 40vw",
    ("hero", "window"): "(min-width: 980px) 460px, 76vw",
}
ICON_SIZE = 128
DISPLAY_FONT = "Rubik, Heebo, Arial, sans-serif"

# Surfaces from site.css, for picking accent shades that pass WCAG AA as text on them.
# The accent shades are checked against the brightest (dark theme) or darkest (light theme)
# background they can sit on: an accent-tinted pill on a tinted card over the aurora.
SURFACE_DARK = "#14121f"
SURFACE_LIGHT = "#f1eef8"
TINT_DARK, TARGET_DARK = .40, 4.8
TINT_LIGHT, TARGET_LIGHT = .30, 5.2
INK = "#14111f"


# ---------------------------------------------------------------- text

def esc(text):
    return html.escape(str(text), quote=True)


_LATIN_WORD = r"\.?[A-Za-z0-9](?:[A-Za-z0-9.,:#+_'’-]*[A-Za-z0-9#+])?"
LATIN_RUN = re.compile(rf"(?<![א-ת])(?P<pre>[א-ת]{{1,3}}-)?(?P<run>{_LATIN_WORD}(?::? {_LATIN_WORD})*)")
HEBREW_RUN = re.compile(r"[֐-׿]+(?:[ \-][֐-׿]+)*")


def prose(text, lang="he"):
    """Escapes body text and isolates the runs written in the other direction.

    In Hebrew every Latin or numeric run gets dir="ltr", and a Hebrew prefix glued to it ("ב-HTML")
    stays on one line with it. In English a Hebrew run gets lang="he" dir="rtl".
    """
    text = re.sub(r"(?<=\S) – (?=\d)", " – ", str(text))  # "– 7,330" never breaks apart
    out, last = [], 0
    if lang == "he":
        for m in LATIN_RUN.finditer(text):
            out.append(esc(text[last:m.start()]))
            # a short name of a few Latin words ("NARUTO: Ultimate Ninja STORM") stays on one line
            nowrap = ' class="nw"' if " " in m["run"] and len(m["run"]) <= 30 and not m["pre"] else ""
            run = f'<span dir="ltr"{nowrap}>{esc(m["run"])}</span>'
            out.append(f'<span class="nw">{esc(m["pre"])}{run}</span>' if m["pre"] else run)
            last = m.end()
    else:
        for m in HEBREW_RUN.finditer(text):
            out.append(esc(text[last:m.start()]))
            out.append(f'<span lang="he" dir="rtl">{esc(m[0])}</span>')
            last = m.end()
    out.append(esc(text[last:]))
    return "".join(out)


def other_dir(text, lang):
    """dir/lang attributes for a short label (a name, a chip) written in the other script."""
    if lang == "he" and not re.search(r"[א-ת]", text):
        return ' dir="ltr"'
    if lang == "en" and re.search(r"[א-ת]", text):
        return ' lang="he" dir="rtl"'
    return ""


def chip_dir(text, lang):
    """dir/lang for a tech chip: Latin chips are LTR on both pages, Hebrew ones RTL."""
    if not re.search(r"[א-ת]", text):
        return ' dir="ltr"'
    return ' lang="he" dir="rtl"' if lang == "en" else ""


def localize(item, lang):
    """The item with its English fields (item["en"]) laid over the Hebrew ones."""
    if lang == "he" or not isinstance(item.get(lang), dict):
        return dict(item)
    merged = dict(item)
    for key, value in item[lang].items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def arrow(direction):
    """A small drawn arrow: "fwd" points the way the text reads, "down" and "up" are vertical."""
    path = {"fwd": "M13 5l-7 7 7 7M6 12h13", "down": "M5 11l7 7 7-7M12 18V5",
            "up": "M5 13l7-7 7 7M12 6v13"}[direction]
    return (f'<svg class="arrow arrow--{direction}" viewBox="0 0 24 24" width="18" height="18" '
            f'aria-hidden="true" focusable="false"><path d="{path}" fill="none" stroke="currentColor" '
            'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def flag_badge(code, label):
    """A small glass badge with a flag (only Israel's is drawn so far: "flag": "il")."""
    if code != "il":
        raise SystemExit(f"unknown flag {code!r}: only \"il\" is drawn")
    star = "110,47 138.6,96.5 81.4,96.5Z M110,113 81.4,63.5 138.6,63.5Z"
    return (f'<span class="flag" role="img" aria-label="{esc(label)}" title="{esc(label)}">'
            '<svg viewBox="0 0 220 160" width="33" height="24" aria-hidden="true" focusable="false">'
            '<rect width="220" height="160" fill="#fff"/>'
            '<rect y="15" width="220" height="25" fill="#0038b8"/>'
            '<rect y="120" width="220" height="25" fill="#0038b8"/>'
            f'<path d="M{star}" fill="none" stroke="#0038b8" stroke-width="5.5" stroke-linejoin="miter"/>'
            '</svg></span>')


CUP = ('<svg class="cup" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">'
       '<g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
       '<path d="M4 10h12v4a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5z"/><path d="M16 11h1.5a2.5 2.5 0 0 1 0 5H16"/>'
       '<path d="M8 3.5c-.8 1 .8 2 0 3M12 3.5c-.8 1 .8 2 0 3"/></g></svg>')

ADS_CLIENT = re.compile(r"ca-pub-\d{16}")
ADS_POLICY = "https://policies.google.com/technologies/ads"


def donate_button(owner, lang, where):
    """The donation pill (Ko-fi), only once owner.donate.url is filled in."""
    donate = localize(owner.get("donate") or {}, lang)
    if not donate.get("url", "").strip():
        return ""
    return (f'<a class="donate donate--{where}" href="{esc(donate["url"].strip())}" target="_blank" '
            f'rel="noopener">{CUP}{esc(donate["label"])}</a>')


def ads_config(owner):
    """owner.ads: the AdSense publisher ID ("ca-pub-" and 16 digits) and optional slot IDs."""
    ads = owner.get("ads") or {}
    client = ads.get("client", "").strip()
    if client and not ADS_CLIENT.fullmatch(client):
        raise SystemExit(f"owner.ads.client must look like ca-pub-0000000000000000, not {client!r}")
    return client, {k: v.strip() for k, v in (ads.get("slots") or {}).items() if v and v.strip()}


def ad_slot(client, slot, ui, where):
    """A responsive ad unit in a labelled glass frame, with its height reserved."""
    return f"""
    <aside class="ad ad--{where}" aria-label="{esc(ui['ad'])}">
      <p class="ad-label">{esc(ui['ad'])}</p>
      <ins class="adsbygoogle" style="display:block" data-ad-client="{esc(client)}" data-ad-slot="{esc(slot)}" data-ad-format="auto" data-full-width-responsive="true"></ins>
      <script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
    </aside>"""


# ---------------------------------------------------------------- color

def luminance(hex_color):
    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(a, b, amount):
    """amount of color a over color b (both #rrggbb)."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x * amount + y * (1 - amount)):02x}" for x, y in zip(ca, cb))


def readable_on(accent, background, toward, target=4.6):
    """Shades the accent toward white (toward > 0) or black until it reads as text on background."""
    for step in range(0, 101, 2):
        color = shade(accent, toward * step / 100) if step else accent
        if contrast(color, background) >= target:
            return color
    return "#ffffff" if toward > 0 else "#000000"


def solid_button(accent):
    """A solid accent pill: the background, and the ink (dark or white) with the higher contrast.

    If neither reaches 4.5:1, the background is shaded away from the ink until it does."""
    ink = INK if contrast(INK, accent) >= contrast("#ffffff", accent) else "#ffffff"
    bg = accent
    for step in range(0, 101, 2):
        bg = shade(accent, (step if ink == INK else -step) / 100) if step else accent
        if contrast(ink, bg) >= 4.6:
            break
    return bg, ink


def accent_vars(p):
    """The card's colors: its accent, the CTA pill, and accent shades that read as text."""
    accent = p["accent"]
    a2 = accent2(p)
    bg, ink = solid_button(accent)
    dark = readable_on(accent, mix(accent, SURFACE_DARK, TINT_DARK), 1, TARGET_DARK)
    light = readable_on(accent, mix(accent, SURFACE_LIGHT, TINT_LIGHT), -1, TARGET_LIGHT)
    return (f"--card-accent: {accent}; --card-accent-2: {a2}; --cta-bg: {bg}; --cta-ink: {ink}; "
            f"--a-text-d: {dark}; --a-text-l: {light}")


# ---------------------------------------------------------------- images

def render_image(image, fit=None, crop=None):
    """Writes the 16:10 WebP sizes of a screenshot and returns (srcset, src, width, height)."""
    src = ROOT / "images" / image
    im = Image.open(src)
    im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
    contain = fit == "contain"
    if not contain:
        w, h = im.size
        if w / h > RATIO:
            nw = round(h * RATIO)
            im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = round(w / RATIO)
            top = 0 if crop == "top" else (h - nh) // 2
            im = im.crop((0, top, w, top + nh))
    out = []
    for width in WIDTHS:
        if contain:
            scaled = im.copy()
            scaled.thumbnail((width, round(width / RATIO)), Image.LANCZOS)
        else:
            scaled = im.resize((width, round(width / RATIO)), Image.LANCZOS)
        name = f"cover-{Path(image).stem}-{width}.webp"
        scaled.save(PUBLIC / "img" / name, "WEBP", quality=84, method=6)
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
    for ch in "אבגדהוזחטיכלמנסעפצקרשתאבגדהו":
        x, y = rng.randrange(20, 780), rng.randrange(60, 500)
        if 210 < x < 590 and 100 < y < 410:
            continue
        letters.append(
            f'<text x="{x}" y="{y}" font-size="{rng.randrange(36, 120)}" '
            f'opacity="{rng.uniform(.12, .34):.2f}" transform="rotate({rng.randrange(-18, 18)} {x} {y})">{ch}</text>')
    gid = f'{p["slug"]}-bubble'
    bubble = ("M290 132h220a44 44 0 0 1 44 44v118a44 44 0 0 1-44 44H398l-66 50v-50h-42"
              "a44 44 0 0 1-44-44V176a44 44 0 0 1 44-44z")
    return (f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#fff" stop-opacity=".34"/>'
            '<stop offset="1" stop-color="#fff" stop-opacity=".08"/></linearGradient>'
            f'<filter id="{gid}-blur" x="-30%" y="-30%" width="160%" height="160%">'
            '<feGaussianBlur stdDeviation="26"/></filter></defs>'
            f'<g fill="#fff" font-family="{DISPLAY_FONT}" font-weight="700">{"".join(letters)}</g>'
            f'<path d="{bubble}" fill="{a2}" opacity=".55" filter="url(#{gid}-blur)"/>'
            f'<path d="{bubble}" fill="url(#{gid})" stroke="#fff" stroke-opacity=".7" stroke-width="2"/>'
            '<path d="M300 133.5h200" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/>'
            f'<text x="400" y="262" text-anchor="middle" fill="#fff" font-family="{DISPLAY_FONT}" '
            'font-weight="800" font-size="70">עברית</text>')


ARTS = {
    "rings": art_rings, "wave3d": art_wave3d, "voice": art_voice, "agents": art_agents,
    "timing": art_timing, "waveform": art_waveform, "hex": art_hex, "chip": art_chip,
    "letters": art_letters,
}


def accent2(project):
    return project.get("accent2") or shade(project["accent"], 0.35)


def render_art(project):
    """Writes a drawn SVG cover to public/img and returns its markup, for inlining in the page."""
    accent = project["accent"]
    a2 = project.get("accent2") or shade(accent, -0.55)
    body = ARTS[project["art"]](project, a2)
    gid = project["slug"]
    glow = project.get("accent2") or shade(accent, 0.3)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" '
        'preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">'
        f'<defs><linearGradient id="{gid}-g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{shade(accent, -0.72)}"/>'
        f'<stop offset=".6" stop-color="{shade(accent, -0.42)}"/>'
        f'<stop offset="1" stop-color="{accent}"/>'
        '</linearGradient>'
        f'<radialGradient id="{gid}-a" cx=".88" cy=".05" r=".7">'
        f'<stop offset="0" stop-color="{glow}" stop-opacity=".85"/>'
        f'<stop offset="1" stop-color="{glow}" stop-opacity="0"/></radialGradient>'
        f'<radialGradient id="{gid}-b" cx=".08" cy="1" r=".75">'
        f'<stop offset="0" stop-color="{accent}" stop-opacity=".9"/>'
        f'<stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>'
        f'<radialGradient id="{gid}-l" cx=".5" cy=".45" r=".55">'
        '<stop offset="0" stop-color="#fff" stop-opacity=".16"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient></defs>'
        f'<rect width="800" height="500" fill="url(#{gid}-g)"/>'
        f'<rect width="800" height="500" fill="url(#{gid}-a)"/>'
        f'<rect width="800" height="500" fill="url(#{gid}-b)"/>'
        f'<rect width="800" height="500" fill="url(#{gid}-l)"/>'
        f"{body}</svg>"
    )
    (PUBLIC / "img" / f"{project['slug']}.svg").write_text(svg, encoding="utf-8")
    return svg


def render_favicon():
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
           '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
           '<stop offset="0" stop-color="#7c5cff"/><stop offset=".55" stop-color="#3b6cff"/>'
           '<stop offset="1" stop-color="#f0a13a"/></linearGradient>'
           '<radialGradient id="l" cx=".3" cy=".2" r=".8"><stop offset="0" stop-color="#fff" '
           'stop-opacity=".45"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient></defs>'
           '<rect width="64" height="64" rx="18" fill="url(#g)"/>'
           '<rect width="64" height="64" rx="18" fill="url(#l)"/>'
           '<text x="32" y="44" text-anchor="middle" font-family="Arial, sans-serif" '
           'font-weight="800" font-size="34" fill="#fff">ים</text></svg>')
    (PUBLIC / "favicon.svg").write_text(svg, encoding="utf-8")



def render_thumb(image, crop=None, width=160):
    """A small 16:10 thumbnail of a picture (for the hero tag and the share image chips)."""
    name = f"thumb-{Path(image).stem}-{width}.webp"
    if not (PUBLIC / "img" / name).exists():
        with Image.open(ROOT / "images" / image) as im:
            im = im.convert("RGB")
            w, h = im.size
            if w / h > RATIO:
                nw = round(h * RATIO)
                im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
            else:
                nh = round(w / RATIO)
                top = 0 if crop == "top" else (h - nh) // 2
                im = im.crop((0, top, w, top + nh))
            im.resize((width, round(width / RATIO)), Image.LANCZOS).save(
                PUBLIC / "img" / name, "WEBP", quality=84, method=6)
    return name


# ---------------------------------------------------------------- devices and icons

_screens = {}


def render_screen(file, kind):
    """Writes the WebP sizes of one device screen once and returns ([(name, w)], name, w, h)."""
    if (file, kind) in _screens:
        return _screens[file, kind]
    src = ROOT / "images" / file
    im = Image.open(src)
    im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
    stem = Path(file).stem
    out = []
    for width in SCREEN_WIDTHS[kind]:
        width = min(width, im.width)
        if out and out[-1][1][0] == width:
            continue
        scaled = im if width == im.width else im.resize(
            (width, round(im.height * width / im.width)), Image.LANCZOS)
        name = f"screen-{stem}-{width}.webp"
        scaled.save(PUBLIC / "img" / name, "WEBP", quality=SCREEN_QUALITY[kind], method=6)
        out.append((name, scaled.size))
    name, (w, h) = out[-1]
    _screens[file, kind] = ([(n, s[0]) for n, s in out], name, w, h)
    return _screens[file, kind]


def screen_img(file, kind, slot, root, alt="", loading='loading="lazy"'):
    files, name, w, h = render_screen(file, kind)
    srcset = ", ".join(f"{root}img/{n} {width}w" for n, width in files)
    return (f'<img src="{root}img/{name}" srcset="{srcset}" sizes="{SCREEN_SIZES[slot, kind]}" '
            f'width="{w}" height="{h}" alt="{esc(alt)}" {loading} decoding="async">')


SLOTS = ("front", "back", "back2")


def render_device(p, root, count):
    """The project's screens inside phones or desktop windows; the first screen sits in front."""
    device = p["device"]
    kind = device["type"]
    parts = []
    for i, file in enumerate(device["screens"][:count]):
        slot = SLOTS[i]
        alt = (device.get("alt") or p.get("alt") or p["name"]) if i == 0 else ""
        img = screen_img(file, kind, "front" if i == 0 else "back", root, alt)
        parts.append(f'<div class="{kind} {kind}--{slot}">{img}</div>')
    return "".join(reversed(parts))


def render_icon(p, root, loading="lazy"):
    """The project's app icon, or its first letter on a glowing tile when it has none."""
    icon = p.get("icon")
    if not icon:
        glyph = p.get("glyph") or p["name"][0]
        return f'<span class="app-icon app-icon--glyph" aria-hidden="true">{esc(glyph)}</span>'
    src = ROOT / "images" / icon
    if src.suffix.lower() == ".svg":
        name = f"icon-{p['slug']}.svg"
        if not (PUBLIC / "img" / name).exists():
            shutil.copy(src, PUBLIC / "img" / name)
    else:
        name = f"icon-{p['slug']}.webp"
        if not (PUBLIC / "img" / name).exists():
            with Image.open(src) as im:
                im = im.convert("RGBA")
                im.thumbnail((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
                im.save(PUBLIC / "img" / name, "WEBP", quality=86, method=6)
    return (f'<span class="app-icon"><img src="{root}img/{name}" width="48" height="48" alt="" '
            f'loading="{loading}" decoding="async"></span>')


def status_badge(p, statuses, ui, sr=True):
    prefix = f'<span class="sr">{esc(ui["status"])} </span>' if sr else ""
    return f'<span class="status status--{p["status"]}">{prefix}{esc(statuses[p["status"]])}</span>'


def render_showcase(projects, statuses, ui, root, lang):
    """The floating composition beside the headline: one window, one phone and a few glass tags."""
    def first(kind):
        return next((p for p in projects if p.get("device", {}).get("type") == kind), None)

    window, phone = first("window"), first("phone")
    if not window and not phone:
        return ""
    layout = "both" if window and phone else ("window" if window else "phone")
    shown = [p for p in (window, phone) if p]
    extra = next((p for p in projects if p not in shown), None)

    items = []
    for p in shown:
        kind = p["device"]["type"]
        # The window is left out on phones (display: none), so it waits for layout before loading.
        loading = 'loading="eager" fetchpriority="high"' if kind == "phone" else 'loading="lazy"'
        img = screen_img(p["device"]["screens"][0], kind, "hero", root, "", loading)
        items.append(f'<div class="sc sc-{kind}" style="--card-accent: {esc(p["accent"])}">'
                     f'<div class="{kind} {kind}--front">{img}</div></div>')
    tags = []
    for slot, p in (("window", window), ("phone", phone), ("extra", extra)):
        if not p:
            continue
        version = f' <span dir="ltr">v{esc(p["version"])}</span>' if p.get("version") else ""
        if p.get("image") and not p.get("device") and not p.get("icon"):
            name = render_thumb(p["image"], p.get("crop"))
            thumb = (f'<span class="sc-thumb"><img src="{root}img/{name}" '
                     f'width="160" height="100" alt="" loading="lazy" decoding="async"></span>')
        else:
            thumb = render_icon(p, root, "eager")
        tags.append(
            f'<div class="sc-tag sc-tag--{slot}" style="--card-accent: {esc(p["accent"])}">'
            f'{thumb}<span class="sc-tag-text">'
            f'<b{other_dir(p["name"], lang)}>{esc(p["name"])}</b>'
            f'<small>{status_badge(p, statuses, ui, sr=False)}{version}</small></span></div>')
    return (f'\n      <div class="showcase showcase--{layout}" aria-hidden="true">'
            f'<div class="sc-halo"></div>{"".join(items)}{"".join(tags)}</div>')


# ---------------------------------------------------------------- cards

def render_stage(p, root, feature, ui):
    """The top (or side) of a card: device frames, a framed screenshot or a drawn cover."""
    if p.get("device"):
        kind = p["device"]["type"]
        count = 3 if feature and kind == "phone" else 2
        return (f'<div class="stage stage--{kind} stage--n{min(count, len(p["device"]["screens"]))}">'
                f'{render_device(p, root, count)}</div>'), kind
    if p.get("image"):
        srcset, src, w, h = render_image(p["image"], p.get("fit"), p.get("crop"))
        srcset = ", ".join(f"{root}{part}" for part in srcset.split(", "))
        contain = " stage--contain" if p.get("fit") == "contain" else ""
        img = (f'<img src="{root}{src}" srcset="{srcset}" sizes="{SIZES}" width="{w}" height="{h}" '
               f'alt="{esc(p.get("alt", p["name"]))}" loading="lazy" decoding="async">')
        flag = flag_badge(p["flag"], ui[f"flag_{p['flag']}"]) if p.get("flag") else ""
        return (f'<div class="stage stage--shot{contain}"><div class="shot">{img}{flag}</div></div>'), "shot"
    return f'<div class="stage stage--art">{render_art(p)}</div>', "art"


def render_card(p, statuses, ui, root, lang, feature, flip):
    stage, kind = render_stage(p, root, feature, ui)

    version = f'<span class="version" dir="ltr">v{esc(p["version"])}</span>' if p.get("version") else ""
    subtitle = (f'<span class="sub"{other_dir(p["subtitle"], lang)}>{esc(p["subtitle"])}</span>'
                if p.get("subtitle") else "")
    kicker = f'<p class="kicker">{esc(p["kicker"])}</p>' if p.get("kicker") else ""
    tech = "".join(f'<li{chip_dir(t, lang)}>{esc(t)}</li>' for t in p.get("tech", []))
    tech = f'<ul class="tech" aria-label="{esc(ui["tech"])}">{tech}</ul>' if tech else ""

    def items(points, start):
        return "".join(
            f'<li><span class="hl-num" dir="ltr" aria-hidden="true">{i:02d}</span>'
            f'<span class="hl-text">{prose(h, lang)}</span></li>'
            for i, h in enumerate(points, start=start))

    points = p.get("highlights", [])
    shown, more = points[:2], points[2:]
    highlights = (f'<ol class="highlights" aria-label="{esc(ui["highlights"])}">{items(shown, 1)}</ol>'
                  if shown else "")
    details = (f'<details><summary>{esc(ui["more"])}</summary>'
               f'<ol class="highlights" start="3">{items(more, 3)}</ol></details>' if more else "")
    def button(link):
        hreflang = f' hreflang="{esc(link["hreflang"])}"' if link.get("hreflang") else ""
        return (f'<a class="btn btn--accent" href="{esc(link["url"])}" target="_blank" '
                f'rel="noopener"{hreflang}>{esc(link["label"])} {arrow("fwd")}</a>')

    links = "".join(button(link) for link in p.get("links", []))
    links = f'<div class="links">{links}</div>' if links else ""

    classes = f"card card--{kind}" + (" card--feature" if feature else "") + (" card--flip" if flip else "")
    name_dir = other_dir(p["name"], lang)
    return f"""
        <article class="{classes}" id="{esc(p['slug'])}" aria-labelledby="t-{esc(p['slug'])}" style="{accent_vars(p)}">
          {stage}
          <div class="card-body">
            <div class="card-top">{render_icon(p, root)}<div class="meta">{status_badge(p, statuses, ui)}{version}</div></div>
            <div class="card-title">
              {kicker}
              <h3 id="t-{esc(p['slug'])}"><span{name_dir}>{esc(p['name'])}</span>{subtitle}</h3>
            </div>
            <p class="summary">{prose(p['summary'], lang)}</p>
            {highlights}
            {details}
            {tech}
            {links}
          </div>
        </article>"""


def aurora_style(projects):
    """The page backdrop is lit by the projects' own colors (up to four of them)."""
    accents = []
    for p in projects:
        if p["accent"].lower() not in accents:
            accents.append(p["accent"].lower())
    return "; ".join(f"--au{i}: {esc(a)}" for i, a in enumerate(accents[:4], start=1))


def long_date(day, lang):
    if lang == "he":
        return day.strftime("%d.%m.%Y")
    return f"{day.day} {day:%b} {day.year}"


# ---------------------------------------------------------------- pages

def render_page(data, lang, base, today):
    conf = LANGS[lang]
    root = conf["root"]
    ui = data["ui"][lang]
    owner = localize(data["owner"], lang)
    statuses = data["statuses"] if lang == "he" else {**data["statuses"], **data.get("statuses_en", {})}
    cats = [localize(c, lang) for c in data["categories"]]
    projects = [localize(p, lang) for p in data["projects"]]

    showcase = render_showcase(projects, statuses, ui, root, lang)

    nav, sections, index = [], [], []
    features = 0
    for c in cats:
        items = [p for p in projects if p["category"] == c["id"]]
        if not items:
            continue
        number = len(sections) + 1
        nav.append(f'<a href="#{c["id"]}">{esc(c["label"])} '
                   f'<span class="count" dir="ltr">{len(items)}</span></a>')
        # The first project of a category is featured across the whole row, and so is a last one
        # that would otherwise be alone on its row. Featured cards alternate their sides.
        cards = []
        for i, p in enumerate(items):
            feature = i == 0 or (i == len(items) - 1 and (len(items) - 1) % 2 == 1)
            flip = feature and features % 2 == 1
            features += feature
            cards.append(render_card(p, statuses, ui, root, lang, feature, flip))
            index.append(
                f'<li><a href="#{esc(p["slug"])}" style="{accent_vars(p)}">'
                f'<span class="index-num" dir="ltr">{len(index) + 1:02d}</span>'
                f'<span class="index-name"{other_dir(p["name"], lang)}>{esc(p["name"])}</span>'
                f'<span class="index-meta">{esc(c["label"])} · '
                f'<span class="sr">{esc(ui["status"])} </span>{esc(statuses[p["status"]])}</span></a></li>')
        sections.append(f"""
    <section class="category" id="{c['id']}" aria-labelledby="h-{c['id']}">
      <div class="category-head">
        <span class="category-num" dir="ltr" aria-hidden="true">{number:02d}</span>
        <div class="category-title">
          <h2 id="h-{c['id']}">{esc(c['label'])}</h2>
          <p>{prose(c['blurb'], lang)}</p>
        </div>
      </div>
      <div class="grid">{"".join(cards)}
      </div>
    </section>""")

    client, slots = ads_config(data["owner"])
    if client and slots.get("between") and len(sections) > 1:
        sections.insert(1, ad_slot(client, slots["between"], ui, "between"))
    ad_end = ad_slot(client, slots["footer"], ui, "end") if client and slots.get("footer") else ""

    released = sum(p["status"] == "released" for p in projects)
    soon = sum(p["status"] == "soon" for p in projects)
    stats = "".join(
        f'<div><dt>{esc(label)}</dt><dd dir="ltr">{n}</dd></div>'
        for n, label in ((len(projects), ui["stat_projects"]), (released, ui["stat_released"]),
                         (soon, ui["stat_soon"]))
        if n)

    # Share previews, canonical links and the sitemap need absolute URLs (owner.site_url).
    url = base + conf["path"]
    head = ""
    if base:
        head += f'\n  <link rel="canonical" href="{esc(url)}">'
        for code, other in LANGS.items():
            head += f'\n  <link rel="alternate" hreflang="{code}" href="{esc(base + other["path"])}">'
        head += f'\n  <link rel="alternate" hreflang="x-default" href="{esc(base)}">'
        head += f'\n  <meta property="og:url" content="{esc(url)}">'
        if (PUBLIC / conf["og"]).exists():
            head += (f'\n  <meta property="og:image" content="{esc(base + conf["og"])}">'
                     f'\n  <meta property="og:image:width" content="{OG_SIZE[0]}">'
                     f'\n  <meta property="og:image:height" content="{OG_SIZE[1]}">'
                     f'\n  <meta property="og:image:alt" content="{esc(ui.get("og_alt") or owner["title"])}">')
    for code, other in LANGS.items():
        if code != lang:
            head += f'\n  <meta property="og:locale:alternate" content="{other["locale"]}">'
    ads_head = ""
    if client:
        ads_head = ('\n  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
                    f'?client={esc(client)}" crossorigin="anonymous"></script>')
    footer = ui["footer_ads"] if client else ui["footer"]
    privacy = (f'<p class="foot-privacy"><a href="{ADS_POLICY}" target="_blank" rel="noopener">'
               f'{esc(ui["ads_privacy"])}</a></p>' if client else "")
    video = ""
    if (PUBLIC / "video").is_dir():
        # Decorative motion behind the page: the poster comes from site.css, the sources from site.js.
        video = (f'\n  <div class="bg-video" aria-hidden="true" data-base="{root}video/">'
                 '<video muted loop playsinline preload="none" disablepictureinpicture tabindex="-1">'
                 '</video></div>')

    other = "en" if lang == "he" else "he"
    switch_href = "en/" if lang == "he" else "../"
    words = esc(owner["title"]).rsplit(" ", 1)
    headline = "&nbsp;".join(words) if len(owner["title"].split()) > 2 else esc(owner["title"])

    page = string.Template((ROOT / "templates" / "index.html").read_text(encoding="utf-8")).substitute(
        lang=lang,
        dir=conf["dir"],
        root=root,
        locale=conf["locale"],
        title=esc(owner["title"]),
        headline=headline,  # never a lone last word
        description=esc(owner["lead"]),
        eyebrow=esc(owner["eyebrow"]),
        lead=prose(owner["lead"], lang),
        head=head,
        aurora=aurora_style(projects),
        hero_class="hero--showcase" if showcase else "hero--solo",
        showcase=showcase,
        stats=stats,
        index="".join(index),
        index_class=" index--two" if len(index) > 6 else "",
        nav="".join(nav),
        sections="".join(sections),
        switch_href=switch_href,
        switch_lang=other,
        switch_dir=LANGS[other]["dir"],
        switch_label=esc(ui["lang_switch"]),
        switch_short=esc(ui.get("lang_short", ui["lang_switch"])),
        motion_label=esc(ui["motion"]),
        skip=esc(ui["skip"]),
        nav_label=esc(ui["nav"]),
        home_label=esc(ui["home"]),
        cats_label=esc(ui["categories_nav"]),
        cta=esc(ui["cta"]),
        down=arrow("down"),
        up=arrow("up"),
        index_label=esc(ui["index"]),
        footer=prose(footer, lang),
        privacy=privacy,
        ads_head=ads_head,
        ad_end=ad_end,
        video=video,
        donate_hero=donate_button(data["owner"], lang, "hero"),
        donate_foot=donate_button(data["owner"], lang, "foot"),
        updated_label=esc(ui["updated"]),
        updated=long_date(today, lang),
        updated_iso=today.isoformat(),
        back_to_top=esc(ui["back_to_top"]),
    )
    out = PUBLIC / conf["path"] / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")


def render_not_found(data):
    """One 404 page for both languages (GitHub Pages serves it at any missing URL)."""
    he, en = data["ui"]["he"], data["ui"]["en"]
    owner = data["owner"]
    page = string.Template((ROOT / "templates" / "404.html").read_text(encoding="utf-8")).substitute(
        title=esc(owner["title"]),
        title_en=esc(localize(owner, "en")["title"]),
        aurora=aurora_style(data["projects"]),
        video='<div class="bg-video" aria-hidden="true"></div>' if (PUBLIC / "video").is_dir() else "",
        he_title=esc(he["404_title"]), he_body=esc(he["404_body"]), he_home=esc(he["404_home"]),
        en_title=esc(en["404_title"]), en_body=esc(en["404_body"]), en_home=esc(en["404_home"]),
        fwd=arrow("fwd"),
    )
    (PUBLIC / "404.html").write_text(page, encoding="utf-8")


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
        device = p.get("device")
        if device and (device.get("type") not in SCREEN_WIDTHS or not device.get("screens")):
            raise SystemExit(f"{p['slug']}: a device needs a type ({sorted(SCREEN_WIDTHS)}) and screens")
        if not device and not p.get("image") and p.get("art") not in ARTS:
            raise SystemExit(f"{p['slug']}: needs a device, an image or one of the arts {sorted(ARTS)}")
    for lang in LANGS:
        if lang not in data.get("ui", {}):
            raise SystemExit(f"projects.json: the page texts for {lang!r} are missing under ui")

    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    (PUBLIC / "img").mkdir(parents=True)
    _screens.clear()
    shutil.copytree(ROOT / "fonts", PUBLIC / "fonts")
    shutil.copy(ROOT / "templates" / "site.css", PUBLIC / "site.css")
    shutil.copy(ROOT / "templates" / "site.js", PUBLIC / "site.js")
    if (ROOT / "videos").is_dir():
        shutil.copytree(ROOT / "videos", PUBLIC / "video")
    render_favicon()
    for lang, image in OG_IMAGES.items():
        if image.exists():
            shutil.copy(image, PUBLIC / LANGS[lang]["og"])

    base = owner.get("site_url", "").strip().rstrip("/")
    base = base + "/" if base else ""
    today = datetime.date.today()
    for lang in LANGS:
        render_page(data, lang, base, today)
    render_not_found(data)

    robots = "User-agent: *\nAllow: /\n"
    if base:
        robots += f"Sitemap: {base}sitemap.xml\n"
        alternates = "".join(
            f'\n    <xhtml:link rel="alternate" hreflang="{code}" href="{esc(base + conf["path"])}"/>'
            for code, conf in LANGS.items())
        alternates += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{esc(base)}"/>'
        urls = "".join(
            f"  <url>\n    <loc>{esc(base + conf['path'])}</loc>\n    <lastmod>{today.isoformat()}</lastmod>"
            f"{alternates}\n  </url>\n" for conf in LANGS.values())
        (PUBLIC / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            f"{urls}</urlset>\n", encoding="utf-8")
    (PUBLIC / "robots.txt").write_text(robots, encoding="utf-8")

    client, _ = ads_config(owner)
    if client:
        (PUBLIC / "ads.txt").write_text(
            f"google.com, {client.removeprefix('ca-')}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")

    if not base:
        print("site_url is empty in projects.json: no share image, canonical links or sitemap yet")
    for image in OG_IMAGES.values():
        if not image.exists():
            print(f"{image.relative_to(ROOT)} is missing: run tools/og.py")

    files = sum(1 for f in PUBLIC.rglob("*") if f.is_file())
    size = sum(f.stat().st_size for f in PUBLIC.rglob("*") if f.is_file())
    print(f"public/: {len(projects)} projects in {len(LANGS)} languages, {files} files, {size / 1024:.0f} KB")


if __name__ == "__main__":
    build()
