"""Animation templates: each returns (html, duration in seconds) for the renderer.

Every template draws on a transparent 1920x1080 page (or the size given) and
animates with CSS only, so the renderer can step through it frame by frame.
Add a template by writing a function and registering it in TEMPLATES.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from .edl import EditError
from .anatomy import figure_svg, resolve_muscles

FONT = "'Inter','SF Pro Display','Helvetica Neue','Segoe UI',Arial,sans-serif"


def _stage(width: int, height: int) -> tuple[float, float, float]:
    """Templates are designed for a frame whose short side is 1080. Returns the
    design-space width and height, and the scale that maps it onto the real frame."""
    scale = min(width, height) / 1080
    return width / scale, height / scale, scale


def _page(body: str, css: str, width: int = 1920, height: int = 1080) -> str:
    sw, sh, scale = _stage(width, height)
    return (f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
            f"html,body{{margin:0;background:transparent;overflow:hidden}}"
            f"#stage{{width:{sw:.2f}px;height:{sh:.2f}px;zoom:{scale:.5f};position:relative;"
            f"overflow:hidden;font-family:{FONT}}}"
            f"{css}</style></head><body><div id='stage'>{body}</div></body></html>")


def caption_pop(text: str, duration: float = 2.0, stagger: float = 0.09, size: int = 96,
                color: str = "#ffffff", accent: str = "#ffe14a", accent_words: list[str] | None = None,
                y: float = 0.78, width: int = 1920, height: int = 1080):
    """Words pop in one after another with a small overshoot, then fade out together."""
    words = text.split()
    if not words:
        raise EditError("caption_pop needs some text")
    hot = {w.lower().strip(".,!?") for w in (accent_words or [])}
    spans = "".join(
        f"<span style='animation-delay:{i * stagger:.3f}s,{duration - 0.25:.3f}s;"
        f"color:{accent if w.lower().strip('.,!?') in hot else color}'>{escape(w)}</span>"
        for i, w in enumerate(words))
    css = (f".c{{position:absolute;left:8%;right:8%;top:{y * 100:.1f}%;transform:translateY(-50%);"
           f"text-align:center;font-weight:900;font-size:{size}px;line-height:1.15;letter-spacing:-0.01em;"
           f"-webkit-text-stroke:{max(2, size // 16)}px #000;paint-order:stroke fill;"
           f"text-shadow:0 {size // 12}px {size // 5}px rgba(0,0,0,.55)}}"
           ".c span{display:inline-block;margin:0 .14em;opacity:0;"
           "animation:pop .32s cubic-bezier(.2,1.5,.4,1) both,out .25s ease-in forwards}"
           "@keyframes pop{from{opacity:0;transform:scale(.55) translateY(.25em)}to{opacity:1;transform:none}}"
           "@keyframes out{to{opacity:0;transform:scale(.92)}}")
    return _page(f"<div class='c'>{spans}</div>", css, width, height), duration


def lower_third(name: str, title: str = "", duration: float = 4.0, accent: str = "#ff5a36",
                x: float = 0.06, y: float = 0.80, width: int = 1920, height: int = 1080):
    """A name and title that slide in from the left behind an accent bar, hold, and slide out."""
    hold = duration - 0.45
    css = (f".w{{position:absolute;left:{x * 100:.1f}%;top:{y * 100:.1f}%;display:flex;align-items:stretch;"
           f"animation:in .5s cubic-bezier(.2,.9,.2,1) both,out .45s ease-in {hold:.3f}s forwards}}"
           f".bar{{width:12px;background:{accent};border-radius:6px;margin-right:22px}}"
           ".t{background:rgba(12,12,14,.86);border-radius:14px;padding:18px 34px 20px;color:#fff}"
           ".n{font-size:56px;font-weight:800;letter-spacing:-0.01em}"
           ".s{font-size:32px;font-weight:500;opacity:.78;margin-top:4px}"
           "@keyframes in{from{opacity:0;transform:translateX(-90px)}to{opacity:1;transform:none}}"
           "@keyframes out{to{opacity:0;transform:translateX(-60px)}}")
    sub = f"<div class='s'>{escape(title)}</div>" if title else ""
    body = f"<div class='w'><div class='bar'></div><div class='t'><div class='n'>{escape(name)}</div>{sub}</div></div>"
    return _page(body, css, width, height), duration


def callout(text: str, box: list[float], duration: float = 3.0, accent: str = "#ffe14a",
            width: int = 1920, height: int = 1080):
    """A highlight box drawn around part of the frame, with a label above it.

    box is [x, y, w, h] as fractions of the frame.
    """
    if len(box) != 4 or not all(0 <= v <= 1 for v in box):
        raise EditError("callout box is [x, y, w, h] as fractions between 0 and 1")
    sw, sh, _ = _stage(width, height)
    x, y, w, h = (box[0] * sw, box[1] * sh, box[2] * sw, box[3] * sh)
    per = 2 * (w + h)
    hold = duration - 0.3
    label_y = y - 70 if y > 90 else y + h + 14
    css = (f"svg{{position:absolute;inset:0;animation:out .3s ease-in {hold:.3f}s forwards}}"
           f"rect{{fill:rgba(255,255,255,.06);stroke:{accent};stroke-width:8;stroke-linejoin:round;"
           f"stroke-dasharray:{per:.0f};animation:draw .55s ease-out both}}"
           f".l{{position:absolute;left:{x:.0f}px;top:{label_y:.0f}px;background:{accent};color:#111;"
           "font-weight:800;font-size:40px;padding:6px 20px 8px;border-radius:10px;"
           f"animation:lab .3s ease-out .4s both,out .3s ease-in {hold:.3f}s forwards}}"
           f"@keyframes draw{{from{{stroke-dashoffset:{per:.0f}}}to{{stroke-dashoffset:0}}}}"
           "@keyframes lab{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}"
           "@keyframes out{to{opacity:0}}")
    body = (f"<svg width='{sw:.0f}' height='{sh:.0f}'><rect x='{x:.0f}' y='{y:.0f}' width='{w:.0f}' "
            f"height='{h:.0f}' rx='14'/></svg><div class='l'>{escape(text)}</div>")
    return _page(body, css, width, height), duration


def captions(words: list[dict], max_chars: int = 26, size: int = 78, color: str = "#ffffff",
             accent: str = "#ffe14a", y: float = 0.80, width: int = 1920, height: int = 1080):
    """Running captions: a few words at a time, the spoken word highlighted.

    words is a list of {"word", "start", "end"} in seconds from the start of the overlay.
    """
    ws = [(str(w.get("word", w.get("text", ""))).strip(), float(w["start"]), float(w["end"])) for w in words]
    ws = [w for w in ws if w[0]]
    if not ws:
        raise EditError("captions needs words with timings")
    lines, cur = [], []
    for w in ws:
        too_long = cur and len(" ".join(x[0] for x in cur)) + 1 + len(w[0]) > max_chars
        long_gap = cur and w[1] - cur[-1][2] > 0.7
        if too_long or long_gap:
            lines.append(cur); cur = []
        cur.append(w)
    lines.append(cur)
    divs = []
    for line in lines:
        start, end = line[0][1], line[-1][2] + 0.12
        spans = "".join(
            f"<span style='animation-delay:{s:.3f}s,{s:.3f}s;animation-duration:.01s,{max(e - s, .12):.3f}s'>"
            f"{escape(t)}</span>" for t, s, e in line)
        divs.append(f"<div class='ln' style='animation-delay:{start:.3f}s;"
                    f"animation-duration:{end - start:.3f}s'>{spans}</div>")
    css = (f".ln{{position:absolute;left:6%;right:6%;top:{y * 100:.1f}%;text-align:center;opacity:0;"
           f"font-weight:900;font-size:{size}px;color:{color};-webkit-text-stroke:{max(2, size // 14)}px #000;"
           "paint-order:stroke fill;text-shadow:0 6px 18px rgba(0,0,0,.6);animation:show linear both}"
           ".ln span{display:inline-block;margin:0 .13em;animation-name:hot,beat;"
           "animation-timing-function:linear,ease-out;animation-fill-mode:both,none}"
           "@keyframes show{0%{opacity:0}2%{opacity:1}98%{opacity:1}100%{opacity:0}}"
           f"@keyframes hot{{from{{color:{color}}}to{{color:{accent}}}}}"
           "@keyframes beat{0%{transform:scale(1)}30%{transform:scale(1.14)}100%{transform:scale(1)}}")
    return _page("".join(divs), css, width, height), ws[-1][2] + 0.3


def muscle_diagram(highlights: list, title: str = "", duration: float | None = None, side: str = "right",
                   primary: str = "#ff4d2e", secondary: str = "#ffb020", first_at: float = 0.8,
                   every: float = 0.7, width: int = 1920, height: int = 1080):
    """A body figure where named muscles light up one after another, with labels.

    highlights is a list of muscle names, or of {"muscle", "label"?, "at"?, "role"?}
    where role is "primary" or "secondary" and at is seconds from the start.
    Front and back views are chosen automatically from the muscles named.
    """
    items = []
    for n, h in enumerate(highlights):
        h = {"muscle": h} if isinstance(h, str) else dict(h)
        h.setdefault("at", first_at + n * every)
        h.setdefault("role", "primary")
        items.append(h)
    if not items:
        raise EditError("muscle_diagram needs at least one muscle")
    views, resolved = resolve_muscles([h["muscle"] for h in items])
    last = max(float(h["at"]) for h in items)
    duration = duration or last + 2.5
    hold = duration - 0.45
    figures = "".join(figure_svg(v) for v in views)
    css_lit, rows = [], []
    for n, (h, (key, default_label)) in enumerate(zip(items, resolved)):
        colour = primary if h["role"] == "primary" else secondary
        at = float(h["at"])
        css_lit.append(f".m-{key}{{animation:lit{n} .55s ease-out {at:.3f}s both}}"
                       f"@keyframes lit{n}{{from{{fill:var(--base)}}35%{{fill:#fff}}to{{fill:{colour}}}}}")
        rows.append(f"<div class='row' style='animation-delay:{at:.3f}s'>"
                    f"<i style='background:{colour}'></i>{escape(h.get('label') or default_label)}</div>")
    card_w = 560 if len(views) == 1 else 860
    pos = "right:4%" if side == "right" else "left:4%"
    slide = 80 if side == "right" else -80
    css = (":root{--base:#8b8f98;--body:#c9ccd3}"
           f".card{{position:absolute;{pos};top:50%;width:{card_w}px;margin-top:-470px;height:940px;"
           "box-sizing:border-box;padding:34px 36px;border-radius:34px;background:rgba(14,15,18,.9);"
           "box-shadow:0 30px 80px rgba(0,0,0,.45);color:#fff;display:flex;flex-direction:column;"
           f"animation:in .5s cubic-bezier(.2,.9,.2,1) both,out .45s ease-in {hold:.3f}s forwards}}"
           ".ttl{font-size:44px;font-weight:800;letter-spacing:-0.01em;margin-bottom:10px}"
           ".figs{flex:1;display:flex;justify-content:center;gap:10px;min-height:0}"
           ".figs svg{height:100%;width:auto}"
           ".body{fill:var(--body)}.m{fill:var(--base)}"
           ".rows{margin-top:14px}"
           ".row{display:flex;align-items:center;font-size:34px;font-weight:700;margin-top:10px;opacity:0;"
           "animation:row .35s ease-out both}"
           ".row i{width:22px;height:22px;border-radius:50%;margin-right:16px;flex:none}"
           f"@keyframes in{{from{{opacity:0;transform:translateX({slide}px)}}to{{opacity:1;transform:none}}}}"
           f"@keyframes out{{to{{opacity:0;transform:translateX({slide}px)}}}}"
           "@keyframes row{from{opacity:0;transform:translateX(-14px)}to{opacity:1;transform:none}}"
           + "".join(css_lit))
    ttl = f"<div class='ttl'>{escape(title)}</div>" if title else ""
    body = f"<div class='card'>{ttl}<div class='figs'>{figures}</div><div class='rows'>{''.join(rows)}</div></div>"
    return _page(body, css, width, height), duration


def html_file(path: str, duration: float, **values):
    """A hand-written animation saved as an HTML file, with {{name}} placeholders filled in.

    This is how a one-off effect copied from a reference video is kept for reuse.
    """
    text = Path(path).read_text()
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", escape(str(value)))
    return text, float(duration)


TEMPLATES = {
    "caption_pop": caption_pop,
    "lower_third": lower_third,
    "callout": callout,
    "captions": captions,
    "muscle_diagram": muscle_diagram,
    "html": html_file,
}


def build(name: str, params: dict) -> tuple[str, float]:
    if name not in TEMPLATES:
        raise EditError(f"no template named {name!r}; there are: {', '.join(sorted(TEMPLATES))}")
    try:
        return TEMPLATES[name](**params)
    except TypeError as e:
        raise EditError(f"template {name!r}: {e}") from None
