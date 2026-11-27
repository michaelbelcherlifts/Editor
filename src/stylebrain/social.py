"""Stills for Instagram and YouTube: photo edits, carousels, covers and stories.

Everything is drawn as an HTML page and saved as one screenshot, with the same
browser the animation renderer uses, so text looks like his video captions.
Photos and video frames are prepared with ffmpeg first: cropped to the size,
and given a colour look from `library/looks/` when one is named.

One reel becomes a package (`package`): a carousel draft built from what was
said, three cover options, and three story suggestions with drafts. The plan
files are JSON so Claude or Michael can rewrite the words and render again.
Nothing here posts anything.

Text marked *like this* is drawn in the accent colour.
"""

from __future__ import annotations

import base64
import json
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

from .edl import EditError
from .media import info, run
from .transcript import Word

FONT = "'Inter','SF Pro Display','Helvetica Neue','Segoe UI',Arial,sans-serif"


@dataclass(frozen=True)
class Size:
    """A platform size, with the box text must stay inside (x, y, w, h in pixels)."""

    name: str
    width: int
    height: int
    safe: tuple[int, int, int, int]
    about: str


# Safe boxes leave room for the app's own buttons and crops:
# feed and carousel posts are cut to 3:4 in the profile grid (about 34 px off each side);
# stories have the profile bar on top and the reply box at the bottom;
# a reel cover shows whole when opened but only its middle 3:4 in the profile grid;
# YouTube puts the length badge in the bottom right corner of a thumbnail.
SIZES = {
    "portrait": Size("portrait", 1080, 1350, (90, 90, 900, 1170), "feed post or carousel slide, 4:5"),
    "square": Size("square", 1080, 1080, (90, 90, 900, 900), "square feed post, 1:1"),
    "story": Size("story", 1080, 1920, (72, 250, 936, 1330), "story, 9:16"),
    "cover": Size("cover", 1080, 1920, (100, 300, 880, 1320), "reel cover, 9:16, title inside the 3:4 grid crop"),
    "thumbnail": Size("thumbnail", 1280, 720, (64, 48, 1152, 560), "YouTube thumbnail, 16:9"),
}

BRAND_DEFAULTS = {"handle": "", "site": "", "accent": "#ffe14a", "text": "#ffffff", "dark": "#0e0f12"}
MAX_SLIDES = 20     # Instagram's limit for one carousel
MIN_FONT = 40       # below this, a slide has too many words to read on a phone


def size(name: str) -> Size:
    if name not in SIZES:
        raise EditError(f"no size named {name!r}; there are: {', '.join(SIZES)}")
    return SIZES[name]


def brand(base: str | Path = ".") -> dict:
    """Handle, site and colours from library/social/brand.json, over the defaults."""
    path = Path(base) / "library" / "social" / "brand.json"
    out = dict(BRAND_DEFAULTS)
    if path.exists():
        out.update(json.loads(path.read_text()))
    return out


# ---------- pictures -------------------------------------------------------------------------------

def _lut(look: str | Path | None, base: str | Path = ".") -> str:
    if not look:
        return ""
    from .look import _lut_filter, find
    path = Path(look) if str(look).endswith(".cube") else find(str(look), base)
    return "," + _lut_filter(path)


def parse_source(spec: str) -> tuple[str, float | None]:
    """"photo.jpg" -> (path, None); "reel.mp4@12.5" -> (path, 12.5)."""
    m = re.fullmatch(r"(.+)@(\d+(?:\.\d+)?)", spec)
    return (m.group(1), float(m.group(2))) if m else (spec, None)


def sharpest_time(video: str, t: float, spread: float = 0.4, samples: int = 9) -> float:
    """The least blurry moment within `spread` seconds of t, so a lift is not caught mid-blur.

    Uses numpy when it is installed; otherwise returns t unchanged.
    """
    try:
        import numpy as np
        from .media import read_frames
    except ImportError:
        return t
    d = info(video).duration
    lo, hi = max(0.0, t - spread), min(d - 0.05, t + spread)
    if hi <= lo:
        return t
    try:
        frames = read_frames(video, lo, hi, fps=samples / (hi - lo), width=320).astype(np.float32).mean(axis=3)
    except EditError:
        return t
    lap = np.abs(frames[:, 1:-1, 1:-1] * 4 - frames[:, :-2, 1:-1] - frames[:, 2:, 1:-1]
                 - frames[:, 1:-1, :-2] - frames[:, 1:-1, 2:])
    sharp = lap.reshape(len(frames), -1).var(axis=1)
    return round(lo + (int(sharp.argmax()) + 0.5) * (hi - lo) / len(frames), 3)


def prepare(spec: str, out: str | Path, width: int, height: int, look: str | None = None,
            focus: tuple[float, float] = (0.5, 0.5), sharpen: bool = True, base: str | Path = ".") -> Path:
    """A photo, or a video frame given as "video@seconds", cropped to fill width x height with a look on it.

    focus is the point (fractions across and down) kept in view when cropping.
    """
    src, t = parse_source(spec)
    if not Path(src).exists():
        raise EditError(f"{src} does not exist")
    fx, fy = focus
    if not (0 <= fx <= 1 and 0 <= fy <= 1):
        raise EditError("focus is two fractions between 0 and 1")
    crop = (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}:(iw-{width})*{fx}:(ih-{height})*{fy}")
    cmd = ["ffmpeg", "-v", "error", "-y"]
    if t is not None:
        t = sharpest_time(src, t) if sharpen else t
        cmd += ["-ss", f"{t:.3f}"]
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    run(cmd + ["-i", src, "-frames:v", "1", "-vf", crop + _lut(look, base), "-q:v", "2", str(out)])
    return out


def _data_uri(path: str | Path) -> str:
    kind = "png" if str(path).lower().endswith(".png") else "jpeg"
    return f"data:image/{kind};base64," + base64.b64encode(Path(path).read_bytes()).decode()


# ---------- drawing --------------------------------------------------------------------------------

def rich(text: str, accent: str) -> str:
    """Escape text, turning *words* into accent-coloured words and newlines into breaks."""
    parts = re.split(r"(\*[^*]+\*)", text)
    out = []
    for p in parts:
        if p.startswith("*") and p.endswith("*") and len(p) > 2:
            out.append(f"<span style='color:{accent}'>{escape(p[1:-1])}</span>")
        else:
            out.append(escape(p))
    return "".join(out).replace("\n", "<br>")


def plain(text: str) -> str:
    return text.replace("*", "")


# Shrinks each .fit box's text until it fits, then reports where every text box ended up.
_FIT = """() => {
  const out = [];
  for (const el of document.querySelectorAll('.fit')) {
    let size = parseFloat(el.dataset.size);
    const min = parseFloat(el.dataset.min);
    const c = el.firstElementChild || el;
    const over = () => c.offsetHeight > el.clientHeight + 2 || c.offsetWidth > el.clientWidth + 2 || c.scrollWidth > c.clientWidth + 2;
    el.style.fontSize = size + 'px';
    while (over() && size > min) { size -= 2; el.style.fontSize = size + 'px'; }
    const overflow = over();
    out.push({role: el.dataset.role, size, overflow});
  }
  const boxes = [];
  for (const el of document.querySelectorAll('.txt')) {
    const r = el.getBoundingClientRect();
    if (r.width && r.height) boxes.push({role: el.dataset.role || '', x: r.left, y: r.top, w: r.width, h: r.height});
  }
  return {fits: out, boxes};
}"""


def _fit(role: str, size: int, minimum: int = MIN_FONT) -> str:
    return f"class='fit txt' data-role='{role}' data-size='{size}' data-min='{minimum}'"


def page(body: str, sz: Size, background: str | None = None, dark: str = "#0e0f12", css: str = "") -> str:
    bg = (f"<img class='bg' src='{_data_uri(background)}'>" if background else "")
    return ("<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
            f"html,body{{margin:0;width:{sz.width}px;height:{sz.height}px;overflow:hidden;background:{dark}}}"
            f"#s{{position:relative;width:{sz.width}px;height:{sz.height}px;overflow:hidden;font-family:{FONT};color:#fff}}"
            ".bg{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}"
            ".shade{position:absolute;inset:0}"
            ".cap{font-weight:900;line-height:1.08;letter-spacing:-0.015em;-webkit-text-stroke:.06em #000;"
            "paint-order:stroke fill;text-shadow:0 .08em .3em rgba(0,0,0,.55)}"
            ".fit{overflow:hidden}"
            f"{css}</style></head><body><div id='s'>{bg}{body}</div></body></html>")


@dataclass
class Still:
    path: str
    width: int
    height: int
    font_sizes: dict = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


def check_boxes(boxes: list[dict], sz: Size) -> list[str]:
    """Text boxes that leave the size's safe box."""
    x, y, w, h = sz.safe
    bad = []
    for b in boxes:
        if b["x"] < x - 1 or b["y"] < y - 1 or b["x"] + b["w"] > x + w + 1 or b["y"] + b["h"] > y + h + 1:
            bad.append(f"{b['role'] or 'text'} is outside the {sz.name} safe zone")
    return bad


def render_stills(jobs: list[tuple[str, str | Path, Size]]) -> list[Still]:
    """Render (html, out path, size) jobs in one browser. .jpg/.jpeg outputs are JPEG, others PNG."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise EditError("rendering needs playwright; run `uv sync --all-extras`") from None
    from .render import _browser
    results = []
    with sync_playwright() as p:
        browser = _browser(p)
        for html, out, sz in jobs:
            out = Path(out)
            out.parent.mkdir(parents=True, exist_ok=True)
            pg = browser.new_page(viewport={"width": sz.width, "height": sz.height})
            pg.set_content(html, wait_until="load")
            pg.evaluate("document.fonts.ready")
            report = pg.evaluate(_FIT)
            jpeg = out.suffix.lower() in (".jpg", ".jpeg")
            pg.screenshot(path=str(out), type="jpeg" if jpeg else "png", **({"quality": 92} if jpeg else {}))
            pg.close()
            problems = check_boxes(report["boxes"], sz)
            sizes = {}
            for f in report["fits"]:
                sizes[f["role"]] = f["size"]
                if f["overflow"]:
                    problems.append(f"{f['role']}: too many words to fit; cut it down")
            results.append(Still(str(out), sz.width, sz.height, sizes, problems))
        browser.close()
    return results


def _box(sz: Size, top: float, height: float) -> str:
    """CSS for a text box spanning the safe width, from `top` to `top + height` (fractions of the safe height)."""
    x, y, w, h = sz.safe
    return f"position:absolute;left:{x}px;width:{w}px;top:{y + top * h:.0f}px;height:{height * h:.0f}px"


def text_layer(text: str, sz: Size, b: dict, place: str = "bottom", size_px: int = 110, role: str = "text",
               shade: bool = True) -> str:
    """Caption-style text in the safe zone, top, middle or bottom, with a dark fade behind it."""
    spans = {"top": (0.0, 0.42, "flex-start"), "middle": (0.25, 0.5, "center"), "bottom": (0.5, 0.5, "flex-end")}
    if place not in spans:
        raise EditError("text goes at the top, middle or bottom")
    top, height, align = spans[place]
    fade = ""
    if shade:
        direction = {"top": "to bottom", "bottom": "to top", "middle": "to top"}[place]
        fade = (f"<div class='shade' style='background:linear-gradient({direction},rgba(0,0,0,.72) 0%,"
                f"rgba(0,0,0,.25) 45%,rgba(0,0,0,0) 70%)'></div>")
    return (f"{fade}<div {_fit(role, size_px)} style='{_box(sz, top, height)};display:flex;flex-direction:column;"
            f"justify-content:{align};text-align:center;color:{b['text']}'>"
            f"<div class='cap'>{rich(text, b['accent'])}</div></div>")


# ---------- photo edits ----------------------------------------------------------------------------

def photo(spec: str, out: str | Path, size_name: str = "portrait", look: str | None = None, text: str = "",
          place: str = "bottom", focus: tuple[float, float] = (0.5, 0.5), base: str | Path = ".") -> Still:
    """Crop a photo (or video frame) to a platform size, put a look on it, and optionally a caption."""
    sz = size(size_name)
    out = Path(out)
    with tempfile.TemporaryDirectory() as tmp:
        bg = prepare(spec, Path(tmp) / "bg.jpg", sz.width, sz.height, look, focus, base=base)
        if not text:
            shutil.copy(bg, out) if out.suffix.lower() in (".jpg", ".jpeg") else run(
                ["ffmpeg", "-v", "error", "-y", "-i", str(bg), str(out)])
            return Still(str(out), sz.width, sz.height)
        html = page(text_layer(text, sz, brand(base), place, 120 if sz.height > 1400 else 104), sz, bg)
        return render_stills([(html, out, sz)])[0]


# ---------- carousels ------------------------------------------------------------------------------

@dataclass
class Slide:
    text: str
    image: str = ""          # a photo path, or "video@seconds"; empty for a plain slide
    kind: str = "idea"       # hook, idea or cta
    said_at: float | None = None

    def to_dict(self) -> dict:
        d = {"kind": self.kind, "text": self.text, "image": self.image}
        if self.said_at is not None:
            d["said_at"] = self.said_at
        return d


def sentences(words: list[Word]) -> list[tuple[str, float, float]]:
    """Group words into sentences on ., ! and ? (or a pause over 1.2 s). Returns (text, start, end)."""
    out, cur = [], []
    for n, w in enumerate(words):
        cur.append(w)
        gap = words[n + 1].start - w.end if n + 1 < len(words) else 0
        if w.text.rstrip().endswith((".", "!", "?")) or gap > 1.2 or n == len(words) - 1:
            out.append((" ".join(x.text.strip() for x in cur).strip(), cur[0].start, cur[-1].end))
            cur = []
    return [s for s in out if s[0]]


_TRIM = re.compile(r"^(?:(?:so|and|okay|ok|alright|um|uh|like|now|well|right|yeah)[,\s]+)+", re.I)


def tidy(sentence: str) -> str:
    s = _TRIM.sub("", sentence.strip())
    return s[:1].upper() + s[1:] if s else s


def carousel_draft(words: list[Word], video: str | None = None, hook: str | None = None, cta: str = "follow",
                   max_words: int = 22, max_ideas: int = 8, brand_: dict | None = None) -> list[Slide]:
    """A first carousel from what was said in a reel: hook slide, one idea per slide, a call to action.

    The words are the spoken ones, tidied a little. Claude should rewrite them as
    slide text before rendering: shorter, one idea each, the hook as a promise.
    Each slide's picture is the frame from when that part was said.
    """
    said = [(tidy(t), a, b) for t, a, b in sentences(words)]
    said = [s for s in said if s[0]]
    if not said and not hook:
        raise EditError("no words to make a carousel from")
    b = brand_ or BRAND_DEFAULTS
    first = said.pop(0) if said and not hook else None
    hook_text = hook or first[0]
    slides = [Slide(hook_text, f"{video}@{(first[1] + first[2]) / 2 if first else 0.5:.2f}" if video else "", "hook",
                    first[1] if first else None)]
    group: list[tuple[str, float, float]] = []
    ideas: list[tuple[str, float, float]] = []
    for s in said:
        if group and len(" ".join(g[0] for g in group).split()) + len(s[0].split()) > max_words:
            ideas.append((" ".join(g[0] for g in group), group[0][1], group[-1][2])); group = []
        group.append(s)
    if group:
        ideas.append((" ".join(g[0] for g in group), group[0][1], group[-1][2]))
    if len(ideas) > max_ideas:
        # Keep the spread of the talk rather than only its start.
        step = len(ideas) / max_ideas
        ideas = [ideas[int(n * step)] for n in range(max_ideas)]
    for text, a, e in ideas:
        slides.append(Slide(text, f"{video}@{(a + e) / 2:.2f}" if video else "", "idea", round(a, 2)))
    slides.append(Slide(cta_text(cta, b), "", "cta"))
    return slides


def cta_text(cta: str, b: dict) -> str:
    handle, site = b.get("handle") or "", b.get("site") or ""
    texts = {
        "follow": "*Follow* for more",
        "save": "*Save* this for your next session",
        "send": "*Send* this to your training partner",
        "comment": "What would you add? *Comment* below",
        "coaching": f"Want a plan built for you? *Coaching* at {site}" if site else "Want a plan built for you? *Link in bio*",
        "none": "",
    }
    if cta not in texts:
        raise EditError(f"call to action is one of: {', '.join(texts)}")
    return texts[cta]


def check_carousel(slides: list[Slide]) -> list[str]:
    """Story-first rules for a carousel. Returns problems, empty when it is fine."""
    problems = []
    if not slides or slides[0].kind != "hook":
        problems.append("slide 1 must be the hook")
    elif len(plain(slides[0].text).split()) > 14:
        problems.append(f"the hook is {len(plain(slides[0].text).split())} words; keep it to 14 or fewer")
    if len(slides) > MAX_SLIDES:
        problems.append(f"{len(slides)} slides; Instagram allows {MAX_SLIDES}")
    if len(slides) < 3:
        problems.append("a carousel needs a hook, at least one idea and an ending")
    for n, s in enumerate(slides[1:], 2):
        if s.kind == "idea" and len(plain(s.text).split()) > 35:
            problems.append(f"slide {n} has {len(plain(s.text).split())} words; one idea is 35 or fewer")
    return problems


def slide_html(s: Slide, n: int, total: int, bg: str | None, b: dict, sz: Size) -> str:
    counter = (f"<div class='txt n' data-role='counter' style='position:absolute;right:{sz.width - sz.safe[0] - sz.safe[2]}px;"
               f"top:{sz.safe[1]}px;font:800 30px {FONT};padding:8px 18px;border-radius:30px;"
               f"background:rgba(0,0,0,.55)'>{n}/{total}</div>")
    if s.kind == "hook":
        swipe = (f"<div class='txt' data-role='swipe' style='position:absolute;right:{sz.width - sz.safe[0] - sz.safe[2]}px;"
                 f"top:{sz.safe[1] + sz.safe[3] - 56}px;font:800 34px {FONT};color:{b['accent']}'>swipe &rarr;</div>")
        text = text_layer(s.text, sz, b, "bottom" if bg else "middle", 128, "hook")
        # Leave room above the swipe tag.
        text = text.replace(f"height:{0.5 * sz.safe[3]:.0f}px", f"height:{0.5 * sz.safe[3] - 70:.0f}px")
        return page(text + swipe + counter, sz, bg, b["dark"])
    if s.kind == "cta":
        handle = (f"<div {_fit('handle', 64)} style='{_box(sz, 0.74, 0.1)};text-align:center;"
                  f"font-weight:800;opacity:.9'>{escape(b.get('handle') or '')}</div>") if b.get("handle") else ""
        return page(text_layer(s.text, sz, b, "middle", 104, "cta", shade=bool(bg)) + handle + counter, sz, bg, b["dark"])
    if bg:
        return page(text_layer(s.text, sz, b, "bottom", 84, f"slide {n}") + counter, sz, bg, b["dark"])
    num = (f"<div class='txt' data-role='number' style='{_box(sz, 0.0, 0.12)};font:900 72px {FONT};"
           f"color:{b['accent']}'>{n - 1:02d}</div>")
    body = (f"<div {_fit(f'slide {n}', 88)} style='{_box(sz, 0.14, 0.8)};display:flex;align-items:center'>"
            f"<div class='cap' style='-webkit-text-stroke:0;text-shadow:none'>{rich(s.text, b['accent'])}</div></div>")
    return page(num + body + counter, sz, None, b["dark"])


def render_carousel(slides: list[Slide], out_dir: str | Path, look: str | None = None, size_name: str = "portrait",
                    base: str | Path = ".") -> list[Still]:
    """Render every slide to out_dir/slide_01.jpg and so on."""
    sz = size(size_name)
    b = brand(base)
    out_dir = Path(out_dir)
    jobs = []
    with tempfile.TemporaryDirectory() as tmp:
        for n, s in enumerate(slides, 1):
            bg = prepare(s.image, Path(tmp) / f"bg{n}.jpg", sz.width, sz.height, look, base=base) if s.image else None
            jobs.append((slide_html(s, n, len(slides), bg, b, sz), out_dir / f"slide_{n:02d}.jpg", sz))
        return render_stills(jobs)


def load_plan(path: str | Path) -> tuple[list[Slide], dict]:
    data = json.loads(Path(path).read_text())
    slides = [Slide(s.get("text", ""), s.get("image", ""), s.get("kind", "idea"), s.get("said_at"))
              for s in data.get("slides", [])]
    return slides, data


def save_plan(path: str | Path, slides: list[Slide], **extra) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**extra, "slides": [s.to_dict() for s in slides]}, indent=2) + "\n")
    return path


# ---------- covers and thumbnails ------------------------------------------------------------------

def cover_times(video: str, count: int = 3) -> list[float]:
    """Candidate cover moments: the sharpest frame near the middle of each part of the video."""
    d = info(video).duration
    return [sharpest_time(video, d * (n + 0.5) / count, spread=min(1.0, d / count / 2)) for n in range(count)]


def cover_html(title: str, bg: str, sz: Size, b: dict) -> str:
    if sz.name == "thumbnail":
        # Big words on the left half, so the face or lift reads on the right.
        x, y, w, h = sz.safe
        body = ("<div class='shade' style='background:linear-gradient(to right,rgba(0,0,0,.78),rgba(0,0,0,.1) 65%)'></div>"
                f"<div {_fit('title', 150, 60)} style='position:absolute;left:{x}px;top:{y}px;width:{w * 0.6:.0f}px;"
                f"height:{h}px;display:flex;align-items:center'><div class='cap' style='text-transform:uppercase'>"
                f"{rich(title, b['accent'])}</div></div>")
        return page(body, sz, bg, b["dark"])
    # Reel cover: title in the upper part of the grid crop, clear of the subject's face in most shots.
    x, y, w, h = sz.safe
    body = ("<div class='shade' style='background:linear-gradient(to bottom,rgba(0,0,0,.65) 10%,rgba(0,0,0,0) 45%)'></div>"
            f"<div {_fit('title', 140, 64)} style='position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h * 0.34:.0f}px;"
            "display:flex;align-items:flex-start;justify-content:center;text-align:center'>"
            f"<div class='cap'>{rich(title, b['accent'])}</div></div>")
    return page(body, sz, bg, b["dark"])


def covers(video: str, title: str, out_dir: str | Path, count: int = 3, look: str | None = None,
           thumbnail: bool = False, times: list[float] | None = None, base: str | Path = ".") -> list[Still]:
    """Cover options for a reel (and YouTube thumbnails when asked), each with a grid preview.

    Returns the covers; each cover_N.jpg has a cover_N_grid.jpg next to it,
    showing the 3:4 crop the profile grid will use.
    """
    if len(plain(title).split()) > 7:
        raise EditError(f"a cover title is read in a glance: {len(plain(title).split())} words is too many, keep to 7")
    b = brand(base)
    out_dir = Path(out_dir)
    times = times or cover_times(video, count)
    jobs = []
    with tempfile.TemporaryDirectory() as tmp:
        for n, t in enumerate(times, 1):
            for sz in [SIZES["cover"]] + ([SIZES["thumbnail"]] if thumbnail else []):
                bg = prepare(f"{video}@{t}", Path(tmp) / f"{sz.name}{n}.jpg", sz.width, sz.height, look,
                             sharpen=False, base=base)
                stem = "cover" if sz.name == "cover" else "thumbnail"
                jobs.append((cover_html(title, str(bg), sz, b), out_dir / f"{stem}_{n}.jpg", sz))
        stills = render_stills(jobs)
    for s in stills:
        if Path(s.path).stem.startswith("cover"):
            grid = Path(s.path).with_name(Path(s.path).stem + "_grid.jpg")
            run(["ffmpeg", "-v", "error", "-y", "-i", s.path, "-vf", "crop=1080:1440:0:240", "-q:v", "3", str(grid)])
    return stills


# ---------- stories --------------------------------------------------------------------------------

@dataclass
class Story:
    kind: str              # teaser, poll, question, coaching, behind
    text: str              # what is drawn on the story
    sticker: str           # the sticker to add in the app, and what to type in it
    day: float             # days after the reel posts (0.1 is a couple of hours later)
    image: str = ""
    why: str = ""

    def to_dict(self) -> dict:
        return {"kind": self.kind, "text": self.text, "sticker": self.sticker, "day": self.day,
                "image": self.image, "why": self.why}


def story_suggestions(hook: str, video: str | None = None, topic: str = "", cta: str = "follow",
                      b: dict | None = None) -> list[Story]:
    """Three stories to post around a reel: a teaser, a poll, then a question box or coaching link.

    Stories warm up people who already follow; they are where a call to action
    to coaching belongs, not on every reel. Drafts are a start for Claude to rewrite.
    """
    b = b or BRAND_DEFAULTS
    d = info(video).duration if video else 0
    frame = lambda f: f"{video}@{d * f:.2f}" if video else ""  # noqa: E731
    about = topic or "this"
    claim = plain(hook).rstrip(".!?")
    out = [
        Story("teaser", f"New reel:\n*{plain(hook)}*", "Add the reel itself (share the post to your story)", 0,
              frame(0.5), "Sends followers who see stories first to the reel in its first hour."),
        Story("poll", f"{claim}.\n*Agree?*", "Poll: Agree / No way", 0.1, frame(0.25),
              "A two-way opinion is the easiest tap; it lifts story replies and reach."),
    ]
    if cta == "coaching":
        site = b.get("site") or "the link in bio"
        out.append(Story("coaching", f"Want this built into *your* program?", f"Link sticker: {site}", 1, frame(0.75),
                         "Coaching asks belong in stories, once the reel has shown the value."))
    else:
        out.append(Story("question", f"Questions about *{about}*?\nAsk me anything", f"Question box: Ask me about {about}",
                         1, frame(0.75), "Answers become the next stories and ideas for reels."))
    return out


def story_html(s: Story, bg: str | None, b: dict) -> str:
    sz = SIZES["story"]
    # Text in the upper part of the safe zone; the lower part is left clear for the sticker.
    body = text_layer(s.text, sz, b, "top", 96, f"story {s.kind}")
    sticker = (f"<div class='txt' data-role='sticker area' style='{_box(sz, 0.52, 0.3)}'></div>")
    return page(body + sticker, sz, bg, b["dark"])


def render_stories(stories: list[Story], out_dir: str | Path, look: str | None = None,
                   base: str | Path = ".") -> list[Still]:
    sz = SIZES["story"]
    b = brand(base)
    out_dir = Path(out_dir)
    jobs = []
    with tempfile.TemporaryDirectory() as tmp:
        for n, s in enumerate(stories, 1):
            bg = prepare(s.image, Path(tmp) / f"s{n}.jpg", sz.width, sz.height, look, base=base) if s.image else None
            jobs.append((story_html(s, str(bg) if bg else None, b), out_dir / f"story_{n}_{s.kind}.jpg", sz))
        return render_stills(jobs)


# ---------- one reel in, a package out -------------------------------------------------------------

def contact(paths: list[str], out: str | Path, width: int = 270) -> Path:
    """One row of images side by side, for a quick look at a whole carousel or set."""
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for p in paths:
        cmd += ["-i", p]
    scaled = "".join(f"[{n}:v]scale={width}:-2,pad={width + 12}:ih:6:0:black[v{n}];" for n in range(len(paths)))
    graph = scaled + "".join(f"[v{n}]" for n in range(len(paths))) + f"hstack=inputs={len(paths)}[o]" \
        if len(paths) > 1 else f"[0:v]scale={width}:-2[o]"
    run(cmd + ["-filter_complex", graph, "-map", "[o]", "-frames:v", "1", "-q:v", "3", str(out)])
    return Path(out)


def package(video: str, words: list[Word], title: str, out_dir: str | Path, hook: str | None = None,
            look: str | None = None, topic: str = "", cta: str = "follow", caption: str = "",
            thumbnail: bool = False, base: str | Path = ".") -> dict:
    """A finished reel in; a carousel, three covers and three stories out, plus package.json for the calendar."""
    out_dir = Path(out_dir)
    b = brand(base)
    slides = carousel_draft(words, video, hook, cta if cta in ("follow", "save", "send", "comment", "coaching") else "follow",
                            brand_=b)
    save_plan(out_dir / "carousel.json", slides, look=look or "", size="portrait")
    car = render_carousel(slides, out_dir / "carousel", look, base=base)
    cov = covers(video, title, out_dir / "covers", look=look, thumbnail=thumbnail, base=base)
    stories = story_suggestions(slides[0].text, video, topic, cta, b)
    (out_dir / "stories.json").write_text(json.dumps([s.to_dict() for s in stories], indent=2) + "\n")
    sto = render_stories(stories, out_dir / "stories", look, base=base)
    contact([s.path for s in car], out_dir / "carousel_overview.jpg")
    contact([s.path for s in cov if "cover" in Path(s.path).stem], out_dir / "covers_overview.jpg")
    contact([s.path for s in sto], out_dir / "stories_overview.jpg")
    problems = check_carousel(slides) + [f"{Path(s.path).name}: {p}" for s in car + cov + sto for p in s.problems]
    posts = [{"format": "cover", "suggested_day": 0, "files": [s.path for s in cov if "cover" in Path(s.path).stem],
              "caption": "", "cta": "none", "notes": f"Pick one cover for the reel. Title: {title}", "status": "draft"},
             {"format": "carousel", "suggested_day": 3, "files": [s.path for s in car],
              "caption": caption or plain(slides[0].text), "cta": cta,
              "notes": "Carousel from the same shoot; post a few days after the reel so they do not compete.",
              "status": "draft"}]
    posts += [{"format": "story", "suggested_day": s.day, "files": [st.path], "caption": plain(s.text).replace("\n", " "),
               "cta": "coaching" if s.kind == "coaching" else "none", "sticker": s.sticker, "notes": s.why,
               "status": "draft"} for s, st in zip(stories, sto)]
    result = {"name": out_dir.name, "reel_title": title, "video": str(video), "title": title, "look": look or "", "posts": posts, "problems": problems}
    (out_dir / "package.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
