import logging
import os
from pathlib import Path


def _configure_macos_library_paths() -> None:
    if os.name != "posix":
        return
    candidates = [
        "/opt/homebrew/opt/glib/lib",
        "/opt/homebrew/opt/pango/lib",
        "/opt/homebrew/opt/cairo/lib",
        "/opt/homebrew/lib",
        "/usr/local/opt/glib/lib",
        "/usr/local/opt/pango/lib",
        "/usr/local/opt/cairo/lib",
        "/usr/local/lib",
    ]
    existing = [path for path in candidates if os.path.isdir(path)]
    if not existing:
        return
    current = [part for part in os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "").split(":") if part]
    merged: list[str] = []
    for path in existing + current:
        if path not in merged:
            merged.append(path)
    os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join(merged)


_configure_macos_library_paths()
logging.getLogger("weasyprint").setLevel(logging.ERROR)
logging.getLogger("fonttools").setLevel(logging.ERROR)

import weasyprint

CSS_PATH = Path(__file__).parent / "style.css"


def build_full_html(chapters_html: list[str], cover_html: str = "") -> str:
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        f'  <link rel="stylesheet" href="{CSS_PATH.as_uri()}">',
        "</head>",
        "<body>",
    ]
    if cover_html:
        parts.append(cover_html)
    for index, chapter_html in enumerate(chapters_html):
        css_class = "chapter-break" if index > 0 else ""
        parts.append(f'<div class="chapter {css_class}">')
        parts.append(chapter_html)
        parts.append("</div>")
    parts.extend(["</body>", "</html>"])
    return "\n".join(parts)


def render_pdf(full_html: str, output_path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    base_url = Path(__file__).parent.as_uri() + "/"
    weasyprint.HTML(string=full_html, base_url=base_url).write_pdf(output_path)
