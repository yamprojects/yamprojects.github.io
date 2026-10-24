"""Renders the share previews images/og.jpg (Hebrew) and images/og-en.jpg (English), 1200x630,
and the home-screen icons in images/icons/ (from the "ים" brand mark), with headless Chrome or Edge.

    python tools/og.py

Run it again when the projects or the title change; tools/build.py copies both images into
public/ (og.jpg and og-en.jpg), and each page points its og:image at its own. Pillow cannot lay
out Hebrew on this PC (no raqm), so a real browser draws templates/og.html instead, with the
fonts and the product screens inlined as data URIs.
"""

import base64
import json
import os
import string
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from build import (ICON_FILES, LANGS, OG_IMAGES, OG_SIZE, PUBLIC, ROOT, accent2, aurora_style, build, esc,
                   localize, render_screen, render_thumb)

BROWSERS = [
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft/Edge/Application/msedge.exe",
]
MIME = {".webp": "image/webp", ".png": "image/png", ".svg": "image/svg+xml", ".woff2": "font/woff2"}


def data_uri(path):
    return f"data:{MIME[path.suffix.lower()]};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def screen(p, kind):
    """The first screen of the first project with a device of this kind, as a data URI."""
    for project in p:
        device = project.get("device") or {}
        if device.get("type") == kind:
            _, name, _, _ = render_screen(device["screens"][0], kind)
            return data_uri(PUBLIC / "img" / name)
    return None


def icon(p):
    """The chip's picture: the app icon, a thumbnail of the project's picture, or its letter."""
    if p.get("image") and not p.get("device") and not p.get("icon"):
        thumb = PUBLIC / "img" / render_thumb(p["image"], p.get("crop"))
        return f'<img class="thumb" src="{data_uri(thumb)}" alt="">'
    for name in (f"icon-{p['slug']}.webp", f"icon-{p['slug']}.svg"):
        if (PUBLIC / "img" / name).exists():
            return f'<img src="{data_uri(PUBLIC / "img" / name)}" alt="">'
    return esc(p.get("glyph") or p["name"][0])


def page(data, lang):
    owner = localize(data["owner"], lang)
    projects = [localize(p, lang) for p in data["projects"]]
    devices = ""
    window, phone = screen(projects, "window"), screen(projects, "phone")
    if window:
        devices += f'<div class="window"><img src="{window}" alt=""></div>'
    if phone:
        devices += f'<div class="phone"><img src="{phone}" alt=""></div>'
    chips = ""
    for p in projects[:3]:
        picture = icon(p)
        thumb = " icon--thumb" if 'class="thumb"' in picture else ""
        chips += (f'<span class="chip" style="--a: {esc(p["accent"])}; --a2: {esc(accent2(p))}">'
                  f'<span class="icon{thumb}">{picture}</span>{esc(p["name"])}</span>')
    first, _, rest = owner["title"].partition(" ")
    title = f"{esc(first)}<br>{esc(rest)}" if rest else esc(first)
    return string.Template((ROOT / "templates" / "og.html").read_text(encoding="utf-8")).substitute(
        lang=lang,
        dir=LANGS[lang]["dir"],
        heebo=data_uri(ROOT / "fonts" / "heebo.woff2"),
        rubik=data_uri(ROOT / "fonts" / "rubik.woff2"),
        aurora=aurora_style(data["projects"]),
        eyebrow=esc(owner["eyebrow"]),
        title=title,
        lead=esc(owner["lead"]),
        devices=devices,
        chips=chips,
    )


def screenshot(browser, html, size):
    """Draws a page at size (w, h) and returns it as an RGB image."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp = Path(tmp)
        html_path, shot = tmp / "page.html", tmp / "page.png"
        html_path.write_text(html, encoding="utf-8")
        subprocess.run([
            str(browser), "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--no-first-run", "--force-device-scale-factor=1",
            f"--window-size={size[0]},{size[1]}", "--virtual-time-budget=3000",
            f"--user-data-dir={tmp / 'profile'}", f"--screenshot={shot}", html_path.as_uri(),
        ], check=True, capture_output=True, timeout=90)
        with Image.open(shot) as image:
            if image.size != tuple(size):
                raise SystemExit(f"the browser drew {image.size}, expected {size}")
            return image.convert("RGB")


def shoot(browser, html, out):
    screenshot(browser, html, OG_SIZE).save(out, "JPEG", quality=90, optimize=True, progressive=True,
                                            subsampling=0)


ICON_MASTER = 1024
ICON_PAGE = """<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><style>
  @font-face { font-family: 'Rubik'; src: url('$rubik') format('woff2'); font-weight: 300 900; }
  html, body { margin: 0; width: ${size}px; height: ${size}px; overflow: hidden; }
  body {
    display: grid;
    place-items: center;
    background:
      radial-gradient(80% 80% at 30% 20%, rgb(255 255 255 / .45), transparent 60%),
      linear-gradient(135deg, #7c5cff, #2f6bff 55%, #f0a13a);
  }
  b {
    color: #fff;
    font: 800 ${glyph}px/1 'Rubik', sans-serif;
    letter-spacing: -0.02em;
    text-shadow: 0 ${shadow}px ${blur}px rgb(20 10 70 / .28);
    translate: 0 -2%;
  }
</style></head><body><b>ים</b></body></html>"""


def render_icons(browser):
    """The home-screen icons: the brand mark drawn once large in the browser (Pillow cannot lay
    out Hebrew here), then scaled. "any" icons get round corners; the maskable one and the
    apple-touch icon stay square (the system shapes them), with the letters inside the safe zone."""
    rubik = data_uri(ROOT / "fonts" / "rubik.woff2")
    masters = {}
    for kind, glyph in (("any", .6), ("maskable", .42)):
        html = string.Template(ICON_PAGE).substitute(
            rubik=rubik, size=ICON_MASTER, glyph=round(ICON_MASTER * glyph),
            shadow=round(ICON_MASTER * .012), blur=round(ICON_MASTER * .04))
        masters[kind] = screenshot(browser, html, (ICON_MASTER, ICON_MASTER))
    out_dir = ROOT / "images" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, (size, kind, rounded) in ICON_FILES.items():
        im = masters[kind].resize((size, size), Image.LANCZOS)
        if rounded:
            from PIL import ImageDraw
            scale = 4
            mask = Image.new("L", (size * scale, size * scale), 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, size * scale - 1, size * scale - 1),
                                                   radius=round(size * scale * .28), fill=255)
            im = im.convert("RGBA")
            im.putalpha(mask.resize((size, size), Image.LANCZOS))
        im.save(out_dir / name, optimize=True)
        print(f"images/icons/{name}: {size}x{size}")


def main():
    browser = next((b for b in BROWSERS if b.exists()), None)
    if browser is None:
        raise SystemExit("needs Chrome or Edge for the screenshot")

    build()  # the previews use the screens and icons from public/img
    data = json.loads((ROOT / "projects.json").read_text(encoding="utf-8"))
    for lang, out in OG_IMAGES.items():
        shoot(browser, page(data, lang), out)
    render_icons(browser)

    build()  # copy the new images into public/
    for out in OG_IMAGES.values():
        print(f"{out.relative_to(ROOT)}: {out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
