"""Measure how a video is edited and keep it as a style profile.

A profile is numbers a person can read: how often it cuts, how the opening is
paced, how fast the speech is, how the picture is graded and how loud it is.
Profiles are saved in `library/styles/` and used two ways: as a target when
editing, and as the yardstick when reviewing a cut (`review.py`).
"""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

from .edl import EditError
from .media import has_audio, info, read_frames, run
from .transcript import Word

HOOK_SECONDS = 15.0


def root(base: str | Path = ".") -> Path:
    return Path(base) / "library" / "styles"


# ---------------------------------------------------------------- measuring

def cut_times(video: str, threshold: float = 0.3, min_gap: float = 0.2) -> list[float]:
    """Times (seconds) where the picture cuts to a new shot."""
    err = run(["ffmpeg", "-v", "info", "-nostats", "-i", str(video), "-an",
               "-vf", f"scale=320:-2,select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
              text=True).stderr
    cuts: list[float] = []
    for m in re.finditer(r"pts_time:([0-9.]+)", err):
        t = float(m.group(1))
        if t > min_gap and (not cuts or t - cuts[-1] >= min_gap):
            cuts.append(round(t, 3))
    return cuts


def shot_lengths(cuts: list[float], duration: float) -> list[float]:
    edges = [0.0, *[c for c in cuts if c < duration], duration]
    return [round(b - a, 3) for a, b in zip(edges, edges[1:]) if b > a]


def _pct(values: list[float], p: float) -> float:
    s = sorted(values)
    if not s:
        return 0.0
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def pacing(cuts: list[float], duration: float) -> dict:
    shots = shot_lengths(cuts, duration)
    hook_end = min(HOOK_SECONDS, duration)
    hook = shot_lengths([c for c in cuts if c < hook_end], hook_end)
    quarters = []
    for q in range(4):
        a, b = duration * q / 4, duration * (q + 1) / 4
        n = sum(1 for c in cuts if a <= c < b)
        quarters.append(round(n / ((b - a) / 60), 1) if b > a else 0.0)
    return {
        "shots": len(shots),
        "cuts_per_minute": round(len(cuts) / (duration / 60), 1) if duration else 0.0,
        "median_shot": round(statistics.median(shots), 2),
        "mean_shot": round(statistics.fmean(shots), 2),
        "short_shot": round(_pct(shots, 0.1), 2),
        "long_shot": round(_pct(shots, 0.9), 2),
        "longest_shot": round(max(shots), 2),
        "cuts_per_minute_by_quarter": quarters,
        "hook": {
            "seconds": round(hook_end, 2),
            "cuts": len(hook) - 1,
            "median_shot": round(statistics.median(hook), 2),
            "first_cut": cuts[0] if cuts else None,
        },
    }


def speech(words: list[Word], duration: float | None = None) -> dict:
    """Speaking pace and pauses from word timings."""
    if not words:
        raise EditError("the transcript has no words")
    span = (duration or words[-1].end) or 1.0
    gaps = [round(b.start - a.end, 3) for a, b in zip(words, words[1:]) if b.start > a.end]
    talking = sum(w.end - w.start for w in words) + sum(g for g in gaps if g < 0.3)
    long_pauses = [g for g in gaps if g >= 0.5]
    hook = " ".join(w.text for w in words if w.start < HOOK_SECONDS)
    return {
        "words_per_minute": round(len(words) / (span / 60)),
        "words_per_minute_while_talking": round(len(words) / (talking / 60)) if talking else 0,
        "median_gap": round(statistics.median(gaps), 2) if gaps else 0.0,
        "long_gap": round(_pct(gaps, 0.9), 2),
        "longest_pause": round(max(gaps), 2) if gaps else 0.0,
        "pauses_over_half_second_per_minute": round(len(long_pauses) / (span / 60), 1),
        "first_word_at": round(words[0].start, 2),
        "hook_text": hook,
    }


def colour(video: str, samples: int = 24) -> dict:
    """How the picture is graded, from frames spread across the video. Needs numpy."""
    import numpy as np

    i = info(video)
    d = i.duration
    frames = read_frames(video, d * 0.02, d * 0.98, fps=max(samples / (d * 0.96), 0.01), width=160)
    px = frames.reshape(-1, 3).astype(np.float32) / 255.0
    luma = px @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    mx, mn = px.max(axis=1), px.min(axis=1)
    sat = np.where(mx > 0.02, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    lo, mid, hi = luma < 0.25, (luma >= 0.25) & (luma < 0.7), luma >= 0.7

    def tint(mask) -> list[float]:
        if not mask.any():
            return [0.0, 0.0, 0.0]
        m = px[mask].mean(axis=0)
        return [round(float(v), 3) for v in (m - m.mean())]

    mean = px.mean(axis=0)
    return {
        "brightness": round(float(luma.mean()), 3),
        "black_point": round(float(np.percentile(luma, 1)), 3),
        "white_point": round(float(np.percentile(luma, 99)), 3),
        "contrast": round(float(np.percentile(luma, 95) - np.percentile(luma, 5)), 3),
        "saturation": round(float(sat.mean()), 3),
        "warmth": round(float(mean[0] - mean[2]), 3),
        "green_magenta": round(float(mean[1] - (mean[0] + mean[2]) / 2), 3),
        "shadow_tint": tint(lo),
        "midtone_tint": tint(mid),
        "highlight_tint": tint(hi),
    }


def audio(video: str) -> dict | None:
    """Loudness and how much of the video is quiet. None when there is no sound."""
    if not has_audio(video):
        return None
    err = run(["ffmpeg", "-v", "info", "-nostats", "-i", str(video), "-vn",
               "-af", "silencedetect=noise=-35dB:d=0.35,ebur128", "-f", "null", "-"], text=True).stderr
    quiet = sum(float(x) for x in re.findall(r"silence_duration: ([0-9.]+)", err))
    summary = err[err.rfind("Summary:"):] if "Summary:" in err else ""
    loud = re.search(r"I:\s+(-?[0-9.]+) LUFS", summary)
    rng = re.search(r"LRA:\s+(-?[0-9.]+) LU", summary)
    d = info(video).duration
    return {
        "loudness_lufs": float(loud.group(1)) if loud else None,
        "loudness_range": float(rng.group(1)) if rng else None,
        "quiet_share": round(min(quiet / d, 1.0), 3) if d else 0.0,
    }


# ----------------------------------------------------------------- profiles

def measure(video: str, words: list[Word] | None = None, threshold: float = 0.3) -> dict:
    """Everything measurable about one video."""
    i = info(video)
    cuts = cut_times(video, threshold)
    out = {
        "source": str(video),
        "frame": {"width": i.width, "height": i.height, "fps": round(i.fps, 3),
                  "shape": "vertical" if i.height > i.width else "square" if i.height == i.width else "wide",
                  "seconds": round(i.duration, 2)},
        "cuts": cuts,
        "pacing": pacing(cuts, i.duration),
        "colour": colour(video),
        "audio": audio(video),
    }
    if words:
        out["speech"] = speech(words, i.duration)
    return out


def _check(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        raise EditError("style names use letters, numbers, - and _ only")
    return name


def save(name: str, profile: dict, about: str = "", base: str | Path = ".") -> Path:
    path = root(base) / f"{_check(name)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"name": name, "about": about, **profile}, indent=2) + "\n")
    return path


def load(name: str, base: str | Path = ".") -> dict:
    path = root(base) / f"{_check(name)}.json"
    if not path.exists():
        known = ", ".join(list_styles(base)) or "none saved yet"
        raise EditError(f"no style named {name!r} ({known})")
    return json.loads(path.read_text())


def list_styles(base: str | Path = ".") -> list[str]:
    return sorted(p.stem for p in root(base).glob("*.json"))


def _words(value: float, steps: list[tuple[float, str]]) -> str:
    for limit, word in steps:
        if value < limit:
            return word
    return steps[-1][1]


def summary(p: dict) -> str:
    """The profile in plain sentences."""
    f, pc, c = p["frame"], p["pacing"], p["colour"]
    lines = [
        f"{f['shape'].capitalize()} {f['width']}x{f['height']} at {f['fps']:g} fps, {f['seconds']:.0f}s long.",
        f"Cuts: {pc['cuts_per_minute']:g} a minute. A typical shot lasts {pc['median_shot']:g}s "
        f"(short ones {pc['short_shot']:g}s, long ones {pc['long_shot']:g}s, longest {pc['longest_shot']:g}s).",
    ]
    h = pc["hook"]
    first = f"first cut at {h['first_cut']:g}s" if h.get("first_cut") is not None else "no cuts at all"
    lines.append(f"Opening {h['seconds']:g}s: {h['cuts']} cuts, typical shot {h['median_shot']:g}s, {first}.")
    q = pc["cuts_per_minute_by_quarter"]
    lines.append("Cuts a minute through the video, by quarter: " + ", ".join(f"{v:g}" for v in q) + ".")
    if s := p.get("speech"):
        parts = [f"Speech: {s['words_per_minute']} words a minute"]
        if "median_gap" in s:
            parts.append(f"typical gap between words {s['median_gap']:g}s")
        if s.get("longest_pause") is not None:
            parts.append(f"longest pause {s['longest_pause']:g}s")
        if "pauses_over_half_second_per_minute" in s:
            parts.append(f"{s['pauses_over_half_second_per_minute']:g} pauses over half a second each minute")
        line = ", ".join(parts) + "."
        if s.get("first_word_at") is not None:
            line += f" First word at {s['first_word_at']:g}s."
        lines.append(line)
        if s.get("hook_text"):
            lines.append(f"Opening words: \"{s['hook_text']}\"")
    bright = _words(c["brightness"], [(0.3, "dark"), (0.45, "medium-dark"), (0.6, "medium"), (2, "bright")])
    contrast = _words(c["contrast"], [(0.45, "low"), (0.7, "medium"), (2, "high")])
    sat = _words(c["saturation"], [(0.15, "muted"), (0.35, "natural"), (2, "vivid")])
    warm = "warm" if c["warmth"] > 0.03 else "cool" if c["warmth"] < -0.03 else "neutral"
    lines.append(f"Picture: {bright}, {contrast} contrast, {sat} colour, {warm} balance. "
                 f"Blacks sit at {c['black_point'] * 100:.0f}%, whites at {c['white_point'] * 100:.0f}%.")
    if a := p.get("audio"):
        if a["loudness_lufs"] is not None:
            lines.append(f"Sound: {a['loudness_lufs']:g} LUFS, quiet for {a['quiet_share'] * 100:.0f}% of the time.")
    if st := p.get("study"):
        from .creators import study_lines
        lines += study_lines(st)
    return "\n".join(lines)
