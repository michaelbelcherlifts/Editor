"""The arsenal: every effect, caption style, transition, cut and sound pairing the editor
can pull from, as data in `library/arsenal/*.json`.

Each entry has an id, a kind (text, caption, transition, cut, pairing), the story beats it
serves (hook, stakes, setup, turn, payoff, value, list, number, joke, emotion, cta...),
an energy from 1 (quiet) to 5 (loud), the creators whose look it comes from, and the
sounds that go with it (`sfx`: tags with a time relative to the effect's start).
Visual entries name a template and its settings, so they render and place like a saved
effect (`effect-place ID`). Cut and pairing entries are recipes: `how` lists the
commands, with {at} and {end} for the times.

Pick by story first: find the beat, then the energy, then the look.
"""

from __future__ import annotations

import json
from pathlib import Path

from .edl import EditError

ROOT = Path("library/arsenal")
KINDS = ("text", "caption", "transition", "cut", "pairing")
NEEDED = ("id", "kind", "name", "beats", "energy", "about")


def load(root: Path = ROOT) -> list[dict]:
    entries, seen = [], set()
    for path in sorted(Path(root).glob("*.json")):
        for e in json.loads(path.read_text()):
            missing = [k for k in NEEDED if k not in e]
            if missing:
                raise EditError(f"{path.name}: entry {e.get('id', '?')} is missing {', '.join(missing)}")
            if e["id"] in seen:
                raise EditError(f"{path.name}: the id {e['id']!r} is used twice")
            seen.add(e["id"])
            entries.append({**e, "file": path.name})
    return entries


def get(entry_id: str, root: Path = ROOT) -> dict:
    for e in load(root):
        if e["id"] == entry_id:
            return e
    raise EditError(f"nothing in the arsenal called {entry_id!r}; try `stylebrain arsenal --find WORD`")


def search(kind: str | None = None, beat: str | None = None, energy: str | None = None,
           creator: str | None = None, find: str | None = None, root: Path = ROOT) -> list[dict]:
    """Filter the arsenal. energy is one number or a range such as 3-5."""
    lo, hi = 1, 5
    if energy:
        try:
            parts = [int(p) for p in str(energy).split("-")]
        except ValueError:
            raise EditError("energy is a number from 1 to 5, or a range such as 3-5") from None
        lo, hi = parts[0], parts[-1]
    out = []
    for e in load(root):
        if kind and e["kind"] != kind:
            continue
        if beat and beat.lower() not in [b.lower() for b in e["beats"]]:
            continue
        if not lo <= int(e["energy"]) <= hi:
            continue
        if creator and creator.lower() not in [c.lower() for c in e.get("creators", [])]:
            continue
        if find and find.lower() not in json.dumps(e).lower():
            continue
        out.append(e)
    return out


def as_recipe(entry: dict) -> dict:
    """A visual arsenal entry in the saved-effect shape, so effect-render and effect-place take it."""
    if "template" not in entry:
        raise EditError(f"{entry['id']} is a recipe, not a graphic: {' / '.join(entry.get('how', []))}")
    return {"name": entry["id"], "template": entry["template"], "params": entry.get("params", {}),
            "about": entry["about"], "reference": entry.get("source", "")}


def describe(e: dict) -> str:
    sounds = ", ".join(f"{s['tag']} at {s['at']:+g}s" for s in e.get("sfx", [])) or "none"
    lines = [f"{e['id']} ({e['kind']}): {e['name']}", f"  {e['about']}",
             f"  beats: {', '.join(e['beats'])}; energy {e['energy']}/5"
             + (f"; from {', '.join(e['creators'])}" if e.get("creators") else ""),
             f"  sounds: {sounds}"]
    if "template" in e:
        lines.append(f"  template {e['template']} {json.dumps(e.get('params', {}))[:200]}")
        lines.append(f"  place: stylebrain effect-place {e['id']} --at TIME"
                     + (" (centre it on the cut)" if e["kind"] == "transition" else ""))
    for step in e.get("how", []):
        lines.append(f"  how: {step}")
    return "\n".join(lines)


def sound_steps(e: dict, at: float) -> list[str]:
    """The sfx-place commands that pair with an entry placed at `at` seconds."""
    return [f"stylebrain sfx-place {s['tag']} --at {max(at + float(s['at']), 0):.2f}" for s in e.get("sfx", [])]


def sheet(entries: list[dict], out: str | Path, width: int = 540, height: int = 960, columns: int = 5,
          backdrop: str = "0x2a2f36", scratch: str | Path = ".stylebrain/arsenal") -> Path:
    """A contact sheet: each visual entry rendered on a plain backdrop, the frame where it is fullest."""
    from .media import run
    from .templates import build
    from .render import render_html

    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    tiles = []
    for e in entries:
        if "template" not in e:
            continue
        params = {**e.get("params", {})}
        if e["template"] != "html":
            params.update(width=width, height=height)
        html, duration = build(e["template"], params)
        when = duration * (0.3 if e["kind"] == "transition" else 0.62)
        mov = render_html(html, scratch / f"{e['id']}.mov", min(duration, when + 0.05), fps=20,
                          width=width, height=height)
        png = scratch / f"{e['id']}.png"
        label = e["id"].replace(":", " ")
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             f"gradients=s={width}x{height}:c0={backdrop}:c1=0x15181c:x0=0:y0=0:x1={width}:y1={height}:d=1",
             "-sseof", "-0.05", "-i", mov.path, "-filter_complex",
             f"[0:v][1:v]overlay=format=auto,drawbox=x=0:y=ih-40:w=iw:h=40:color=black@0.6:t=fill,"
             f"drawtext=text='{label}':x=12:y=h-31:fontsize=22:fontcolor=white",
             "-frames:v", "1", str(png)])
        tiles.append(png)
    if not tiles:
        raise EditError("no graphics among those entries to put on a sheet")
    while len(tiles) % columns:
        tiles.append(tiles[-1].with_name("_blank.png"))
        if not tiles[-1].exists():
            run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=0x101214:s={width}x{height}",
                 "-frames:v", "1", str(tiles[-1])])
    rows = len(tiles) // columns
    inputs = [x for t in tiles for x in ("-i", str(t))]
    layout = "|".join(f"{c * width}_{r * height}" for r in range(rows) for c in range(columns))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    scale = min(1.0, 3000 / (columns * width))
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex",
         f"xstack=inputs={len(tiles)}:layout={layout},scale=iw*{scale:.3f}:-2", "-frames:v", "1", str(out)])
    return out

