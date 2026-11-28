"""Where each rep of a lift starts and ends in a clip, found by a local script.

Michael, on the first cut from his own footage: "you cut half of the bench press out ... the full idea
of the clip needs to be there", and he asked for something that runs as a script so nobody has to
look through frames to find a press. A cut in a lift clip must hold whole reps: leaving the top, the
far point (chest, hole, lockout from the floor), and back to where it began.

How it works, with no model to download and no view of the lift assumed:

1. The clip is read small and grey, about ten frames a second.
2. A set is the same movement repeated, so the picture repeats. The stretch of the clip where the
   picture changes in a steady rhythm is taken as the set (`find_set`). A single rep has no rhythm:
   say roughly where it is with `between`.
3. Inside that stretch, the one pattern of change that explains most of the picture (the first
   principal component) rises and falls once per rep, whatever the camera angle (`trace`).
4. The lift starts and ends at rest (bar locked out, or on the floor for a deadlift), so the first
   turning point is the far point of rep one. Each rep runs from leaving rest to being back at rest
   (`find_reps`).

Needs numpy (`uv sync --extra reframe` or `--extra people`). The times are a measurement, not a
judgement: `sheet` saves the frames at each rep's start, far point and end so they can be checked at
a glance.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .edl import EditError, EditList
from .media import info, read_frames, run

PER_SECOND = 10.0
WIDTH = 48
CHUNK = 20.0
FOLDER = Path(".stylebrain") / "reps"


@dataclass(frozen=True)
class Rep:
    start: float          # leaves rest
    turn: float           # the far point: chest, the hole, or lockout for a deadlift
    end: float            # back at rest
    depth: float = 1.0    # how far it travelled next to the biggest rep in the set (1 is the biggest)

    @property
    def seconds(self) -> float:
        return round(self.end - self.start, 3)


# ---------------------------------------------------------------- pure signal work

def _smooth(x, n: int):
    import numpy as np
    if n <= 1 or len(x) < n:
        return np.asarray(x, float)
    pad = n // 2
    padded = np.concatenate([np.full(pad, x[0]), x, np.full(pad, x[-1])])
    return np.convolve(padded, np.ones(n) / n, mode="valid")[: len(x)]


def turning_points(values, threshold: float) -> list[tuple[int, str]]:
    """Places where the line turns round by at least `threshold`: (index, "low" or "high"), in order.

    Where the line starts is not a turning point, and neither is where it ends: a low only counts once
    the line has come back up from it.
    """
    out: list[tuple[int, str]] = []
    hi = lo = 0
    going = ""
    for i, v in enumerate(values):
        if not going:
            hi = i if v > values[hi] else hi
            lo = i if v < values[lo] else lo
            if values[hi] - v >= threshold:
                going, lo = "down", i
            elif v - values[lo] >= threshold:
                going, hi = "up", i
        elif going == "down":
            if v < values[lo]:
                lo = i
            elif v - values[lo] >= threshold:
                out.append((lo, "low"))
                going, hi = "up", i
        else:
            if v > values[hi]:
                hi = i
            elif values[hi] - v >= threshold:
                out.append((hi, "high"))
                going, lo = "down", i
    return out


def find_reps(times, values, per_second: float = PER_SECOND, shortest: float = 0.7, longest: float = 15.0,
              pad: float = 0.15) -> list[Rep]:
    """Reps in a trace that sits at one level at rest and swings away once per rep.

    Which way is "away" is read from the trace: the lift begins at rest, so the first turning point
    is the far point of the first rep.
    """
    import numpy as np

    t = np.asarray(times, float)
    v = _smooth(np.asarray(values, float), max(1, round(per_second * 0.3)))
    if len(v) < 5:
        return []
    lo, hi = np.percentile(v, 3), np.percentile(v, 97)
    if hi - lo < 1e-9:
        return []
    v = (v - lo) / (hi - lo)
    points = turning_points(v, 0.35)
    if points and points[0][1] == "high":      # rest is the low side: turn it over so rest is high
        v = 1.0 - v
        points = turning_points(v, 0.35)
    lows = [i for i, kind in points if kind == "low"]
    if not lows:
        return []
    reps: list[Rep] = []
    for n, low in enumerate(lows):
        before = lows[n - 1] if n else 0
        after = lows[n + 1] if n + 1 < len(lows) else len(v) - 1
        top_before = before + int(np.argmax(v[before: low + 1]))
        top_after = low + int(np.argmax(v[low: after + 1]))
        travel_in, travel_out = v[top_before] - v[low], v[top_after] - v[low]
        if travel_out < 0.35 or travel_in < 0.35:
            continue                   # it never came back up (or never started at rest): not a whole rep
        leave = top_before
        for i in range(low, top_before - 1, -1):          # last moment it was still at rest
            if v[i] >= v[top_before] - 0.12 * travel_in:
                leave = i
                break
        back = top_after
        for i in range(low, top_after + 1):               # first moment it is back at rest
            if v[i] >= v[top_after] - 0.12 * travel_out:
                back = i
                break
        a, b = max(float(t[leave]) - pad, float(t[0])), min(float(t[back]) + pad, float(t[-1]))
        if shortest <= b - a <= longest:
            reps.append(Rep(round(a, 2), round(float(t[low]), 2), round(b, 2), round(float(min(travel_in, travel_out)), 3)))
    if reps:
        deepest = max(r.depth for r in reps)
        reps = [Rep(r.start, r.turn, r.end, round(r.depth / deepest, 2)) for r in reps]
    return reps


def rhythm(values, per_second: float, shortest: float = 1.0, longest: float = 7.0) -> tuple[float, float]:
    """How strongly a trace repeats, 0 to 1, and the length of one repeat in seconds."""
    import numpy as np

    v = np.asarray(values, float)
    v = v - v.mean()
    power = float((v * v).sum())
    if power < 1e-12:
        return 0.0, 0.0
    best, period = 0.0, 0.0
    for lag in range(max(1, round(shortest * per_second)), min(len(v) - 2, round(longest * per_second)) + 1):
        r = float((v[:-lag] * v[lag:]).sum()) / power
        if r > best:
            best, period = r, lag / per_second
    return round(best, 3), period


def _first_component(frames):
    """The one pattern of change that explains most of these frames, as a value per frame, and its share."""
    import numpy as np

    y = frames - frames.mean(axis=0)
    u, s, _ = np.linalg.svd(y, full_matrices=False)
    total = float((s * s).sum())
    if total < 1e-9:
        return np.zeros(len(frames)), 0.0
    return u[:, 0] * s[0], float(s[0] * s[0]) / total


def find_set(times, frames, per_second: float = PER_SECOND, window: float = 10.0, step: float = 2.0,
             need: float = 0.45) -> tuple[float, float] | None:
    """The stretch of the clip where the picture changes in a steady rhythm, with a little room either side."""
    import numpy as np

    n, w, s = len(frames), round(window * per_second), max(1, round(step * per_second))
    if n < w:
        w = n
    hits = []
    for a in range(0, max(1, n - w + 1), s):
        trace, share = _first_component(frames[a: a + w])
        strength, _ = rhythm(_smooth(trace, 3), per_second)
        if strength >= need and share >= 0.2:
            hits.append((a, a + w, strength))
    if not hits:
        return None
    # The longest run of windows that touch each other is the set; a stray repeat elsewhere is not.
    runs, run_ = [], [hits[0]]
    for h in hits[1:]:
        if h[0] <= run_[-1][1]:
            run_.append(h)
        else:
            runs.append(run_)
            run_ = [h]
    runs.append(run_)
    best = max(runs, key=lambda r: (r[-1][1] - r[0][0]) * float(np.mean([h[2] for h in r])))
    a, b = best[0][0], min(best[-1][1], n) - 1
    return float(times[a]), float(times[b])


# ---------------------------------------------------------------- reading the clip

def load(video: str, start: float = 0.0, end: float | None = None, per_second: float = PER_SECOND,
         width: int = WIDTH):
    """The clip read small and grey: (times, frames as one row each). Needs numpy."""
    import numpy as np

    end = info(video).duration if end is None else end
    if end - start < 1.0:
        raise EditError("that is under a second: too short to hold a rep")
    rows, a = [], start
    while a < end - 1e-6:
        b = min(a + CHUNK, end)
        try:
            f = read_frames(video, a, b, fps=per_second, width=width)
        except EditError:
            break
        grey = f.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)
        rows.append(grey.reshape(len(grey), -1))
        a = b
    if not rows:
        raise EditError(f"could not read frames from {video}")
    frames = np.concatenate(rows)
    return start + np.arange(len(frames)) / per_second, frames


def trace(times, frames, a: float, b: float, per_second: float = PER_SECOND):
    """The rep trace between two times, with a second of room either side: (times, values)."""
    import numpy as np

    keep = (times >= a - 1.0) & (times <= b + 1.0)
    t, f = times[keep], frames[keep]
    values, _ = _first_component(f)
    return t, _smooth(np.asarray(values), max(1, round(per_second * 0.2)))


def measure(video: str, between: tuple[float, float] | None = None, per_second: float = PER_SECOND) -> dict:
    """Find the set and its reps in a clip. `between` says roughly where a single or a short set is."""
    if between:
        a, b = between
        if b <= a:
            raise EditError("--between needs a start before its end")
        times, frames = load(video, max(a - 1.5, 0.0), b + 1.5, per_second)
        span, how = (a, b), "the stretch you gave"
    else:
        times, frames = load(video, per_second=per_second)
        span, how = find_set(times, frames, per_second), "found by its rhythm"
        if span is None:
            return {"video": str(video), "set": None, "reps": [], "how": "no steady rhythm found",
                    "note": "No repeated movement was found. A single rep has no rhythm: give roughly where "
                            "it is with --between START END."}
    t, v = trace(times, frames, span[0], span[1], per_second)
    reps = find_reps(t, v, per_second)
    out = {"video": str(video), "how": how, "reps": [asdict(r) for r in reps],
           "set": [reps[0].start, reps[-1].end] if reps else None, "looked": [round(span[0], 2), round(span[1], 2)]}
    if not reps:
        out["note"] = ("A stretch was found but no whole rep in it. Try --between START END around the set, "
                       "with a second of stillness before and after.")
    elif reps and min(r.depth for r in reps) < 0.6:
        out["note"] = "One rep travels much less than the others: check it on the sheet (a half rep, or a walk-in)."
    return out


# ---------------------------------------------------------------- saved results and the edit

def path_for(video: str, base: str | Path = ".") -> Path:
    return Path(base) / FOLDER / (Path(video).name + ".json")


def save(result: dict, base: str | Path = ".") -> Path:
    p = path_for(result["video"], base)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, indent=2))
    return p


def saved(video: str, base: str | Path = ".") -> list[Rep] | None:
    """The reps measured for a clip, or None when it has not been measured."""
    p = path_for(video, base)
    if not p.exists():
        return None
    return [Rep(**r) for r in json.loads(p.read_text()).get("reps", [])]


def whole(reps: list[Rep], a: float, b: float) -> tuple[float, float]:
    """Stretch a time range so it holds every rep it touches from start to end."""
    for r in reps:
        if r.start < b and r.end > a:
            a, b = min(a, r.start), max(b, r.end)
    return round(a, 2), round(b, 2)


def broken(reps: list[Rep], a: float, b: float, slack: float = 0.08) -> list[tuple[int, Rep, str]]:
    """Reps a time range cuts into: (number, rep, what is missing)."""
    out = []
    for n, r in enumerate(reps, 1):
        if r.end <= a + slack or r.start >= b - slack:
            continue
        lost = []
        if r.start < a - slack:
            lost.append("the way down" if a <= r.turn else "the way down and the press")
        if r.end > b + slack:
            lost.append("the way back up" if b >= r.turn else "everything after it starts")
        if lost:
            out.append((n, r, " and ".join(lost)))
    return out


def check(edit: EditList, base: str | Path = ".") -> tuple[list[str], list[str]]:
    """Every piece of the edit against the reps measured in its clip: (problems, clips never measured)."""
    problems, unmeasured = [], []
    at = 0
    for n, seg in enumerate(edit.segments, 1):
        reps = saved(seg.source, base)
        a, b = seg.src_in / edit.fps, seg.src_out / edit.fps
        where = f"piece {n} at {at / edit.fps:.2f}s ({Path(seg.source).name} {a:.2f}-{b:.2f}s)"
        if reps is None:
            if seg.source not in unmeasured:
                unmeasured.append(seg.source)
        else:
            for number, r, lost in broken(reps, a, b):
                wa, wb = whole(reps, a, b)
                problems.append(f"{where} cuts rep {number} ({r.start:.2f}-{r.end:.2f}s) and loses {lost}; "
                                f"whole reps need {wa:.2f}-{wb:.2f}s")
        at += seg.src_out - seg.src_in
    return problems, unmeasured


def sheet(video: str, reps: list[Rep], out: str | Path, width: int = 200) -> Path:
    """One row per rep: the frame at its start, its far point and its end, with the time on each."""
    if not reps:
        raise EditError("there are no reps to show")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    moments = [t for r in reps for t in (r.start, r.turn, r.end)]
    for label in (True, False):
        cmd, parts = ["ffmpeg", "-v", "error", "-y"], []
        for i, t in enumerate(moments):
            cmd += ["-ss", f"{t:.3f}", "-i", str(video)]
            text = (f",drawtext=text='{t:.2f}s':fontcolor=white:fontsize=18:box=1:boxcolor=black@0.6:x=4:y=4"
                    if label else "")
            parts.append(f"[{i}:v]trim=end_frame=1,scale={width}:-2,setsar=1{text}[f{i}]")
        grid = "".join(f"[f{i}]" for i in range(len(moments)))
        layout = "|".join(f"{'+'.join(['w0'] * (i % 3)) or '0'}_{'+'.join(['h0'] * (i // 3)) or '0'}"
                          for i in range(len(moments)))
        graph = ";".join(parts) + f";{grid}xstack=inputs={len(moments)}:layout={layout}[o]"
        try:
            run(cmd + ["-filter_complex", graph, "-map", "[o]", "-frames:v", "1", str(out)])
            return out
        except EditError:
            if not label:
                raise
    return out


def text(result: dict) -> str:
    reps = [Rep(**r) for r in result["reps"]]
    if not reps:
        return result.get("note", "no reps found")
    a, b = result["set"]
    lines = [f"{len(reps)} rep{'s' if len(reps) != 1 else ''} between {a:.2f}s and {b:.2f}s ({result['how']})"]
    for n, r in enumerate(reps, 1):
        lines.append(f"  rep {n}: {r.start:6.2f}s to {r.end:6.2f}s  ({r.seconds:.1f}s, far point at {r.turn:.2f}s"
                     + (f", travels {round(r.depth * 100)}% of the biggest" if r.depth < 0.8 else "") + ")")
    if result.get("note"):
        lines.append("  note: " + result["note"])
    return "\n".join(lines)
