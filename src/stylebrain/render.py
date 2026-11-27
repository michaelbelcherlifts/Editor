"""Render an HTML animation to video, frame by frame, with transparency.

An animation is one HTML page. The renderer opens it in a headless browser,
pauses every CSS and Web Animations API animation, steps time forward one
frame at a time, and screenshots each frame. ffmpeg joins the frames into a
ProRes 4444 .mov with an alpha channel, which Resolve places over footage.

Pages that animate with JavaScript instead of CSS can define
`window.seek = (seconds) => {...}`; it is called before every frame.

Needs the `render` extra (playwright) and a Chromium. Set STYLEBRAIN_CHROMIUM
to a browser binary to use that one; otherwise playwright's own is used
(`uv run playwright install chromium`).
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .edl import EditError

_SEEK = """(ms) => {
  for (const a of document.getAnimations()) { a.pause(); a.currentTime = ms; }
  if (typeof window.seek === 'function') window.seek(ms / 1000);
}"""

_PRESEEDED = "/opt/pw-browsers/chromium"


@dataclass(frozen=True)
class Rendered:
    path: str
    frames: int
    fps: float
    width: int
    height: int

    @property
    def duration(self) -> float:
        return self.frames / self.fps


def _browser(p):
    exe = os.environ.get("STYLEBRAIN_CHROMIUM") or (_PRESEEDED if os.path.exists(_PRESEEDED) else None)
    try:
        return p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    except Exception as e:  # playwright raises its own Error type
        raise EditError(f"could not start the browser ({e}); run `uv run playwright install chromium`") from None


def render_html(html: str, out: str | Path, duration: float, fps: float = 30.0,
                width: int = 1920, height: int = 1080, transparent: bool = True) -> Rendered:
    """Render HTML text to `out`. Transparent renders must end in .mov."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise EditError("rendering needs playwright; run `uv sync --all-extras`") from None
    out = Path(out)
    if transparent and out.suffix.lower() != ".mov":
        raise EditError("transparent renders are ProRes 4444; use a .mov file name")
    frames = max(1, round(duration * fps))
    out.parent.mkdir(parents=True, exist_ok=True)
    codec = (["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0"]
             if transparent else ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16"])
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", f"{fps}",
                           "-c:v", "png", "-i", "-", *codec, "-r", f"{fps}", str(out)],
                          stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        with sync_playwright() as p:
            browser = _browser(p)
            page = browser.new_page(viewport={"width": width, "height": height})
            page.set_content(html, wait_until="load")
            page.evaluate("document.fonts.ready")
            for n in range(frames):
                page.evaluate(_SEEK, n * 1000.0 / fps)
                ff.stdin.write(page.screenshot(omit_background=transparent, type="png"))
            browser.close()
    except BrokenPipeError:
        pass
    finally:
        ff.stdin.close()
        err = ff.stderr.read().decode(errors="replace")
        code = ff.wait()
    if code != 0:
        raise EditError(f"ffmpeg could not write {out}: {err.strip()[-400:]}")
    return Rendered(str(out), frames, fps, width, height)
