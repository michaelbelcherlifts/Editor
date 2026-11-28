"""Teaching graphics for lifting videos (PRD W8.4).

- lift_diagram: muscle diagram presets for the main lifts and common accessories.
- form_cue: arrows, lines and measured joint angles drawn over a freeze frame.
- tempo_counter: a rep tempo such as 3-1-1-0 counted down phase by phase.
- compare_chart: labelled bars that grow and count, for comparisons.
- checklist: a numbered checklist whose items tick (pass) or cross (fail) one by one.
- meet_lights: the three referee lights of a powerlifting meet, white or red.

The muscles in each lift preset are a coaching summary, not a study. They are
Michael's call: show him the preset before it goes in a final cut.
"""

from __future__ import annotations

import json
import math
from html import escape

from .edl import EditError
from .kinetic import _COUNT_JS, _number
from .pagekit import CAPTION_BAND, _page, _stage, keep_clear_box

P, S = "primary", "secondary"

# lift: (title, [(muscle, role, label or None)])
LIFTS: dict[str, tuple[str, list[tuple[str, str, str | None]]]] = {
    "bench": ("Bench press", [("chest", P, None), ("triceps", P, None), ("shoulders", S, None)]),
    "close_grip_bench": ("Close-grip bench", [("triceps", P, None), ("chest", P, None), ("shoulders", S, None)]),
    "squat": ("Squat", [("quads", P, None), ("glutes", P, None), ("hamstrings", S, None),
                        ("lower back", S, "Lower back (bracing)"), ("abs", S, "Core (bracing)")]),
    "low_bar_squat": ("Low-bar squat", [("glutes", P, None), ("quads", P, None), ("hamstrings", S, None),
                                        ("lower back", S, None)]),
    "deadlift": ("Deadlift", [("glutes", P, None), ("hamstrings", P, None), ("lower back", P, None),
                              ("quads", S, None), ("traps", S, None), ("lats", S, "Lats (bar close)"),
                              ("forearms", S, "Forearms (grip)")]),
    "sumo_deadlift": ("Sumo deadlift", [("quads", P, None), ("glutes", P, None), ("hamstrings", S, None),
                                        ("lower back", S, None), ("forearms", S, "Forearms (grip)")]),
    "rdl": ("Romanian deadlift", [("hamstrings", P, None), ("glutes", P, None), ("lower back", S, None),
                                  ("forearms", S, "Forearms (grip)")]),
    "overhead_press": ("Overhead press", [("shoulders", P, None), ("triceps", P, None), ("traps", S, None),
                                          ("abs", S, "Core (bracing)")]),
    "row": ("Barbell row", [("lats", P, None), ("rear delts", P, None), ("traps", S, "Upper back"),
                            ("biceps", S, None)]),
    "pull_up": ("Pull-up", [("lats", P, None), ("biceps", P, None), ("rear delts", S, None),
                            ("forearms", S, "Forearms (grip)")]),
    "dip": ("Dip", [("chest", P, None), ("triceps", P, None), ("shoulders", S, None)]),
    "hip_thrust": ("Hip thrust", [("glutes", P, None), ("hamstrings", S, None)]),
    "lunge": ("Lunge", [("quads", P, None), ("glutes", P, None), ("hamstrings", S, None)]),
}
_LIFT_ALIASES = {"bench press": "bench", "back squat": "squat", "conventional deadlift": "deadlift",
                 "dl": "deadlift", "ohp": "overhead_press", "press": "overhead_press", "sumo": "sumo_deadlift",
                 "romanian deadlift": "rdl", "pullup": "pull_up", "chin up": "pull_up", "dips": "dip",
                 "cgbp": "close_grip_bench", "bent over row": "row", "lunges": "lunge"}


def lift_key(lift: str) -> str:
    k = lift.strip().lower().replace("-", " ")
    k = _LIFT_ALIASES.get(k, k).replace(" ", "_")
    if k not in LIFTS:
        raise EditError(f"no lift preset {lift!r}; there are: {', '.join(sorted(LIFTS))}")
    return k


def lift_diagram(lift: str, title: str | None = None, only: list[str] | None = None, **settings):
    """Muscle diagram preset for a lift (bench, squat, deadlift, accessories), primaries first.

    only: keep just these muscles from the preset. Other settings go to muscle_diagram.
    """
    from .templates import muscle_diagram

    name, muscles = LIFTS[lift_key(lift)]
    if only:
        keep = {m.lower() for m in only}
        muscles = [m for m in muscles if m[0] in keep]
        if not muscles:
            raise EditError(f"none of {only} are in the {name} preset")
    highlights = [{"muscle": m, "role": r, **({"label": lab} if lab else {})} for m, r, lab in muscles]
    return muscle_diagram(highlights, title=name if title is None else title, **settings)


def _pt(p, sw, sh, what):
    if not (isinstance(p, (list, tuple)) and len(p) == 2 and all(0 <= float(v) <= 1 for v in p)):
        raise EditError(f"{what} is [x, y] as fractions of the frame, between 0 and 1")
    return float(p[0]) * sw, float(p[1]) * sh


def joint_angle(vertex, a, b) -> float:
    """Angle at `vertex` between the lines to a and b, in degrees (points in pixels)."""
    a1 = math.atan2(a[1] - vertex[1], a[0] - vertex[0])
    b1 = math.atan2(b[1] - vertex[1], b[0] - vertex[0])
    d = abs(math.degrees(a1 - b1)) % 360
    return 360 - d if d > 180 else d


def form_cue(arrows: list[dict] | None = None, angles: list[dict] | None = None, lines: list[dict] | None = None,
             duration: float = 3.0, color: str = "#ffe14a", good: str = "#3ddc84", dim: float = 0.25,
             width: int = 1920, height: int = 1080):
    """Arrows, lines and measured joint angles drawn over a freeze frame.

    Points are [x, y] fractions of the frame.
    arrows: {"from", "to", "label"?, "at"?}. lines: {"from", "to", "label"?, "dashed"?, "at"?}
    (a bar path, a vertical). angles: {"vertex", "a", "b", "label"?, "at"?}; the degrees
    are measured from the points. Put the frame itself on the timeline as a freeze.
    """
    arrows, angles, lines = arrows or [], angles or [], lines or []
    if not (arrows or angles or lines):
        raise EditError("form_cue needs at least one arrow, line or angle")
    sw, sh, _ = _stage(width, height)
    svg, labels, at = [], [], 0.35
    hold = duration - 0.3

    def label(x, y, text, t, colour):
        x = min(max(x, 20), sw - 360)
        y = min(max(y, 20), sh - 80)
        labels.append(f"<div class='lb' style='left:{x:.0f}px;top:{y:.0f}px;background:{colour};"
                      f"animation-delay:{t + 0.3:.2f}s,{hold:.2f}s'>{escape(text)}</div>")

    for kind, items in (("line", lines), ("arrow", arrows)):
        for it in items:
            x1, y1 = _pt(it.get("from"), sw, sh, f"{kind} from")
            x2, y2 = _pt(it.get("to"), sw, sh, f"{kind} to")
            t = float(it.get("at", at)); at = t + 0.35
            length = math.hypot(x2 - x1, y2 - y1)
            dash = "stroke-dasharray:22 16;" if it.get("dashed") else f"stroke-dasharray:{length:.0f};"
            anim = (f"animation:draw{'' if not it.get('dashed') else 'd'} .5s ease-out {t:.2f}s both,"
                    f"out .3s ease-in {hold:.2f}s forwards;--len:{length:.0f}")
            head = " marker-end='url(#ah)'" if kind == "arrow" else ""
            svg.append(f"<line x1='{x1:.0f}' y1='{y1:.0f}' x2='{x2:.0f}' y2='{y2:.0f}'{head} "
                       f"style='{dash}{anim}'/>")
            if it.get("label"):
                label((x1 + x2) / 2 + 24, (y1 + y2) / 2 - 30, it["label"], t, color)
    for it in angles:
        v = _pt(it.get("vertex"), sw, sh, "angle vertex")
        a = _pt(it.get("a"), sw, sh, "angle a")
        b = _pt(it.get("b"), sw, sh, "angle b")
        t = float(it.get("at", at)); at = t + 0.5
        deg = joint_angle(v, a, b)
        r = 0.45 * min(math.hypot(a[0] - v[0], a[1] - v[1]), math.hypot(b[0] - v[0], b[1] - v[1]), 260)
        a1 = math.atan2(a[1] - v[1], a[0] - v[0]); b1 = math.atan2(b[1] - v[1], b[0] - v[0])
        sweep = (b1 - a1) % (2 * math.pi)
        flag = 1 if sweep < math.pi else 0
        sx, sy = v[0] + r * math.cos(a1), v[1] + r * math.sin(a1)
        ex, ey = v[0] + r * math.cos(b1), v[1] + r * math.sin(b1)
        arc_len = r * math.radians(deg)
        style = f"animation:out .3s ease-in {hold:.2f}s forwards"
        svg.append(f"<g style='{style}'><line class='arm' x1='{v[0]:.0f}' y1='{v[1]:.0f}' x2='{a[0]:.0f}' y2='{a[1]:.0f}' "
                   f"style='animation-delay:{t:.2f}s'/><line class='arm' x1='{v[0]:.0f}' y1='{v[1]:.0f}' "
                   f"x2='{b[0]:.0f}' y2='{b[1]:.0f}' style='animation-delay:{t:.2f}s'/>"
                   f"<path class='arc' d='M{sx:.1f},{sy:.1f} A{r:.1f},{r:.1f} 0 0 {flag} {ex:.1f},{ey:.1f}' "
                   f"style='stroke-dasharray:{arc_len:.0f};--len:{arc_len:.0f};animation-delay:{t + 0.2:.2f}s'/>"
                   f"<circle cx='{v[0]:.0f}' cy='{v[1]:.0f}' r='12' class='dot' style='animation-delay:{t:.2f}s'/></g>")
        mid = a1 + (sweep if flag else sweep - 2 * math.pi) / 2
        lx, ly = v[0] + (r + 70) * math.cos(mid) - 60, v[1] + (r + 70) * math.sin(mid) - 30
        text = f"{deg:.0f}°" + (f"  {it['label']}" if it.get("label") else "")
        label(lx, ly, text, t + 0.2, good)
    css = (f".dim{{position:absolute;inset:0;background:rgba(0,0,0,{dim});animation:fd .3s ease-out both,"
           f"out .3s ease-in {hold:.2f}s forwards}}"
           f"svg{{position:absolute;inset:0}}line,path{{fill:none;stroke:{color};stroke-width:10;stroke-linecap:round;"
           "filter:drop-shadow(0 3px 6px rgba(0,0,0,.6))}"
           f".arm{{stroke:#fff;stroke-width:7;opacity:0;animation:fd .25s ease-out both}}"
           f".arc{{stroke:{good};stroke-width:9;animation:draw .45s ease-out both}}"
           f".dot{{fill:{good};stroke:#000;stroke-width:3;opacity:0;animation:fd .2s ease-out both}}"
           f"#ah path{{fill:{color};stroke:none}}"
           ".lb{position:absolute;color:#111;font-weight:900;font-size:42px;padding:6px 18px 8px;border-radius:12px;"
           "white-space:nowrap;opacity:0;animation:fd .25s ease-out both,out .3s ease-in forwards;"
           "box-shadow:0 6px 18px rgba(0,0,0,.45)}"
           "@keyframes draw{from{stroke-dashoffset:var(--len)}to{stroke-dashoffset:0}}"
           "@keyframes drawd{from{opacity:0}to{opacity:1}}"
           "@keyframes fd{from{opacity:0}to{opacity:1}}@keyframes out{to{opacity:0}}")
    marker = ("<defs><marker id='ah' viewBox='0 0 10 10' refX='5' refY='5' markerWidth='3.2' markerHeight='3.2' "
              "orient='auto-start-reverse'><path d='M0,0 L10,5 L0,10 Z'/></marker></defs>")
    body = (f"<div class='dim'></div><svg width='{sw:.0f}' height='{sh:.0f}'>{marker}{''.join(svg)}</svg>"
            + "".join(labels))
    return _page(body, css, width, height), float(duration)


_PHASES = ("Lower", "Pause", "Drive", "Top")


def tempo_counter(tempo: str = "3-1-1-0", reps: int = 1, lead: float = 0.5, accent: str = "#ffe14a",
                  x: float = 0.06, y: float = 0.12, width: int = 1920, height: int = 1080):
    """A rep tempo (eccentric-pause-concentric-pause, e.g. 3-1-1-0) counted down phase by phase.

    Phases of 0 seconds are skipped. "X" means explosive and counts as 0.5 s.
    """
    parts = [p.strip().upper() for p in str(tempo).replace(":", "-").split("-")]
    if len(parts) != 4:
        raise EditError("tempo is four numbers, e.g. 3-1-1-0 (lower, pause, drive, top)")
    try:
        secs = [0.5 if p == "X" else float(p) for p in parts]
    except ValueError:
        raise EditError("tempo parts are seconds or X, e.g. 3-1-X-0") from None
    if sum(secs) <= 0 or reps < 1:
        raise EditError("tempo needs some time and at least one rep")
    plan, t = [], lead
    for r in range(reps):
        for name, s in zip(_PHASES, secs):
            if s > 0:
                plan.append([name, round(t, 3), s, r + 1]); t += s
    duration = t + 0.6
    js = (f"const P={json.dumps(plan)},R={reps};const ph=document.getElementById('ph'),n=document.getElementById('n'),"
          "rp=document.getElementById('rp'),ring=document.getElementById('ring');"
          "window.seek=t=>{let cur=null;for(const p of P){if(t>=p[1])cur=p;}"
          "if(!cur){ph.textContent=P[0][0];n.textContent=Math.ceil(P[0][2]);ring.style.strokeDashoffset=0;rp.textContent='';return;}"
          "const el=t-cur[1],left=Math.max(cur[2]-el,0),done=t>=cur[1]+cur[2]&&cur===P[P.length-1];"
          "ph.textContent=done?'Done':cur[0];n.textContent=done?'✓':Math.max(Math.ceil(left-1e-6),1);"
          "ring.style.strokeDashoffset=(done?1:Math.min(el/cur[2],1))*628;"
          "rp.textContent=R>1?`Rep ${cur[3]}/${R}`:'';};window.seek(0);")
    css = (f".tc{{position:absolute;left:{x * 100:.1f}%;top:{y * 100:.1f}%;display:flex;align-items:center;gap:26px;"
           "background:rgba(12,12,14,.84);border-radius:28px;padding:22px 34px 22px 22px;color:#fff;"
           "animation:fd .3s ease-out both}"
           ".dial{position:relative;width:220px;height:220px}"
           ".dial svg{position:absolute;inset:0;transform:rotate(-90deg)}"
           ".dial circle{fill:none;stroke-width:16}"
           f"#ring{{stroke:{accent};stroke-dasharray:628;stroke-linecap:round}}"
           "#n{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:110px;"
           "font-weight:900;font-variant-numeric:tabular-nums}"
           "#ph{font-size:64px;font-weight:900;text-transform:uppercase;letter-spacing:.02em}"
           f".tp{{font-size:34px;font-weight:700;opacity:.7}}#rp{{font-size:34px;font-weight:800;color:{accent}}}"
           "@keyframes fd{from{opacity:0}to{opacity:1}}")
    body = (f"<div class='tc'><div class='dial'><svg viewBox='0 0 220 220'><circle cx='110' cy='110' r='100' "
            f"stroke='rgba(255,255,255,.15)'/><circle id='ring' cx='110' cy='110' r='100'/></svg><div id='n'></div></div>"
            f"<div><div id='ph'></div><div class='tp'>Tempo {escape('-'.join(parts))}</div><div id='rp'></div></div></div>")
    return _page(body, css, width, height, js), duration


def compare_chart(bars: list[dict], title: str = "", unit: str = "", duration: float = 4.5,
                  color: str = "#8b8f98", accent: str = "#ffe14a", highlight: int | None = None,
                  keep_clear: list[float] | None = CAPTION_BAND, width: int = 1920, height: int = 1080):
    """Labelled bars that grow one after another and count up: bars are {"label", "value", "color"?}.

    highlight: index of the bar to draw in the accent colour (the point of the comparison).
    """
    if not bars or any("label" not in b or "value" not in b for b in bars):
        raise EditError("compare_chart needs bars such as {\"label\": \"Me\", \"value\": 516}")
    try:
        top_v = max(float(b["value"]) for b in bars)
    except ValueError:
        raise EditError("compare_chart values are numbers") from None
    if top_v <= 0:
        raise EditError("compare_chart needs at least one value above 0")
    sw, sh, _ = _stage(width, height)
    want = 170 + 150 * len(bars)
    top, h = keep_clear_box(sh, want, keep_clear)
    row_h = (h - (110 if title else 50)) / len(bars)
    rows = []
    for i, b in enumerate(bars):
        at = 0.5 + i * 0.35
        frac = float(b["value"]) / top_v
        c = b.get("color") or (accent if i == highlight else color)
        u = f"<small>{escape(unit)}</small>" if unit else ""
        rows.append(f"<div class='r' style='height:{row_h:.0f}px'><div class='lab'>{escape(str(b['label']))}</div>"
                    f"<div class='track'><div class='bar' style='width:{frac * 100:.1f}%;background:{c};"
                    f"animation-delay:{at:.2f}s'></div><div class='val' style='animation-delay:{at:.2f}s'>"
                    f"{_number(b['value'], at, 0.7)}{u}</div></div></div>")
    hold = duration - 0.4
    fs = max(26, min(46, row_h * 0.42))
    css = (f".card{{position:absolute;left:50%;transform:translateX(-50%);top:{top:.0f}px;height:{h:.0f}px;"
           f"width:{min(sw * 0.88, 1500):.0f}px;box-sizing:border-box;padding:30px 44px;border-radius:32px;"
           "background:rgba(14,15,18,.92);color:#fff;display:flex;flex-direction:column;justify-content:center;"
           f"animation:in .4s ease-out both,out .4s ease-in {hold:.2f}s forwards}}"
           ".ttl{font-size:50px;font-weight:900;margin-bottom:18px}"
           f".r{{display:flex;align-items:center;gap:24px;font-size:{fs:.0f}px;font-weight:800}}"
           ".lab{width:28%;text-align:right;opacity:.9}"
           ".track{flex:1;position:relative;height:62%;display:flex;align-items:center}"
           ".bar{height:100%;border-radius:12px;transform-origin:left;animation:grow .7s cubic-bezier(.2,.9,.2,1) both}"
           ".val{margin-left:18px;font-variant-numeric:tabular-nums;opacity:0;animation:fd .3s ease-out both;white-space:nowrap}"
           ".val small{font-size:.6em;margin-left:4px;opacity:.8}"
           "@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}"
           "@keyframes in{from{opacity:0;transform:translate(-50%,30px)}to{opacity:1;transform:translate(-50%,0)}}"
           "@keyframes out{to{opacity:0}}@keyframes fd{from{opacity:0}to{opacity:1}}")
    ttl = f"<div class='ttl'>{escape(title)}</div>" if title else ""
    return _page(f"<div class='card'>{ttl}{''.join(rows)}</div>", css, width, height, _COUNT_JS), float(duration)


def checklist(items: list, ticks: list[float] | None = None, title: str = "", duration: float | None = None,
              start: float = 0.4, each: float = 1.2, accent: str = "#3ddc84", fail: str = "#ff4d4d",
              keep_clear: list[float] | None = CAPTION_BAND, width: int = 1080, height: int = 1920):
    """A numbered checklist ("pass all five...") whose items appear and tick one by one.

    items: strings, or {"text", "pass"?: true/false}; a failed item gets a red cross.
    ticks: seconds when each item ticks (say it on the voice-over); default every `each` seconds.
    """
    rows = [{"text": i} if isinstance(i, str) else dict(i) for i in (items or [])]
    if not rows or any(not str(r.get("text", "")).strip() for r in rows):
        raise EditError("checklist needs items, such as [\"Feet flat\", {\"text\": \"Pause\", \"pass\": false}]")
    if ticks is None:
        ticks = [start + i * each for i in range(len(rows))]
    ticks = [float(t) for t in ticks]
    if len(ticks) != len(rows) or ticks != sorted(ticks) or ticks[0] < 0:
        raise EditError("checklist ticks must be one rising time per item")
    duration = float(duration or ticks[-1] + 1.6)
    sw, sh, _ = _stage(width, height)
    want = 140 + 120 * len(rows) + (90 if title else 0)
    top, h = keep_clear_box(sh, want, keep_clear)
    out = max(duration - 0.4, ticks[-1] + 0.2)
    li = []
    for n, (r, t) in enumerate(zip(rows, ticks), 1):
        ok = r.get("pass", True) is not False
        mark = "&#10003;" if ok else "&#10007;"
        li.append(f"<div class='it' style='animation-delay:{max(t - 0.25, 0):.3f}s'>"
                  f"<span class='n'>{n}</span><span class='tx'>{escape(str(r['text']))}</span>"
                  f"<span class='mk {'ok' if ok else 'no'}' style='animation-delay:{t:.3f}s'>{mark}</span></div>")
    ttl = f"<div class='ttl'>{escape(title)}</div>" if title else ""
    css = (f".card{{position:absolute;left:50%;top:{top:.0f}px;max-height:{h:.0f}px;width:{min(sw * 0.86, 1400):.0f}px;"
           "transform:translateX(-50%);box-sizing:border-box;padding:40px 46px;border-radius:34px;"
           "background:rgba(14,15,18,.9);color:#fff;box-shadow:0 30px 80px rgba(0,0,0,.45);overflow:hidden;"
           f"animation:in .4s cubic-bezier(.2,1.1,.3,1) both,out .4s ease-in {out:.3f}s forwards}}"
           ".ttl{font-size:54px;font-weight:900;margin-bottom:18px;letter-spacing:-0.01em}"
           ".it{display:flex;align-items:center;gap:26px;font-size:50px;font-weight:800;margin:18px 0;"
           "opacity:0;animation:up .3s ease-out both}"
           ".n{flex:none;width:68px;height:68px;border-radius:50%;background:rgba(255,255,255,.12);"
           "display:flex;align-items:center;justify-content:center;font-size:38px}"
           ".tx{flex:1}"
           ".mk{flex:none;font-size:70px;font-weight:900;opacity:0;animation:pop .35s cubic-bezier(.2,1.6,.3,1) both}"
           f".ok{{color:{accent}}}.no{{color:{fail}}}"
           "@keyframes in{from{opacity:0;transform:translate(-50%,40px)}to{opacity:1;transform:translate(-50%,0)}}"
           "@keyframes out{to{opacity:0}}"
           "@keyframes up{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}"
           "@keyframes pop{from{opacity:0;transform:scale(2.2)}to{opacity:1;transform:none}}")
    return _page(f"<div class='card'>{ttl}{''.join(li)}</div>", css, width, height), duration


_LIGHT = {"white": "#ffffff", "red": "#ff2d2d"}


def meet_lights(lights: list[str] | None = None, at: float = 0.3, stagger: float = 0.25, duration: float = 3.0,
                label: str = "", y: float = 0.14, size: int = 120, width: int = 1080, height: int = 1920):
    """The three referee lights of a powerlifting meet: white (good lift) or red (no lift), lighting in turn.

    Two or three whites is a good lift; the label under them (e.g. "GOOD LIFT") is optional.
    """
    lights = [str(x).lower() for x in (lights or ["white", "white", "white"])]
    if len(lights) != 3 or any(x not in _LIGHT for x in lights):
        raise EditError("meet_lights needs three lights, each white or red")
    out = max(float(duration) - 0.35, at + 3 * stagger)
    dots = "".join(f"<span class='l' style='--c:{_LIGHT[c]};animation-delay:{at + i * stagger:.3f}s'></span>"
                   for i, c in enumerate(lights))
    lab = f"<div class='lb' style='animation-delay:{at + 3 * stagger:.3f}s'>{escape(label)}</div>" if label else ""
    css = (f".w{{position:absolute;left:0;right:0;top:{y * 100:.1f}%;text-align:center;"
           f"animation:fo .3s ease-in {out:.3f}s forwards}}"
           f".row{{display:inline-flex;gap:{size * 0.4:.0f}px;padding:{size * 0.22:.0f}px {size * 0.35:.0f}px;"
           "border-radius:999px;background:rgba(10,10,12,.85);box-shadow:0 20px 50px rgba(0,0,0,.5)}"
           f".l{{width:{size}px;height:{size}px;border-radius:50%;background:#2a2a2e;"
           "animation:on .25s ease-out both}"
           f".lb{{margin-top:22px;font-size:{size * 0.5:.0f}px;font-weight:900;color:#fff;letter-spacing:.08em;"
           "text-shadow:0 6px 20px rgba(0,0,0,.6);opacity:0;animation:up .3s ease-out both}"
           "@keyframes on{to{background:var(--c);box-shadow:0 0 40px var(--c),0 0 90px var(--c)}}"
           "@keyframes up{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}"
           "@keyframes fo{to{opacity:0}}")
    return _page(f"<div class='w'><div class='row'>{dots}</div>{lab}</div>", css, width, height), float(duration)
