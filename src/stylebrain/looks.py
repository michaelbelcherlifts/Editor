"""The "house" look: templates built from Michael's round 1 critique and his strength.now reference.

He judged the default caption templates "AI-ish": a fallback system font, a different accent colour on every
reel, tilted slam-in words. These set text in fonts that ship with the editor (Montserrat, Anton), use warm
white with one red accent on at most one word per group, and move calmly.

- house_captions: heavy italic white captions, two or three words, the group breaking at a full stop or a pause
- house_hook: the opening text, already on screen on the first frame (no entry animation)
- big_title: a huge condensed number or word meant to sit behind the person (see `people.behind`)
- notification: a phone notification banner floating in the scene, tilted in 3D
"""

from __future__ import annotations

import re
from html import escape

from .edl import EditError
from .pagekit import _page, font_faces

WHITE = "#F7F5F0"     # warm white, softer than screen white
ACCENT = "#E3262F"    # the one accent: the red of his reference
INK = "#0B0B0C"
MONT = "'Montserrat','Inter',Arial,sans-serif"
ANTON = "'Anton','Bebas Neue','Arial Narrow',sans-serif"
_SHOW = "@keyframes vis{from{visibility:visible}to{visibility:visible}}"


def _key(word: str) -> str:
    return re.sub(r"[^\w.]", "", word.lower()).strip(".")


def _window(a: float, b: float) -> str:
    return f"visibility:hidden;animation:vis {max(b - a, 0.04):.3f}s linear {a:.3f}s"


def group_words(words: list[dict], max_words: int = 3, max_chars: int = 16, gap: float = 0.25) -> list[list[dict]]:
    """Caption groups that end at a full stop or comma, at a pause, or when they get long."""
    out, cur = [], []
    for w in words:
        word = str(w.get("word", "")).strip()
        if not word:
            continue
        w = {**w, "word": word}
        if cur and (len(cur) >= max_words or len(" ".join(x["word"] for x in cur + [w])) > max_chars
                    or float(w["start"]) - float(cur[-1]["end"]) > gap):
            out.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.,?!;:]$", word):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def _clean(word: str) -> str:
    # A hyphen never breaks a line ("one-rep" stays together); trailing punctuation is dropped.
    return re.sub(r"[.,;:]$", "", word).replace("-", "‑").upper()


def house_captions(words: list[dict], duration: float | None = None, accent_words: list[str] | None = None,
                   max_words: int = 3, max_chars: int = 16, size: int = 100, y: float = 0.62,
                   width: int = 1080, height: int = 1920):
    """Heavy italic white captions, two or three words at a time, one red word at most per group.
    Words are {"word", "start", "end"} in seconds from the overlay start. Use y 0.80 over a wide lift shot so
    the words sit under the plates rather than on them."""
    groups = group_words(words or [], max_words, max_chars)
    if not groups:
        raise EditError("house_captions needs words with timings")
    hot = {_key(w) for w in (accent_words or [])}
    total = max(float(duration or 0), float(groups[-1][-1]["end"]) + 0.3)
    divs = []
    for i, g in enumerate(groups):
        a = float(g[0]["start"])
        b = min(float(groups[i + 1][0]["start"]), float(g[-1]["end"]) + 0.5) if i + 1 < len(groups) else total
        used, parts = False, []
        for w in g:
            t = escape(_clean(w["word"]))
            if not used and _key(w["word"]) in hot:
                parts.append(f"<span class='hot'>{t}</span>")
                used = True
            else:
                parts.append(t)
        divs.append(f"<div class='c' style='{_window(a, b)}'><div class='in' style='animation-delay:{a:.3f}s'>"
                    f"{' '.join(parts)}</div></div>")
    css = (font_faces("montserrat") +
           f".c{{position:absolute;left:7%;right:7%;top:{y * 100:.1f}%;transform:translateY(-50%);text-align:center}}"
           f".in{{display:inline-block;font-family:{MONT};font-weight:900;font-size:{size}px;line-height:1;"
           f"letter-spacing:-0.01em;color:{WHITE};transform:skewX(-7deg);-webkit-text-stroke:7px {INK};"
           "paint-order:stroke fill;text-shadow:0 6px 16px rgba(0,0,0,.55);animation:pop .11s ease-out both}"
           f".hot{{color:{ACCENT}}}"
           "@keyframes pop{from{opacity:0;transform:skewX(-7deg) scale(.9)}to{opacity:1;transform:skewX(-7deg) scale(1)}}"
           + _SHOW)
    return _page("".join(divs), css, width, height), total


def house_hook(lines: list[str], duration: float, accent_words: list[str] | None = None, y: float = 0.13,
               size: int = 92, width: int = 1080, height: int = 1920):
    """The opening text, top third, already on screen on the first frame: no entry animation, so the
    thumbnail and the first frame both carry it."""
    if not lines or not any(str(x).strip() for x in lines):
        raise EditError("house_hook needs one or two lines of text")
    hot = {_key(w) for w in (accent_words or [])}
    rows = ["&nbsp;".join(f"<span class='hot'>{escape(w.upper())}</span>" if _key(w) in hot else escape(w.upper())
                          for w in str(line).split()) for line in lines]
    css = (font_faces("montserrat") +
           f".h{{position:absolute;left:6%;right:6%;top:{y * 100:.1f}%;text-align:center;font-family:{MONT};"
           f"font-weight:900;font-size:{size}px;line-height:1.04;color:{WHITE};transform:skewX(-7deg);"
           f"-webkit-text-stroke:7px {INK};paint-order:stroke fill;text-shadow:0 6px 16px rgba(0,0,0,.55)}}"
           f".hot{{color:{ACCENT}}}")
    return _page("<div class='h'>" + "<br>".join(rows) + "</div>", css, width, height), float(duration)


def big_title(text: str, duration: float, unit: str = "", accent: bool = False, y: float = 0.27, size: int = 400,
              x: float = 0.5,
              width: int = 1080, height: int = 1920):
    """A huge condensed number or word for behind the person: place it high (y about 0.27) so the
    head only overlaps its lower edge, and move it sideways (`x`) off a second person. Composite with
    `stylebrain behind`."""
    if not str(text).strip():
        raise EditError("big_title needs text")
    colour = ACCENT if accent else WHITE
    u = f"<span class='u'>{escape(unit)}</span>" if unit else ""
    css = (font_faces("anton") +
           f".b{{position:absolute;left:{x * 100:.1f}%;top:{y * 100:.1f}%;transform:translate(-50%,-50%);text-align:center;white-space:nowrap;"
           f"font-family:{ANTON};font-size:{size}px;line-height:.88;color:{colour};"
           "text-shadow:0 10px 40px rgba(0,0,0,.35);animation:bin .18s ease-out both}"
           ".u{display:block;font-size:.36em;letter-spacing:.06em}"
           "@keyframes bin{from{opacity:0;transform:translate(-50%,-50%) scale(1.06)}to{opacity:1;transform:translate(-50%,-50%) scale(1)}}")
    return _page(f"<div class='b'>{escape(str(text))}{u}</div>", css, width, height), float(duration)


def notification(app: str, message: str, duration: float = 4.0, icon: str = "", x: float = 0.5, y: float = 0.36,
                 tilt: list[float] | None = None, width: int = 1080, height: int = 1920):
    """A phone notification banner floating in the scene, tilted in 3D, that drops in and drifts slightly:
    the viewer's question or a coach's message on screen (strength.now x theswolefessor reference).
    Keep it off the face: between the face and the captions works on a talking head."""
    if not app.strip() or not message.strip():
        raise EditError("notification needs an app name and a message")
    rx, ry, rz = (tilt or [16, -16, 12])[:3]
    ic = escape((icon or app.strip()[0]).upper()[:2])
    rot = f"rotateX({rx}deg) rotateY({ry}deg) rotateZ({rz}deg)"
    drift = f"rotateX({rx + 3}deg) rotateY({ry + 4}deg) rotateZ({rz - 1}deg) translateY(-8px)"
    body = (f"<div class='w'><div class='n'><div class='ic'>{ic}</div><div class='tx'>"
            f"<div class='t'>{escape(app)}<span class='now'>now</span></div>"
            f"<div class='m'>{escape(message)}</div></div></div></div>")
    css = (font_faces("inter") +
           f".w{{position:absolute;left:{x * 100:.1f}%;top:{y * 100:.1f}%;perspective:1400px;transform:translate(-50%,-50%)}}"
           ".n{width:820px;display:flex;gap:26px;align-items:center;padding:30px 34px;border-radius:44px;"
           "background:rgba(28,28,30,.86);border:1.5px solid rgba(255,255,255,.14);"
           "box-shadow:0 30px 80px rgba(0,0,0,.55),inset 0 1px 0 rgba(255,255,255,.08);"
           f"transform:{rot};animation:nin .38s cubic-bezier(.2,.9,.25,1) both,drift 6s ease-in-out .38s infinite alternate}}"
           ".ic{flex:none;width:92px;height:92px;border-radius:22px;background:#2b2b2e;color:#fff;font-family:'Inter',Arial;"
           f"font-weight:800;font-size:46px;display:flex;align-items:center;justify-content:center;box-shadow:inset 0 0 0 2px {ACCENT}}}"
           ".tx{flex:1;min-width:0;font-family:'Inter',Arial,sans-serif;color:#fff}"
           ".t{font-weight:700;font-size:34px;display:flex;justify-content:space-between}"
           ".now{font-weight:500;color:rgba(255,255,255,.55);font-size:30px}"
           ".m{font-weight:500;font-size:34px;line-height:1.22;color:rgba(255,255,255,.92);margin-top:6px}"
           f"@keyframes nin{{from{{opacity:0;transform:{rot} translateY(-60px) scale(.94)}}to{{opacity:1;transform:{rot}}}}}"
           f"@keyframes drift{{from{{transform:{rot}}}to{{transform:{drift}}}}}")
    return _page(body, css, width, height), float(duration)
