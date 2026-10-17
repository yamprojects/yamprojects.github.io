"""Renders the share preview images/og.png (1200x630) with headless Chrome or Edge.

    python tools/og.py

Run it again when the projects or the title change; tools/build.py copies the image into public/.
Pillow cannot lay out Hebrew on this PC (no raqm), so a real browser draws templates/og.html
instead, with the font and the first three covers inlined as data URIs.
"""

import base64
import json
import os
import string
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from build import OG_IMAGE, OG_SIZE, PUBLIC, ROOT, build, esc

BROWSERS = [
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft/Edge/Application/msedge.exe",
]


def data_uri(path, mime):
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def cover(project):
    """The cover build.py made for a project, as a data URI."""
    if project.get("image"):
        return data_uri(PUBLIC / "img" / f"{project['slug']}-960.webp", "image/webp")
    return data_uri(PUBLIC / "img" / f"{project['slug']}.svg", "image/svg+xml")


def main():
    browser = next((b for b in BROWSERS if b.exists()), None)
    if browser is None:
        raise SystemExit("needs Chrome or Edge for the screenshot")

    build()  # the preview shows the covers from public/img
    data = json.loads((ROOT / "projects.json").read_text(encoding="utf-8"))
    owner = data["owner"]
    cards = "".join(
        f'<figure class="shot shot-{i}{" contain" if p.get("fit") == "contain" else ""}" '
        f'style="--accent: {esc(p["accent"])}"><img src="{cover(p)}" alt="">'
        f'<figcaption>{esc(p["name"])}</figcaption></figure>'
        for i, p in enumerate(data["projects"][:3], start=1))

    page = string.Template((ROOT / "templates" / "og.html").read_text(encoding="utf-8")).substitute(
        font=data_uri(ROOT / "fonts" / "heebo.woff2", "font/woff2"),
        eyebrow=esc(owner["eyebrow"]),
        title=esc(owner["title"]),
        lead=esc(owner["lead"]),
        cards=cards,
    )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp = Path(tmp)
        html_path, shot = tmp / "og.html", tmp / "og.png"
        html_path.write_text(page, encoding="utf-8")
        subprocess.run([
            str(browser), "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--no-first-run", "--force-device-scale-factor=1",
            f"--window-size={OG_SIZE[0]},{OG_SIZE[1]}", "--virtual-time-budget=3000",
            f"--user-data-dir={tmp / 'profile'}", f"--screenshot={shot}", html_path.as_uri(),
        ], check=True, capture_output=True, timeout=90)
        with Image.open(shot) as image:
            if image.size != OG_SIZE:
                raise SystemExit(f"the browser drew {image.size}, expected {OG_SIZE}")
            image.convert("RGB").save(OG_IMAGE, optimize=True)

    build()  # copy the new image into public/
    print(f"{OG_IMAGE.relative_to(ROOT)}: {OG_IMAGE.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
