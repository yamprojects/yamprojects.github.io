"""Renders the share previews images/og.jpg (Hebrew) and images/og-en.jpg (English), 1200x630,
with headless Chrome or Edge.

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

from build import (LANGS, OG_IMAGES, OG_SIZE, PUBLIC, ROOT, accent2, aurora_style, build, esc,
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


def shoot(browser, html, out):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp = Path(tmp)
        html_path, shot = tmp / "og.html", tmp / "og.png"
        html_path.write_text(html, encoding="utf-8")
        subprocess.run([
            str(browser), "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--no-first-run", "--force-device-scale-factor=1",
            f"--window-size={OG_SIZE[0]},{OG_SIZE[1]}", "--virtual-time-budget=3000",
            f"--user-data-dir={tmp / 'profile'}", f"--screenshot={shot}", html_path.as_uri(),
        ], check=True, capture_output=True, timeout=90)
        with Image.open(shot) as image:
            if image.size != OG_SIZE:
                raise SystemExit(f"the browser drew {image.size}, expected {OG_SIZE}")
            image.convert("RGB").save(out, "JPEG", quality=90, optimize=True, progressive=True,
                                      subsampling=0)


def main():
    browser = next((b for b in BROWSERS if b.exists()), None)
    if browser is None:
        raise SystemExit("needs Chrome or Edge for the screenshot")

    build()  # the previews use the screens and icons from public/img
    data = json.loads((ROOT / "projects.json").read_text(encoding="utf-8"))
    for lang, out in OG_IMAGES.items():
        shoot(browser, page(data, lang), out)

    build()  # copy the new images into public/
    for out in OG_IMAGES.values():
        print(f"{out.relative_to(ROOT)}: {out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
