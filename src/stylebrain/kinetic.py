"""Type-led templates from the creator study (PRD W8.2).

- kinetic_type: huge word-by-word titles, tilted and stacked, one key word in colour
  (the TOGI look).
- mid_captions: one to three words at a time in the middle of the frame.
- title_bar: a title held across the whole video.
- end_card: numbers or macros that count up on a card.
- counter: a rep or day counter that ticks at given times.
- spaced_title, plain_captions, burst: the cinematic edit study (docs/cinematic-editing.md):
  wide-spaced title words, quiet plain captions, hand-drawn burst marks.
- clipper: the "clipper" layout: black bands above and below a fitted landscape
  clip, with a headline in the top band.
- hud_card: game-style stakes and payoff cards (mission, passed, failed) and a
  hazard-striped warning card for "don't let X see this" hooks.

All draw on a transparent page and are stepped by the renderer. Counting numbers
use `window.seek`, so they land on exact values on every frame.
"""

from __future__ import annotations

import json
from html import escape

from .edl import EditError
from .pagekit import CAPTION_BAND, HEAVY, _page, _stage, font_faces, keep_clear_box

_PUNCT = ".,!?;:\"'"


def _key(word: str) -> str:
    return word.lower().strip(_PUNCT)


def timed_words(words: list[dict] | None = None, text: str | None = None, duration: float | None = None,
                lead: float = 0.2) -> list[tuple[str, float, float]]:
    """Words with times, from a transcript slice or from plain text spread evenly over `duration`."""
    if words:
        out = [(str(w.get("word", w.get("text", ""))).strip(), float(w["start"]), float(w["end"])) for w in words]
        out = [w for w in out if w[0]]
    elif text and text.split():
        parts = text.split()
        span = (duration or 0.42 * len(parts) + 0.6) - lead - 0.4
        step = max(span, 0.2) / len(parts)
        out = [(p, lead + i * step, lead + (i + 1) * step) for i, p in enumerate(parts)]
    else:
        out = []
    if not out:
        raise EditError("needs `words` with timings, or `text`")
    return out


def _chunks(ws, max_words: int, gap: float = 0.35):
    groups, cur = [], []
    for w in ws:
        if cur and (len(cur) >= max_words or w[1] - cur[-1][2] > gap or cur[-1][0][-1:] in ".!?,"):
            groups.append(cur); cur = []
        cur.append(w)
    groups.append(cur)
    return groups


_SHOW = "@keyframes vis{from,to{visibility:visible}}"


def _window(start: float, end: float) -> str:
    """Inline style that makes an element visible only between start and end."""
    return f"visibility:hidden;animation:vis {max(end - start, 0.04):.3f}s linear {start:.3f}s"


def kinetic_type(words: list[dict] | None = None, text: str | None = None, duration: float | None = None,
                 accent_words: list[str] | None = None, accent: str = "#2f7bff", color: str = "#ffffff",
                 per_group: int = 2, size: int = 200, y: float = 0.40, tilt: float = 5.0,
                 width: int = 1920, height: int = 1080):
    """Huge word-by-word titles that slam in tilted and stacked, one key word in colour (TOGI style).

    Give `words` ({"word","start","end"}, seconds from the overlay start) to sync to speech,
    or `text` (and optionally `duration`) to spread the words evenly.
    """
    ws = timed_words(words, text, duration)
    hot = {_key(w) for w in (accent_words or [])}
    sw, _, _ = _stage(width, height)
    groups = _chunks(ws, max(1, per_group))
    end_all = ws[-1][2] + 0.5
    total = max(duration or 0, end_all)
    angles = [-tilt, tilt * 0.6, -tilt * 0.4, tilt]
    blocks, n = [], 0
    for gi, g in enumerate(groups):
        start = g[0][1]
        end = groups[gi + 1][0][1] if gi + 1 < len(groups) else total
        lines = []
        for t, s, _e in g:
            word = t.upper()
            fit = int(0.88 * sw / max(0.66 * len(word), 1))
            px = min(size, fit)
            colour = accent if _key(t) in hot else color
            rot = angles[n % len(angles)]
            n += 1
            lines.append(f"<div class='w' style='font-size:{px}px;color:{colour};--r:{rot:.1f}deg;"
                         f"animation-delay:{s:.3f}s'>{escape(word)}</div>")
        blocks.append(f"<div class='g' style='{_window(start, end)}'>{''.join(lines)}</div>")
    css = (f".g{{position:absolute;left:0;right:0;top:{y * 100:.1f}%;transform:translateY(-50%);"
           "display:flex;flex-direction:column;align-items:center}"
           f".w{{font-family:{HEAVY};font-weight:900;line-height:.86;letter-spacing:-0.02em;"
           "font-stretch:expanded;text-shadow:0 10px 0 rgba(0,0,0,.28),0 18px 40px rgba(0,0,0,.45);"
           "transform:rotate(var(--r));opacity:0;animation:slam .26s cubic-bezier(.2,1.4,.4,1) both}"
           "@keyframes slam{from{opacity:0;transform:rotate(calc(var(--r)*3)) scale(1.9)}"
           "60%{opacity:1}to{opacity:1;transform:rotate(var(--r)) scale(1)}}" + _SHOW)
    return _page("".join(blocks), css, width, height), total


# Where words land within one set, as frame fractions (centre of each word), in order.
_SLOTS = [(0.24, 0.20), (0.76, 0.20), (0.50, 0.44), (0.28, 0.62), (0.72, 0.80), (0.50, 0.88)]


def kinetic_scatter(words: list[dict] | None = None, text: str | None = None, duration: float | None = None,
                    accent_words: list[str] | None = None, accent: str = "#0729fd", color: str = "#ffffff",
                    per_set: int = 5, breaks: list[int] | None = None, tilt_words: list[str] | None = None,
                    tilt: float = 35.0, size: float = 0.10, positions: list[list[float]] | None = None,
                    layer: str = "all", pop: float = 0.0, width: int = 1920, height: int = 1080):
    """TOGI's kinetic titles as measured from his video: words snap on one by one around the
    frame in time with speech, a set builds up and is then swapped all at once.

    White words sit behind the person and accent (blue) words in front. An overlay cannot go
    behind someone, so render twice with layer="back" (white words) and layer="front"
    (accent words), and stack: footage, back layer, a cut-out of the person (Magic Mask in
    Resolve), front layer. layer="all" draws both in one clip.
    breaks: word numbers (from 0) where a new set starts; otherwise every `per_set` words.
    positions: one [x, y] (or [x, y, scale]) per word, as frame fractions, to place words by hand.
    tilt_words get a big tilt (about 35 degrees). size is the letter height as a fraction
    of the frame height. pop > 0 adds a scale-in of that many seconds (TOGI uses none).
    """
    if layer not in ("all", "back", "front"):
        raise EditError("layer is all, back or front")
    ws = timed_words(words, text, duration)
    hot = {_key(w) for w in (accent_words or [])}
    tilted = {_key(w) for w in (tilt_words or [])}
    sw, sh, _ = _stage(width, height)
    starts = sorted({0, *(int(b) for b in breaks)}) if breaks else list(range(0, len(ws), max(1, per_set)))
    sets = [ws[a:b] for a, b in zip(starts, starts[1:] + [len(ws)]) if ws[a:b]]
    total = max(duration or 0, ws[-1][2] + 0.5)
    blocks, n = [], 0
    for si, group in enumerate(sets):
        end = sets[si + 1][0][1] if si + 1 < len(sets) else total
        for k, (t, start, _e) in enumerate(group):
            is_hot = _key(t) in hot
            pos = positions[n] if positions and n < len(positions) else _SLOTS[k % len(_SLOTS)]
            n += 1
            if (layer == "back" and is_hot) or (layer == "front" and not is_hot):
                continue
            word = t.upper()
            px = size * sh * (1.15 if is_hot else 1.0) / 0.72      # cap height is about 0.72 em
            if len(pos) > 2:                                       # [x, y, scale]
                px *= float(pos[2])
            px = min(px, 0.86 * sw / max(0.78 * len(word), 1))
            rot = (-tilt if _key(t) in tilted else 0.0)
            style = ("text-shadow:0 0 0 transparent" if is_hot
                     else "text-shadow:0 6px 22px rgba(0,0,0,.28),0 2px 4px rgba(0,0,0,.18)")
            anim = f";animation:vis {end - start:.3f}s linear {start:.3f}s"
            inner = (f"<span class='p' style='animation-delay:{start:.3f}s'>{escape(word)}</span>"
                     if pop > 0 else escape(word))
            blocks.append(f"<div class='w' style='left:{pos[0] * 100:.1f}%;top:{pos[1] * 100:.1f}%;"
                          f"font-size:{px:.0f}px;color:{accent if is_hot else color};--r:{rot:.1f}deg;{style};"
                          f"visibility:hidden{anim}'>{inner}</div>")
    css = (f".w{{position:absolute;transform:translate(-50%,-50%) rotate(var(--r));white-space:nowrap;"
           f"font-family:{HEAVY};font-weight:900;line-height:1;letter-spacing:-0.01em;font-stretch:expanded}}"
           f".p{{display:inline-block;animation:sp {max(pop, 0.01):.3f}s ease-out both}}"
           "@keyframes sp{from{transform:scale(1.3)}to{transform:none}}" + _SHOW)
    return _page("".join(blocks), css, width, height), total


def mid_captions(words: list[dict] | None = None, text: str | None = None, duration: float | None = None,
                 max_words: int = 3, size: int = 104, color: str = "#ffffff", accent: str = "#ffe14a",
                 accent_words: list[str] | None = None, y: float = 0.50, uppercase: bool = False,
                 width: int = 1920, height: int = 1080):
    """One to three words at a time in the middle of the frame, each chunk popping in."""
    ws = timed_words(words, text, duration)
    hot = {_key(w) for w in (accent_words or [])}
    groups = _chunks(ws, max(1, max_words))
    total = max(duration or 0, ws[-1][2] + 0.3)
    divs = []
    for gi, g in enumerate(groups):
        start = g[0][1]
        end = min(groups[gi + 1][0][1], g[-1][2] + 0.6) if gi + 1 < len(groups) else total
        spans = " ".join(
            f"<span style='color:{accent if _key(t) in hot else color}'>{escape(t.upper() if uppercase else t)}</span>"
            for t, _s, _e in g)
        divs.append(f"<div class='ch' style='{_window(start, end)}'><div class='in' style='animation-delay:{start:.3f}s'>{spans}</div></div>")
    css = (f".ch{{position:absolute;left:6%;right:6%;top:{y * 100:.1f}%;transform:translateY(-50%);"
           f"text-align:center;font-weight:900;font-size:{size}px;line-height:1.08;"
           f"-webkit-text-stroke:{max(2, size // 13)}px #000;paint-order:stroke fill;"
           "text-shadow:0 8px 22px rgba(0,0,0,.55)}"
           ".in{animation:cp .2s cubic-bezier(.2,1.5,.4,1) both}"
           "@keyframes cp{from{transform:scale(.7);opacity:0}to{transform:none;opacity:1}}" + _SHOW)
    return _page("".join(divs), css, width, height), total


def title_bar(text: str, duration: float, sub: str = "", accent: str = "#ff5a36", y: float = 0.06,
              light: bool = False, size: int = 58, width: int = 1920, height: int = 1080):
    """A title held for the whole video (set duration to the video's length), sliding in at the start."""
    if not text.strip():
        raise EditError("title_bar needs text")
    bg, fg = ("#ffffff", "#111111") if light else ("rgba(12,12,14,.86)", "#ffffff")
    css = (f".tb{{position:absolute;left:50%;top:{y * 100:.1f}%;transform:translateX(-50%);max-width:88%;"
           f"background:{bg};color:{fg};border-radius:18px;padding:16px 34px 18px;text-align:center;"
           f"border-bottom:8px solid {accent};box-shadow:0 14px 40px rgba(0,0,0,.35);"
           "animation:drop .45s cubic-bezier(.2,1.2,.3,1) both}"
           f".t{{font-size:{size}px;font-weight:900;letter-spacing:-0.01em;line-height:1.05}}"
           f".s{{font-size:{int(size * 0.55)}px;font-weight:600;opacity:.75;margin-top:6px}}"
           "@keyframes drop{from{opacity:0;transform:translate(-50%,-60px)}to{opacity:1;transform:translate(-50%,0)}}")
    s = f"<div class='s'>{escape(sub)}</div>" if sub else ""
    return _page(f"<div class='tb'><div class='t'>{escape(text)}</div>{s}</div>", css, width, height), float(duration)


_COUNT_JS = """
const ease = p => 1 - Math.pow(1 - p, 3);
window.seek = t => {
  for (const el of document.querySelectorAll('[data-v]')) {
    const v = +el.dataset.v, at = +el.dataset.at, d = +el.dataset.d;
    const p = Math.min(Math.max((t - at) / d, 0), 1);
    el.textContent = (v * ease(p)).toLocaleString('en-US',
      {minimumFractionDigits: +el.dataset.dp, maximumFractionDigits: +el.dataset.dp});
  }
};
window.seek(0);
"""


def _decimals(v) -> int:
    s = str(v)
    return len(s.split(".")[1]) if "." in s else 0


def _number(value, at: float, count: float = 0.8) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return escape(str(value))   # not a number: shown as written
    return f"<span data-v='{v}' data-at='{at:.3f}' data-d='{count}' data-dp='{_decimals(value)}'>0</span>"


def end_card(items: list[dict], title: str = "", duration: float = 4.0, accent: str = "#ffe14a",
             keep_clear: list[float] | None = CAPTION_BAND, width: int = 1920, height: int = 1080):
    """Numbers or macros on a card, each counting up in turn: items are {"label", "value", "unit"?}."""
    if not items:
        raise EditError("end_card needs items such as {\"label\": \"Protein\", \"value\": 210, \"unit\": \"g\"}")
    sw, sh, _ = _stage(width, height)
    rows = []
    for i, it in enumerate(items):
        if "label" not in it or "value" not in it:
            raise EditError("each end_card item needs a label and a value")
        at = 0.45 + i * 0.25
        unit = f"<small>{escape(str(it.get('unit', '')))}</small>" if it.get("unit") else ""
        rows.append(f"<div class='it' style='animation-delay:{at:.2f}s'><div class='v'>{_number(it['value'], at)}{unit}</div>"
                    f"<div class='l'>{escape(str(it['label']))}</div></div>")
    cols = min(len(items), 2 if sw < sh else 4)
    want = 260 + 230 * -(-len(items) // cols)
    top, h = keep_clear_box(sh, want, keep_clear)
    hold = duration - 0.4
    css = (f".card{{position:absolute;left:50%;top:{top:.0f}px;min-height:{h:.0f}px;max-height:{h:.0f}px;"
           f"width:{min(sw * 0.86, 1500):.0f}px;transform:translateX(-50%);box-sizing:border-box;padding:40px 48px;"
           "border-radius:36px;background:rgba(14,15,18,.92);color:#fff;box-shadow:0 30px 80px rgba(0,0,0,.45);"
           f"display:flex;flex-direction:column;justify-content:center;"
           f"animation:in .45s cubic-bezier(.2,1.1,.3,1) both,out .4s ease-in {hold:.3f}s forwards}}"
           ".ttl{font-size:52px;font-weight:900;margin-bottom:26px;text-align:center}"
           f".grid{{display:grid;grid-template-columns:repeat({cols},1fr);gap:26px 30px}}"
           ".it{text-align:center;opacity:0;animation:up .35s ease-out both}"
           f".v{{font-size:112px;font-weight:900;color:{accent};line-height:1;font-variant-numeric:tabular-nums}}"
           ".v small{font-size:52px;margin-left:6px;opacity:.9}"
           ".l{font-size:36px;font-weight:700;opacity:.8;margin-top:8px;text-transform:uppercase;letter-spacing:.04em}"
           "@keyframes in{from{opacity:0;transform:translate(-50%,40px) scale(.96)}to{opacity:1;transform:translate(-50%,0)}}"
           "@keyframes out{to{opacity:0}}"
           "@keyframes up{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:none}}")
    ttl = f"<div class='ttl'>{escape(title)}</div>" if title else ""
    body = f"<div class='card'>{ttl}<div class='grid'>{''.join(rows)}</div></div>"
    return _page(body, css, width, height, _COUNT_JS), float(duration)


def counter(label: str = "REP", ticks: list[float] | None = None, value: int | None = None, start: int = 1,
            total: int | None = None, duration: float | None = None, accent: str = "#ffe14a",
            x: float = 0.92, y: float = 0.12, size: int = 120, width: int = 1920, height: int = 1080):
    """A rep counter that ticks at the given times, or a day counter showing one value.

    ticks: seconds (from the overlay start) when each rep lands; the count starts at `start`
    on the first tick. value: show one number (e.g. DAY 37) with a single pop.
    total: shown as "3/8".
    """
    if ticks is None and value is None:
        raise EditError("counter needs ticks (rep times) or a value (e.g. day 37)")
    if ticks is not None:
        ticks = sorted(float(t) for t in ticks)
        if not ticks:
            raise EditError("counter ticks is empty")
        duration = duration or ticks[-1] + 1.5
        first = start
    else:
        ticks, first = [0.15], int(value)
        duration = duration or 3.0
    of = f"<span class='of'>/{int(total)}</span>" if total else ""
    css = (f".ct{{position:absolute;left:{x * 100:.1f}%;top:{y * 100:.1f}%;transform:translate(-100%,0);"
           "text-align:right;color:#fff;text-shadow:0 6px 18px rgba(0,0,0,.6);"
           "animation:fin .3s ease-out both}"
           f".lb{{font-size:{int(size * 0.32)}px;font-weight:800;letter-spacing:.12em;opacity:.85}}"
           f".n{{display:inline-block;font-size:{size}px;font-weight:900;line-height:.95;color:{accent};"
           f"-webkit-text-stroke:{max(2, size // 22)}px #000;paint-order:stroke fill;"
           "font-variant-numeric:tabular-nums;transform-origin:right center}"
           ".nr{white-space:nowrap}"
           f".of{{font-size:{int(size * 0.45)}px;font-weight:800;margin-left:6px}}"
           "@keyframes fin{from{opacity:0}to{opacity:1}}")
    js = (f"const T={json.dumps(ticks)},F={first};const n=document.getElementById('n'),ct=document.getElementById('ct');"
          "window.seek=t=>{let k=0;while(k<T.length&&T[k]<=t)k++;"
          "ct.style.visibility=k?'visible':'hidden';if(!k)return;n.textContent=F+k-1;"
          "const s=t-T[k-1];n.style.transform=`scale(${1+0.45*Math.exp(-s*11)})`;};window.seek(0);")
    body = (f"<div class='ct' id='ct'><div class='lb'>{escape(label.upper())}</div>"
            f"<div class='nr'><span class='n' id='n'></span>{of}</div></div>")
    return _page(body, css, width, height, js), float(duration)


def clipper(headline: str, duration: float, sub: str = "", accent_words: list[str] | None = None,
            accent: str = "#ffe14a", footage_aspect: float = 16 / 9, band: str = "#000000", size: int = 72,
            width: int = 1080, height: int = 1920):
    """The "clipper" layout for vertical video: bands above and below a fitted landscape clip,
    with a headline in the top band (and an optional line in the bottom band).

    Put the landscape clip on the timeline scaled to fit the width; this overlay draws the
    bands and text. Set duration to the clip's length.
    """
    if not headline.strip():
        raise EditError("clipper needs a headline")
    sw, sh, _ = _stage(width, height)
    clip_h = sw / footage_aspect
    band_h = (sh - clip_h) / 2
    if band_h < 80:
        raise EditError("the clipper layout is for vertical frames, where a landscape clip leaves bands")
    hot = {_key(w) for w in (accent_words or [])}
    words = " ".join(f"<span style='color:{accent}'>{escape(w)}</span>" if _key(w) in hot else escape(w)
                     for w in headline.split())
    css = (f".b{{position:absolute;left:0;right:0;height:{band_h:.0f}px;background:{band};display:flex;"
           "align-items:center;justify-content:center;box-sizing:border-box;padding:0 6%}"
           ".top{top:0;align-items:flex-end;padding-bottom:36px}.bot{bottom:0;align-items:flex-start;padding-top:36px}"
           f".h{{color:#fff;font-size:{size}px;font-weight:900;line-height:1.1;text-align:center;"
           "animation:hin .4s ease-out both}"
           f".s{{color:#fff;opacity:.85;font-size:{int(size * 0.6)}px;font-weight:700;text-align:center}}"
           "@keyframes hin{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}")
    bottom = f"<div class='s'>{escape(sub)}</div>" if sub else ""
    body = f"<div class='b top'><div class='h'>{words}</div></div><div class='b bot'>{bottom}</div>"
    return _page(body, css, width, height), float(duration)


CONDENSED = "'Bebas Neue','Oswald','League Gothic','Barlow Condensed','Arial Narrow','Helvetica Neue',sans-serif"


def spaced_title(words: list[dict] | None = None, text: str | None = None, duration: float | None = None,
                 per_group: int = 1, size: int = 190, spacing: float = 0.45, y: float = 0.55,
                 color: str = "#ffffff", rough: bool = True, fade: float = 0.25,
                 width: int = 1920, height: int = 1080):
    """Cinematic title words, one (or `per_group`) at a time: tall condensed capitals spread wide
    with letter spacing, a soft shadow and an optional worn print texture (`rough`). Each word
    fades in from a slight blur on its own time and holds until the next.

    The look of military and sports cinematic edits: the voice-over's key words set
    across the picture, quiet and large, rather than captions that shout.
    """
    ws = timed_words(words, text, duration)
    if spacing < 0 or fade < 0:
        raise EditError("spacing and fade cannot be negative")
    groups = _chunks(ws, max(1, per_group))
    total = max(duration or 0, ws[-1][2] + 0.4)
    divs = []
    for gi, g in enumerate(groups):
        start = g[0][1]
        end = groups[gi + 1][0][1] if gi + 1 < len(groups) else total
        label = escape(" ".join(t.upper().strip(_PUNCT) or t for t, _s, _e in g))
        divs.append(f"<div class='st' style='{_window(start, end)}'>"
                    f"<div class='in' style='animation-delay:{start:.3f}s'>{label}</div></div>")
    grain = ("filter:url(#rough);" if rough else "")
    css = (font_faces("bebas") +   # bundled, so the spaced title looks the same on every computer
           f".st{{position:absolute;left:3%;right:3%;top:{y * 100:.1f}%;transform:translateY(-50%);"
           f"text-align:center;white-space:nowrap}}"
           f".in{{display:inline-block;font-family:{CONDENSED};font-weight:700;font-size:{size}px;line-height:1;"
           f"letter-spacing:{spacing:.3f}em;margin-right:-{spacing:.3f}em;color:{color};{grain}"
           "text-shadow:0 6px 24px rgba(0,0,0,.55);"
           f"animation:sti {max(fade, 0.01):.3f}s ease-out both}}"
           "@keyframes sti{from{opacity:0;filter:blur(6px)}to{opacity:1}}" + _SHOW)
    svg = ("<svg width='0' height='0' style='position:absolute'><filter id='rough'>"
           "<feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' seed='3'/>"
           "<feColorMatrix values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.4 1.6'/>"
           "<feComposite in='SourceGraphic' operator='in'/></filter></svg>") if rough else ""
    return _page(svg + "".join(divs), css, width, height), total


def plain_captions(words: list[dict] | None = None, text: str | None = None, duration: float | None = None,
                   max_words: int = 2, size: int = 64, y: float = 0.62, color: str = "#ffffff",
                   uppercase: bool = True, width: int = 1920, height: int = 1080):
    """Quiet captions: one or two words at a time in plain bold white, no box, no outline,
    no colour, no bounce. They cut on with the word and sit just below the middle.

    The editor-tutorial look (and the opposite of the busy, highlighted caption style
    that reads as auto-generated): it lets the footage carry the video.
    """
    ws = timed_words(words, text, duration)
    groups = _chunks(ws, max(1, max_words))
    total = max(duration or 0, ws[-1][2] + 0.3)
    divs = []
    for gi, g in enumerate(groups):
        start = g[0][1]
        end = min(groups[gi + 1][0][1], g[-1][2] + 0.5) if gi + 1 < len(groups) else total
        label = escape(" ".join(t.upper() if uppercase else t for t, _s, _e in g))
        divs.append(f"<div class='pc' style='{_window(start, end)}'>{label}</div>")
    css = (f".pc{{position:absolute;left:8%;right:8%;top:{y * 100:.1f}%;transform:translateY(-50%);"
           f"text-align:center;font-weight:800;font-size:{size}px;line-height:1.1;color:{color};"
           "letter-spacing:0.01em;text-shadow:0 2px 10px rgba(0,0,0,.45)}" + _SHOW)
    return _page("".join(divs), css, width, height), total


def burst(x: float = 0.5, y: float = 0.45, radius: float = 0.16, duration: float = 0.8, strokes: int = 9,
          color: str = "#ffffff", width: int = 1080, height: int = 1920):
    """Hand-drawn marks bursting out around a point, then fading: the chalky emphasis lines
    editors draw around a subject on a hit, a catch or a lockout.

    x, y (0 to 1) place the centre; radius is a share of the frame's short side.
    """
    if not (0 <= x <= 1 and 0 <= y <= 1) or radius <= 0 or duration <= 0 or strokes < 3:
        raise EditError("burst needs x and y between 0 and 1, a radius and duration above 0, and 3 or more strokes")
    sw, sh, _ = _stage(width, height)
    r = radius * min(sw, sh)
    cx, cy = x * sw, y * sh
    marks = []
    for k in range(strokes):
        ang = 360 * k / strokes + (17 if k % 2 else -9)
        ln = r * (0.32 if k % 3 else 0.42)
        marks.append(f"<div class='mk' style='left:{cx:.1f}px;top:{cy:.1f}px;height:{ln:.1f}px;"
                     f"transform:rotate({ang:.1f}deg) translateY(-{r:.1f}px);animation-delay:{0.012 * (k % 4):.3f}s'></div>")
    grow = min(0.18, duration / 3)
    css = (f".mk{{position:absolute;width:{max(8, r * 0.08):.1f}px;margin-left:-{max(4, r * 0.04):.1f}px;"
           f"background:{color};border-radius:40% 60% 50% 45%;transform-origin:50% 0;opacity:0;"
           f"filter:url(#chalk);animation:bm {duration:.3f}s linear both}}"
           f"@keyframes bm{{0%{{opacity:0;clip-path:inset(0 0 100% 0)}}{100 * grow / duration:.1f}%{{opacity:1;clip-path:inset(0)}}"
           f"70%{{opacity:1}}100%{{opacity:0}}}}")
    svg = ("<svg width='0' height='0' style='position:absolute'><filter id='chalk'>"
           "<feTurbulence type='fractalNoise' baseFrequency='0.6' numOctaves='2' seed='7'/>"
           "<feDisplacementMap in='SourceGraphic' scale='6'/></filter></svg>")
    return _page(svg + "".join(marks), css, width, height), duration


_HUD = {
    # kind: (label shown above the text, text colour, accent, default sub)
    "mission": ("MISSION", "#ffffff", "#ffe14a", ""),
    "passed": ("", "#ffe14a", "#ffe14a", ""),
    "failed": ("", "#ff3b30", "#ff3b30", ""),
    "warning": ("WARNING", "#111111", "#ffd400", ""),
}


def hud_card(text: str, kind: str = "mission", sub: str = "", duration: float = 2.5, y: float = 0.38,
             size: int = 110, width: int = 1080, height: int = 1920):
    """Game-style cards for a stake and its payoff (our own design, no game's art or font).

    kind: mission (the stake: a label, then the goal, sliding in), passed (the payoff:
    big text punching in, sub such as "+RESPECT"), failed (red, the frame darkens behind it),
    warning (black-on-yellow hazard bar for "Do NOT let a ... see this" hooks).
    """
    if kind not in _HUD:
        raise EditError(f"hud_card kind must be one of {', '.join(_HUD)}")
    if not text.strip():
        raise EditError("hud_card needs text")
    label, fg, accent, _ = _HUD[kind]
    out = max(float(duration) - 0.35, 0.3)
    shadow = "0 8px 0 rgba(0,0,0,.55),0 0 30px rgba(0,0,0,.6)"
    base = (f".h{{position:absolute;left:0;right:0;top:{y * 100:.1f}%;text-align:center;font-family:{HEAVY};"
            f"animation:hout .3s ease-in {out:.3f}s forwards}}"
            f".t{{font-size:{size}px;font-weight:900;line-height:.95;letter-spacing:-0.01em;color:{fg};"
            "text-transform:uppercase;padding:0 6%}"
            f".s{{font-size:{int(size * 0.42)}px;font-weight:800;margin-top:14px;color:#fff;letter-spacing:.06em;"
            f"text-shadow:{shadow}}}"
            "@keyframes hout{to{opacity:0}}")
    sub_html = f"<div class='s'>{escape(sub)}</div>" if sub else ""
    if kind == "mission":
        css = base + (f".lb{{display:inline-block;font-size:{int(size * 0.36)}px;font-weight:900;letter-spacing:.3em;"
                      f"color:#111;background:{accent};padding:6px 22px 6px 30px;margin-bottom:16px}}"
                      f".t{{text-shadow:{shadow};animation:slide .45s cubic-bezier(.2,1,.3,1) .12s both}}"
                      ".lb{animation:slide .35s cubic-bezier(.2,1,.3,1) both}"
                      "@keyframes slide{from{opacity:0;transform:translateX(-120px)}to{opacity:1;transform:none}}")
        body = f"<div class='h'><div class='lb'>{label}</div><div class='t'>{escape(text)}</div>{sub_html}</div>"
    elif kind == "warning":
        stripes = f"repeating-linear-gradient(-45deg,{accent} 0 34px,#111 34px 68px)"
        css = base + (f".bar{{background:{accent};border-top:22px solid transparent;border-bottom:22px solid transparent;"
                      f"border-image:{stripes} 22;padding:26px 0 30px;box-shadow:0 20px 60px rgba(0,0,0,.5);"
                      "animation:slam .32s cubic-bezier(.2,1.4,.3,1) both}"
                      f".lb{{font-size:{int(size * 0.34)}px;font-weight:900;letter-spacing:.35em;color:#111;margin-bottom:8px}}"
                      ".s{color:#111;text-shadow:none}"
                      "@keyframes slam{from{opacity:0;transform:scaleY(.2)}to{opacity:1;transform:none}}")
        body = f"<div class='h'><div class='bar'><div class='lb'>{label}</div><div class='t'>{escape(text)}</div>{sub_html}</div></div>"
    else:
        dim = ("<div class='dim'></div>" if kind == "failed" else "")
        css = base + (f".t{{font-size:{int(size * 1.25)}px;-webkit-text-stroke:{max(3, size // 18)}px #000;"
                      f"paint-order:stroke fill;text-shadow:{shadow};animation:punch .4s cubic-bezier(.2,1.5,.3,1) both}}"
                      ".s{animation:up .3s ease-out .3s both}"
                      ".dim{position:absolute;inset:0;background:radial-gradient(ellipse at center,rgba(60,0,0,.25),rgba(0,0,0,.75));"
                      f"animation:fade .4s ease-out both,hout .3s ease-in {out:.3f}s forwards}}"
                      "@keyframes punch{from{opacity:0;transform:scale(1.8)}to{opacity:1;transform:none}}"
                      "@keyframes up{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}"
                      "@keyframes fade{from{opacity:0}to{opacity:1}}")
        body = f"{dim}<div class='h'><div class='t'>{escape(text)}</div>{sub_html}</div>"
    return _page(body, css, width, height), float(duration)
