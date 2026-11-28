"""The arsenal's building blocks: ways for text to arrive and leave, caption styles, and
overlay transitions. Each is one template with many named variants, so the arsenal
(`arsenal.py`) can store hundreds of presets as small settings rather than code.

- text_fx: any short text with an entry (pop, slam, typewriter, mask rise, decode...),
  an exit, and a look (outline, box, neon, 3D...).
- caption_style: running captions from word timings in one of many styles (karaoke fill,
  box on the active word, one word at a time, colour sweep...).
- wipe: an overlay transition that covers the frame at a cut and uncovers it (flash,
  dip, swipe band, iris, shutter, blinds, glitch blocks, light leak...). The cut sits
  at the middle of its duration.

All draw on a transparent page and step frame by frame in the renderer.
"""

from __future__ import annotations

import json
from html import escape

from .edl import EditError
from .kinetic import _SHOW, _chunks, _key, _window, timed_words
from .pagekit import _page, _stage, font_faces

FAMILIES = {
    "heavy": ("'Montserrat','Inter',Arial,sans-serif", 900, "montserrat"),
    "condensed": ("'Anton','Bebas Neue',Impact,sans-serif", 400, "anton"),
    "tall": ("'Bebas Neue','Anton',Impact,sans-serif", 400, "bebas"),
    "clean": ("'Inter',Arial,sans-serif", 800, "inter"),
    "mono": ("'JetBrains Mono','Courier New',monospace", 800, None),
    "serif": ("Georgia,'Times New Roman',serif", 700, None),
}

# Entry animations. Each: (unit: "letter" | "word" | "line", keyframes body, length s, easing)
ENTRIES = {
    "pop": ("word", "from{opacity:0;transform:scale(.4)}70%{opacity:1;transform:scale(1.12)}to{opacity:1;transform:none}", .3, "ease-out"),
    "slam": ("word", "from{opacity:0;transform:scale(2.6)}60%{opacity:1;transform:scale(.94)}to{opacity:1;transform:none}", .22, "cubic-bezier(.2,1,.3,1)"),
    "snap": ("word", "from,to{opacity:1}", .01, "linear"),
    "fade": ("line", "from{opacity:0}to{opacity:1}", .35, "ease-out"),
    "rise": ("word", "from{opacity:0;transform:translateY(.6em)}to{opacity:1;transform:none}", .35, "cubic-bezier(.2,.9,.2,1)"),
    "drop": ("word", "from{opacity:0;transform:translateY(-1.4em)}60%{opacity:1;transform:translateY(.12em)}80%{transform:translateY(-.05em)}to{opacity:1;transform:none}", .45, "ease-out"),
    "slide_left": ("line", "from{opacity:0;transform:translateX(40%)}to{opacity:1;transform:none}", .4, "cubic-bezier(.2,.9,.2,1)"),
    "slide_right": ("line", "from{opacity:0;transform:translateX(-40%)}to{opacity:1;transform:none}", .4, "cubic-bezier(.2,.9,.2,1)"),
    "mask_rise": ("word", "from{opacity:1;transform:translateY(105%)}to{opacity:1;transform:none}", .42, "cubic-bezier(.2,.9,.1,1)"),
    "blur_in": ("word", "from{opacity:0;filter:blur(14px);transform:scale(1.15)}to{opacity:1;filter:blur(0);transform:none}", .45, "ease-out"),
    "zoom_through": ("line", "from{opacity:0;transform:scale(6);filter:blur(8px)}to{opacity:1;transform:none;filter:blur(0)}", .32, "cubic-bezier(.1,.9,.2,1)"),
    "shrink_in": ("line", "from{opacity:0;transform:scale(.2)}to{opacity:1;transform:none}", .35, "cubic-bezier(.2,1.3,.4,1)"),
    "stamp": ("line", "from{opacity:0;transform:scale(2.2) rotate(-14deg)}55%{opacity:1;transform:scale(.92) rotate(-6deg)}to{opacity:1;transform:rotate(-6deg)}", .3, "ease-out"),
    "flip": ("word", "from{opacity:0;transform:perspective(600px) rotateX(-90deg)}to{opacity:1;transform:none}", .4, "ease-out"),
    "spin": ("word", "from{opacity:0;transform:rotate(-180deg) scale(.3)}to{opacity:1;transform:none}", .45, "cubic-bezier(.2,1.2,.4,1)"),
    "bounce": ("letter", "from{opacity:0;transform:translateY(-.8em)}50%{opacity:1;transform:translateY(.15em)}75%{transform:translateY(-.06em)}to{opacity:1;transform:none}", .45, "ease-out"),
    "letters": ("letter", "from{opacity:0;transform:translateY(.4em) scale(.6)}to{opacity:1;transform:none}", .22, "ease-out"),
    "wave": ("letter", "0%{opacity:0;transform:translateY(.5em)}50%{opacity:1;transform:translateY(-.2em)}to{opacity:1;transform:none}", .4, "ease-in-out"),
    "typewriter": ("letter", "from,to{opacity:1}", .01, "linear"),
    "decode": ("letter", "from,to{opacity:1}", .01, "linear"),
    "wipe": ("line", "from{clip-path:inset(-20% 100% -20% 0)}to{clip-path:inset(-20% 0 -20% 0)}", .45, "cubic-bezier(.6,0,.2,1)"),
    "split": ("line", "from{opacity:0;letter-spacing:.8em}to{opacity:1}", .45, "cubic-bezier(.2,.9,.2,1)"),
    "glitch": ("line", "0%{opacity:0;transform:translateX(-8px);text-shadow:6px 0 #ff2a6d,-6px 0 #05d9e8}"
               "20%{opacity:1;transform:translateX(6px)}40%{transform:translateX(-4px);clip-path:inset(30% 0 40% 0)}"
               "60%{transform:translateX(3px);clip-path:inset(0)}80%{text-shadow:2px 0 #ff2a6d,-2px 0 #05d9e8}"
               "to{opacity:1;transform:none}", .4, "steps(8)"),
    "flicker": ("line", "0%{opacity:0}10%{opacity:1}15%{opacity:.1}25%{opacity:1}30%{opacity:.2}45%{opacity:1}55%{opacity:.4}to{opacity:1}", .6, "linear"),
    "shake": ("line", "0%{opacity:1;transform:translate(0)}20%{transform:translate(-10px,4px)}40%{transform:translate(8px,-6px)}"
              "60%{transform:translate(-6px,3px)}80%{transform:translate(4px,-2px)}to{opacity:1;transform:none}", .35, "linear"),
    "marker": ("line", "from{opacity:1}to{opacity:1}", .01, "linear"),      # a highlighter sweep behind the text
    "underline": ("line", "from{opacity:1}to{opacity:1}", .01, "linear"),   # a bar draws under the text
    "outline_fill": ("line", "from{opacity:1}to{opacity:1}", .01, "linear"),  # outline first, then it fills
}
EXITS = {
    "none": None,
    "fade": "to{opacity:0}",
    "pop_out": "30%{transform:scale(1.1)}to{opacity:0;transform:scale(0)}",
    "drop_out": "to{opacity:0;transform:translateY(1em)}",
    "rise_out": "to{opacity:0;transform:translateY(-1em)}",
    "blur_out": "to{opacity:0;filter:blur(14px);transform:scale(1.1)}",
    "wipe_out": "to{clip-path:inset(-20% 0 -20% 100%)}",
    "zoom_out": "to{opacity:0;transform:scale(5);filter:blur(6px)}",
    "glitch_out": "20%{transform:translateX(8px);text-shadow:6px 0 #ff2a6d,-6px 0 #05d9e8}60%{clip-path:inset(40% 0 30% 0)}to{opacity:0}",
}
LOOKS = {
    "shadow": "text-shadow:0 6px 24px rgba(0,0,0,.6),0 2px 4px rgba(0,0,0,.4)",
    "outline": "-webkit-text-stroke:var(--sw) #000;paint-order:stroke fill;text-shadow:0 6px 16px rgba(0,0,0,.45)",
    "native": "-webkit-text-stroke:calc(var(--sw)*.5) #000;paint-order:stroke fill",
    "box": "background:var(--box);padding:.08em .32em .12em;border-radius:.12em;box-decoration-break:clone;-webkit-box-decoration-break:clone",
    "pill": "background:var(--box);padding:.1em .6em .14em;border-radius:1em;box-decoration-break:clone;-webkit-box-decoration-break:clone",
    "neon": "text-shadow:0 0 .08em #fff,0 0 .25em var(--accent),0 0 .6em var(--accent),0 0 1.2em var(--accent)",
    "3d": "text-shadow:.03em .03em 0 var(--deep),.06em .06em 0 var(--deep),.09em .09em 0 var(--deep),.12em .12em 0 var(--deep),.15em .15em .3em rgba(0,0,0,.5)",
    "gradient": "background:linear-gradient(180deg,#fff 20%,var(--accent));-webkit-background-clip:text;background-clip:text;color:transparent!important;filter:drop-shadow(0 6px 14px rgba(0,0,0,.5))",
    "plain": "",
}

_DECODE_JS = """
const GL='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#$%&@';
window.seek=t=>{for(const el of document.querySelectorAll('[data-dc]')){const at=+el.dataset.dc;
 if(t>=at){el.textContent=el.dataset.ch;continue;}
 if(t<at-0.5){el.textContent='\\u00a0';el.style.opacity=0;continue;}
 el.style.opacity=1;const k=Math.floor(t*30)+(+el.dataset.i)*7;el.textContent=GL[(k*13)%GL.length];}};
window.seek(0);
"""


def _family(name: str):
    if name not in FAMILIES:
        raise EditError(f"family is one of {', '.join(FAMILIES)}")
    return FAMILIES[name]


def text_fx(text: str, entry: str = "pop", exit: str = "fade", look: str = "outline", duration: float = 2.0,
            at: float = 0.1, stagger: float | None = None, size: int = 110, family: str = "heavy",
            color: str = "#ffffff", accent: str = "#ffe14a", accent_words: list[str] | None = None,
            box: str = "rgba(0,0,0,.82)", uppercase: bool = True, x: float = 0.5, y: float = 0.5,
            tilt: float = 0.0, align: str = "center", width: int = 1920, height: int = 1080):
    """Any short text with a named entry, exit and look: the arsenal's text building block.

    entry: pop, slam, snap, fade, rise, drop, slide_left, slide_right, mask_rise, blur_in,
    zoom_through, shrink_in, stamp, flip, spin, bounce, letters, wave, typewriter, decode,
    wipe, split, glitch, flicker, shake, marker, underline, outline_fill.
    exit: none, fade, pop_out, drop_out, rise_out, blur_out, wipe_out, zoom_out, glitch_out.
    look: shadow, outline, native, box, pill, neon, 3d, gradient, plain.
    x, y: the centre of the text (frame fractions); with align left or right, x is that edge.
    family: heavy, condensed, tall, clean, mono, serif (the type family; `font` still overrides).
    """
    if not text.strip():
        raise EditError("text_fx needs text")
    for what, value, known in (("entry", entry, ENTRIES), ("exit", exit, EXITS), ("look", look, LOOKS)):
        if value not in known:
            raise EditError(f"{what} {value!r} is not known; there are: {', '.join(known)}")
    unit, frames, length, ease = ENTRIES[entry]
    fam, weight, embed = _family(family)
    hot = {_key(w) for w in (accent_words or [])}
    step = stagger if stagger is not None else {"letter": 0.035, "word": 0.09, "line": 0.0}[unit]
    if entry == "typewriter":
        step = stagger if stagger is not None else 0.05
    words = (text.upper() if uppercase else text).split()
    parts, i = [], 0
    for wi, w in enumerate(words):
        colour = accent if _key(text.split()[wi]) in hot else color
        if unit == "letter":
            letters = []
            for ch in w:
                d = at + i * step
                if entry == "decode":
                    letters.append(f"<span class='u' data-dc='{d + 0.35:.3f}' data-i='{i}' data-ch='{escape(ch)}'>"
                                   f"{escape(ch)}</span>")
                else:
                    letters.append(f"<span class='u' style='animation-delay:{d:.3f}s'>{escape(ch)}</span>")
                i += 1
            parts.append(f"<span class='w' style='color:{colour}'>{''.join(letters)}</span>")
            i += 1
        elif unit == "word":
            inner = f"<span class='u' style='animation-delay:{at + wi * step:.3f}s'>{escape(w)}</span>"
            parts.append(f"<span class='w m' style='color:{colour}'>{inner}</span>" if entry == "mask_rise"
                         else f"<span class='w' style='color:{colour}'>{inner}</span>")
        else:
            parts.append(f"<span class='w' style='color:{colour}'>{escape(w)}</span>")
    last_in = at + max(i, len(words)) * step + length
    if entry == "decode":
        last_in += 0.35
    out_len = 0.3
    out_at = max(duration - out_len, last_in)
    duration = max(duration, last_in + (out_len if exit != "none" else 0.05))
    line_anim = f"animation:in {length:.3f}s {ease} {at:.3f}s both" if unit == "line" else ""
    exit_anim = (f"animation:out {out_len}s ease-in {out_at:.3f}s forwards" if EXITS[exit] else "")
    unit_css = (f".u{{display:inline-block;opacity:0;animation:in {length:.3f}s {ease} both}}"
                if unit != "line" else "")
    if entry == "typewriter":
        unit_css = ".u{display:inline-block;opacity:0;animation:in .01s steps(1) both}"
    if entry == "decode":
        unit_css = ".u{display:inline-block;min-width:.5em;text-align:center}"
    extra = ""
    if entry == "marker":
        extra = (f".t{{background:linear-gradient(var(--accent),var(--accent)) no-repeat 0 60%/0% 78%;"
                 f"animation:mk .45s cubic-bezier(.6,0,.2,1) {at:.3f}s both}}"
                 "@keyframes mk{to{background-size:100% 78%}}")
    elif entry == "underline":
        extra = (f".t{{background:linear-gradient(var(--accent),var(--accent)) no-repeat 0 100%/0% .12em;"
                 f"padding-bottom:.08em;animation:ul .4s cubic-bezier(.6,0,.2,1) {at:.3f}s both}}"
                 "@keyframes ul{to{background-size:100% .12em}}")
    elif entry == "outline_fill":
        extra = (f".t .w{{-webkit-text-stroke:var(--sw) {color};color:transparent!important;"
                 f"animation:of .5s ease-out {at + 0.35:.3f}s both}}"
                 "@keyframes of{to{color:var(--fill)}}")
    elif entry == "split":
        line_anim = f"animation:in {length:.3f}s {ease} {at:.3f}s both"
    outer = f"<div class='o'><div class='t'>{' '.join(parts)}</div></div>"
    css = ((font_faces(embed) if embed else "") +
           f":root{{--accent:{accent};--box:{box};--deep:{'#000' if look != '3d' else _darker(accent)};"
           f"--sw:{max(2, size // 14)}px;--fill:{color}}}"
           f".o{{position:absolute;left:{x * 100:.1f}%;top:{y * 100:.1f}%;width:{90 if align == 'center' else 88}%;"
           f"transform:translate({'-50%' if align == 'center' else '0'},-50%) rotate({tilt:.1f}deg);"
           f"text-align:{align};{exit_anim}}}"
           f".t{{display:inline;font-family:{fam};font-weight:{weight};font-size:{size}px;line-height:1.12;"
           f"color:{color};{LOOKS[look]};{line_anim}}}"
           ".w{display:inline-block;white-space:nowrap}.m{overflow:hidden;vertical-align:bottom;padding:0 .02em}"
           f"{unit_css}@keyframes in{{{frames}}}"
           + (f"@keyframes out{{{EXITS[exit]}}}" if EXITS[exit] else "") + extra)
    if look in ("box", "pill"):
        css += ".t{display:inline;line-height:1.35}"
    return _page(outer, css, width, height, _DECODE_JS if entry == "decode" else ""), float(duration)


def _darker(hex_colour: str) -> str:
    h = hex_colour.lstrip("#")
    if len(h) != 6:
        return "#000"
    r, g, b = (int(h[i:i + 2], 16) // 3 for i in (0, 2, 4))
    return f"#{r:02x}{g:02x}{b:02x}"


CAPTION_STYLES = ("karaoke", "box_active", "single", "bounce_active", "underline_active", "sweep",
                  "past_colour", "boxed_line", "minimal", "pill_active", "stack_two", "big_keyword")


def caption_style(words: list[dict] | None = None, text: str | None = None, duration: float | None = None,
                  style: str = "box_active", max_words: int = 3, size: int = 92, family: str = "heavy",
                  color: str = "#ffffff", accent: str = "#ffe14a", accent2: str = "#3ddc84",
                  box: str = "rgba(0,0,0,.82)", accent_words: list[str] | None = None, uppercase: bool = True,
                  y: float = 0.68, width: int = 1920, height: int = 1080):
    """Running captions in one of many styles. words are {"word","start","end"} (or give text).

    style: karaoke (the active word fills with colour), box_active (a coloured box jumps to the
    active word), single (one word at a time, popping), bounce_active (the active word jumps
    and grows), underline_active, sweep (keywords alternate two accent colours, the
    "Hormozi" look), past_colour (spoken words stay coloured), boxed_line (the line on a dark
    box), minimal (small, quiet sentence case), pill_active (a rounded pill on the active
    word), stack_two (two lines, the newest below), big_keyword (keywords twice the size).
    """
    if style not in CAPTION_STYLES:
        raise EditError(f"caption style is one of {', '.join(CAPTION_STYLES)}")
    ws = timed_words(words, text, duration)
    fam, weight, embed = _family(family)
    hot = {_key(w) for w in (accent_words or [])}
    per = 1 if style == "single" else max(1, max_words) if style != "stack_two" else max(2, max_words)
    groups = _chunks(ws, per)
    total = max(duration or 0, ws[-1][2] + 0.3)
    if style == "minimal":
        size, uppercase = int(size * 0.62), False
    divs, nk = [], 0
    for gi, g in enumerate(groups):
        start = g[0][1]
        end = min(groups[gi + 1][0][1], g[-1][2] + 0.6) if gi + 1 < len(groups) else total
        spans = []
        for t, s, e in g:
            word = escape(t.upper() if uppercase else t)
            is_hot = _key(t) in hot
            cls = "k" if is_hot else ""
            style_attr = f"animation-delay:{s:.3f}s;--d:{max(e - s, .1):.3f}s"
            if style == "sweep" and is_hot:
                style_attr += f";color:{accent if nk % 2 == 0 else accent2}"
                nk += 1
            spans.append(f"<span class='a {cls}' style='{style_attr}'>{word}</span>")
        divs.append(f"<div class='ln' style='{_window(start, end)}'><span class='in' "
                    f"style='animation-delay:{start:.3f}s'>{' '.join(spans)}</span></div>")
    on = {   # how the active word changes while it is spoken
        "karaoke": f"@keyframes act{{from{{color:{color}}}to{{color:{accent}}}}}.a{{animation:act var(--d) linear both}}",
        "past_colour": f"@keyframes act{{from{{color:{color}}}to{{color:{accent}}}}}.a{{animation:act .05s linear both}}",
        "box_active": (f"@keyframes act{{0%,100%{{background:{accent};color:#111}}}}"
                       ".a{padding:0 .14em;border-radius:.14em;animation:act var(--d) linear}"),
        "pill_active": (f"@keyframes act{{0%,100%{{background:{accent};color:#111}}}}"
                        ".a{padding:0 .3em;border-radius:1em;animation:act var(--d) linear}"),
        "bounce_active": ("@keyframes act{0%{transform:translateY(0) scale(1)}35%{transform:translateY(-.15em) scale(1.18)}"
                          f"100%{{transform:none}}}}.a{{display:inline-block;animation:act var(--d) ease-out}}"
                          f".a{{color:{color}}}"),
        "underline_active": (f"@keyframes act{{0%,100%{{box-shadow:inset 0 -.14em 0 {accent}}}}}"
                             ".a{animation:act var(--d) linear}"),
        "single": ".a{display:inline-block}",
        "sweep": ".a{display:inline-block}",
        "boxed_line": "",
        "minimal": "",
        "stack_two": "",
        "big_keyword": f".k{{font-size:2em;color:{accent};display:inline-block;line-height:1}}",
    }[style]
    pop = ("@keyframes lp{from{transform:scale(.7);opacity:0}to{transform:none;opacity:1}}"
           ".in{display:inline-block;animation:lp .18s cubic-bezier(.2,1.5,.4,1) both}")
    look = {"minimal": "text-shadow:0 2px 10px rgba(0,0,0,.5);font-weight:700",
            "boxed_line": f"background:{box};padding:.1em .4em .14em;border-radius:.18em;box-decoration-break:clone;-webkit-box-decoration-break:clone",
            }.get(style, f"-webkit-text-stroke:{max(2, size // 13)}px #000;paint-order:stroke fill;"
                         "text-shadow:0 6px 18px rgba(0,0,0,.55)")
    css = ((font_faces(embed) if embed else "") +
           f".ln{{position:absolute;left:6%;right:6%;top:{y * 100:.1f}%;transform:translateY(-50%);text-align:center;"
           f"font-family:{fam};font-weight:{weight};font-size:{size}px;line-height:1.2;color:{color}}}"
           f".in{{{look}}}" + (pop if style not in ("minimal", "boxed_line") else ".in{display:inline}")
           + f".k{{color:{accent}}}" + on + _SHOW)
    if style == "stack_two":
        css += ".in{max-width:70%;display:inline-block}"
    return _page("".join(divs), css, width, height), total


WIPES = ("flash", "dip", "swipe", "swipe_double", "iris", "iris_out", "shutter", "split", "blinds",
         "diagonal", "glitch", "light_leak", "burn", "pixels", "bars", "radial", "word")


def wipe(kind: str = "swipe", duration: float = 0.5, color: str = "#ffffff", color2: str = "#111111",
         direction: str = "left", text: str = "", width: int = 1920, height: int = 1080):
    """An overlay transition: it covers the frame by the middle of `duration` and uncovers it after.
    Place it so its middle lands on the cut.

    kind: flash (white pop), dip (to colour and back), swipe (a band crosses the frame),
    swipe_double (two colours chase), iris (a circle closes to the cut, then opens), iris_out,
    shutter (top and bottom close), split (left and right close), blinds (stripes),
    diagonal, glitch (RGB blocks), light_leak (warm glow), burn (film burn), pixels (blocks
    fill in), bars (vertical bars rise), radial (clock wipe), word (a big word fills the frame).
    direction for swipes: left, right, up, down.
    """
    if kind not in WIPES:
        raise EditError(f"wipe kind is one of {', '.join(WIPES)}")
    if duration <= 0:
        raise EditError("wipe needs a duration above 0")
    sw, sh, _ = _stage(width, height)
    d = duration
    move = {"left": ("translateX(105%)", "translateX(-105%)"), "right": ("translateX(-105%)", "translateX(105%)"),
            "up": ("translateY(105%)", "translateY(-105%)"), "down": ("translateY(-105%)", "translateY(105%)")}
    if direction not in move:
        raise EditError("direction is left, right, up or down")
    a, b = move[direction]
    body, css, js = "", "", ""
    full = "position:absolute;inset:0"
    if kind == "flash":
        body = "<div class='f'></div>"
        css = f".f{{{full};background:{color};animation:fl {d}s linear both}}@keyframes fl{{0%{{opacity:0}}45%,55%{{opacity:1}}100%{{opacity:0}}}}"
    elif kind == "dip":
        body = "<div class='f'></div>"
        css = f".f{{{full};background:{color2};animation:fl {d}s ease-in-out both}}@keyframes fl{{0%{{opacity:0}}45%,55%{{opacity:1}}100%{{opacity:0}}}}"
    elif kind in ("swipe", "swipe_double"):
        body = "<div class='s s1'></div>" + ("<div class='s s2'></div>" if kind == "swipe_double" else "")
        css = (f".s{{{full};animation:sw {d}s cubic-bezier(.7,0,.3,1) both}}.s1{{background:{color}}}"
               f".s2{{background:{color2};animation-duration:{d * 0.8:.3f}s;animation-delay:{d * 0.1:.3f}s}}"
               f"@keyframes sw{{0%{{transform:{a}}}45%,55%{{transform:none}}100%{{transform:{b}}}}}")
    elif kind in ("iris", "iris_out"):
        r = (sw ** 2 + sh ** 2) ** 0.5 / 2 + 10
        body = "<div class='f'></div>"
        if kind == "iris":   # frame closes to a dot, then opens: a huge ring shrinks the hole
            css = (f".f{{position:absolute;left:50%;top:50%;width:0;height:0;border-radius:50%;"
                   f"box-shadow:0 0 0 {r:.0f}px {color2};animation:ir {d}s ease-in-out both}}"
                   f"@keyframes ir{{0%{{width:{2 * r:.0f}px;height:{2 * r:.0f}px;margin:-{r:.0f}px 0 0 -{r:.0f}px}}"
                   "45%,55%{width:0;height:0;margin:0}"
                   f"100%{{width:{2 * r:.0f}px;height:{2 * r:.0f}px;margin:-{r:.0f}px 0 0 -{r:.0f}px}}}}")
        else:                # a circle of colour grows over the frame, then shrinks away
            css = (f".f{{position:absolute;left:50%;top:50%;border-radius:50%;background:{color};"
                   f"animation:ir {d}s ease-in-out both}}"
                   f"@keyframes ir{{0%,100%{{width:0;height:0;margin:0}}45%,55%{{width:{2 * r:.0f}px;height:{2 * r:.0f}px;"
                   f"margin:-{r:.0f}px 0 0 -{r:.0f}px}}}}")
    elif kind in ("shutter", "split"):
        if kind == "shutter":
            p1, p2 = "top:0;left:0;right:0;height:50.5%", "bottom:0;left:0;right:0;height:50.5%"
            o1, o2 = "translateY(-101%)", "translateY(101%)"
        else:
            p1, p2 = "left:0;top:0;bottom:0;width:50.5%", "right:0;top:0;bottom:0;width:50.5%"
            o1, o2 = "translateX(-101%)", "translateX(101%)"
        body = "<div class='p p1'></div><div class='p p2'></div>"
        css = (f".p{{position:absolute;background:{color2}}}.p1{{{p1};animation:p1 {d}s cubic-bezier(.7,0,.3,1) both}}"
               f".p2{{{p2};animation:p2 {d}s cubic-bezier(.7,0,.3,1) both}}"
               f"@keyframes p1{{0%,100%{{transform:{o1}}}45%,55%{{transform:none}}}}"
               f"@keyframes p2{{0%,100%{{transform:{o2}}}45%,55%{{transform:none}}}}")
    elif kind in ("blinds", "bars", "pixels"):
        n = 10 if kind != "pixels" else 12
        cells = []
        if kind == "pixels":
            rows = max(1, round(n * sh / sw))
            for r_ in range(rows):
                for c in range(n):
                    k = (r_ * 7 + c * 13) % (rows * n) / (rows * n)
                    cells.append(f"<div class='c' style='left:{c * 100 / n:.3f}%;top:{r_ * 100 / rows:.3f}%;"
                                 f"width:{100 / n + .2:.3f}%;height:{100 / rows + .2:.3f}%;--k:{k:.3f}'></div>")
            css = (f".c{{position:absolute;background:{color2};animation:px {d}s steps(1) both;"
                   f"animation-delay:calc(var(--k) * {d * 0.4:.3f}s)}}"
                   f"@keyframes px{{0%{{opacity:0}}1%{{opacity:1}}{55}%{{opacity:1}}100%{{opacity:0}}}}")
        else:
            for c in range(n):
                k = c / n
                pos = (f"left:{c * 100 / n:.3f}%;top:0;bottom:0;width:{100 / n + .2:.3f}%" if kind == "bars"
                       else f"top:{c * 100 / n:.3f}%;left:0;right:0;height:{100 / n + .2:.3f}%")
                cells.append(f"<div class='c' style='{pos};--k:{k:.3f}'></div>")
            ax = "scaleY" if kind == "bars" else "scaleY"
            origin = "bottom" if kind == "bars" else "top"
            css = (f".c{{position:absolute;background:{color2};transform-origin:{origin};"
                   f"animation:bl {d}s cubic-bezier(.7,0,.3,1) both;animation-delay:calc(var(--k) * {d * 0.08:.3f}s)}}"
                   f"@keyframes bl{{0%,100%{{transform:{ax}(0)}}42%,58%{{transform:{ax}(1)}}}}")
        body = "".join(cells)
    elif kind == "diagonal":
        body = "<div class='g'></div>"
        css = (f".g{{position:absolute;left:-60%;top:-60%;width:220%;height:220%;background:{color2};"
               f"transform:rotate(-30deg) translateX(-100%);animation:dg {d}s cubic-bezier(.7,0,.3,1) both}}"
               "@keyframes dg{0%{transform:rotate(-30deg) translateX(-100%)}45%,55%{transform:rotate(-30deg) translateX(0)}"
               "100%{transform:rotate(-30deg) translateX(100%)}}")
    elif kind == "glitch":
        bars = []
        for k in range(14):
            top = (k * 37) % 100
            h = 3 + (k * 11) % 9
            c = ["#ff2a6d", "#05d9e8", "#ffffff", "#111111"][k % 4]
            bars.append(f"<div class='b' style='top:{top}%;height:{h}%;background:{c};--o:{(k * 23) % 60 - 30}%;"
                        f"animation-delay:{(k % 5) * d * 0.04:.3f}s'></div>")
        body = "".join(bars) + "<div class='f'></div>"
        css = (f".b{{position:absolute;left:0;right:0;opacity:0;animation:gb {d}s steps(6) both}}"
               "@keyframes gb{0%{opacity:0}20%{opacity:.9;transform:translateX(var(--o))}50%{opacity:1;transform:none}"
               "80%{opacity:.8;transform:translateX(calc(var(--o) * -1))}100%{opacity:0}}"
               f".f{{{full};background:{color2};animation:gf {d}s steps(1) both}}"
               "@keyframes gf{0%,46%{opacity:0}47%,54%{opacity:1}55%,100%{opacity:0}}")
    elif kind in ("light_leak", "burn"):
        cols = ("#ff9a3c", "#ff4e50", "#ffd86b") if kind == "light_leak" else ("#ff5a00", "#fff1c1", "#7a1a00")
        body = "<div class='l'></div>"
        css = (f".l{{{full};mix-blend-mode:screen;background:radial-gradient(ellipse 60% 80% at 20% 40%,{cols[0]},transparent 70%),"
               f"radial-gradient(ellipse 50% 60% at 80% 60%,{cols[1]},transparent 70%),"
               f"radial-gradient(circle at 55% 30%,{cols[2]},transparent 55%);"
               f"animation:lk {d}s ease-in-out both}}"
               "@keyframes lk{0%{opacity:0;transform:translateX(-30%) scale(1.2)}50%{opacity:1;transform:none}"
               "100%{opacity:0;transform:translateX(30%) scale(1.2)}}")
        if kind == "burn":
            css = css.replace("50%{opacity:1;transform:none}", "45%,55%{opacity:1;transform:scale(1.6)}")
    elif kind == "radial":
        js = (f"const el=document.getElementById('r');window.seek=t=>{{const p=Math.min(Math.max(t/{d},0),1);"
              "let a,from;if(p<.5){a=p*2*360;from=0;}else{a=(1-(p-.5)*2)*360;from=360-a;}"
              f"el.style.background=`conic-gradient(from ${{from}}deg,{color2} 0deg ${{a}}deg,transparent ${{a}}deg)`;}};window.seek(0);")
        body = "<div id='r' style='position:absolute;left:-50%;top:-50%;width:200%;height:200%'></div>"
    elif kind == "word":
        if not text.strip():
            raise EditError("the word wipe needs text")
        body = f"<div class='f'></div><div class='w'>{escape(text.upper())}</div>"
        fs = min(sh * 0.5, sw * 1.6 / max(len(text), 1))
        css = (font_faces("anton") +
               f".f{{{full};background:{color2};animation:wf {d}s steps(1) both}}"
               "@keyframes wf{0%,44%{opacity:0}45%,58%{opacity:1}59%,100%{opacity:0}}"
               f".w{{position:absolute;left:50%;top:50%;font-family:'Anton',Impact,sans-serif;font-size:{fs:.0f}px;"
               f"color:{color};line-height:1;white-space:nowrap;animation:ww {d}s cubic-bezier(.2,.9,.2,1) both}}"
               "@keyframes ww{0%{opacity:0;transform:translate(-50%,-50%) scale(.3)}35%{opacity:1;transform:translate(-50%,-50%) scale(1)}"
               "60%{opacity:1;transform:translate(-50%,-50%) scale(1.15)}100%{opacity:0;transform:translate(-50%,-50%) scale(6)}}")
    return _page(body, css, width, height, js), float(d)


def cut_at(kind: str, duration: float) -> float:
    """Seconds into a wipe where the picture should cut (the moment it is fully covered)."""
    return duration / 2
