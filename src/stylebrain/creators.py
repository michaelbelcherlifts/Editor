"""Creator style profiles built from the creator study (`data/creator-study/`).

The study measured many clips per creator in a browser (cuts, on-screen text,
zooms, picture, speech, hook words). This module folds one creator's clips into
a style profile that `style-show`, `review` and `look-from-style` can use, and
says how many clips each number rests on.

Each number in the profile is the median across that creator's clips, so one
odd video does not move it. The `study` block keeps the spread and the sample
size, and names the creator's best and worst clips by views.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from .style import pacing, save

# Below this many clips a profile is still written but marked as thin.
MIN_CLIPS = 8


def load_records(folder: str | Path) -> list[dict]:
    """Every record file in a study folder (`records/*.json` or the folder itself)."""
    folder = Path(folder)
    sub = folder / "records"
    files = sorted((sub if sub.is_dir() else folder).glob("*.json"))
    return [json.loads(p.read_text()) for p in files]


def _med(values) -> float | None:
    vals = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return round(statistics.median(vals), 3) if vals else None


def _share(values) -> float | None:
    vals = [v for v in values if isinstance(v, (int, float))]
    return round(sum(1 for v in vals if v) / len(vals), 2) if vals else None


def _iqr(values) -> list[float] | None:
    vals = sorted(v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool))
    if len(vals) < 4:
        return None
    q = statistics.quantiles(vals, n=4)
    return [round(q[0], 3), round(q[2], 3)]


def _clip_pacing(rec: dict) -> dict:
    a = rec["attributes"]
    seconds = min(a.get("seconds") or 0, a.get("scanned_seconds") or a.get("seconds") or 0)
    cuts = [c for c in rec.get("cuts") or [] if c < seconds]
    return pacing(cuts, seconds or 1.0)


def profile(records: list[dict], name: str) -> dict:
    """One style profile from one creator's study records."""
    if not records:
        raise ValueError(f"no study records for {name!r}")
    shorts = [r for r in records if r.get("format") == "short"]
    use = shorts if len(shorts) >= max(3, len(records) // 2) else records
    fmt = "short" if use is shorts else "long-form opening"
    A = [r["attributes"] for r in use]
    P = [_clip_pacing(r) for r in use]

    def col(key):
        return [a.get(key) for a in A]

    vertical = _share(col("vertical"))
    seconds = _med(col("seconds")) if fmt == "short" else _med(col("scanned_seconds"))
    widths = [r["meta"].get("w") for r in use if r.get("meta", {}).get("w")]
    heights = [r["meta"].get("h") for r in use if r.get("meta", {}).get("h")]
    frame = {"shape": "vertical" if (vertical or 0) >= 0.5 else "wide",
             "width": int(_med(widths) or 0), "height": int(_med(heights) or 0),
             "fps": 30, "seconds": seconds or 0.0}

    pace = {
        "shots": int(_med(p["shots"] for p in P)),
        "cuts_per_minute": _med(p["cuts_per_minute"] for p in P),
        "median_shot": _med(p["median_shot"] for p in P),
        "mean_shot": _med(p["mean_shot"] for p in P),
        "short_shot": _med(p["short_shot"] for p in P),
        "long_shot": _med(p["long_shot"] for p in P),
        "longest_shot": _med(p["longest_shot"] for p in P),
        "cuts_per_minute_by_quarter": [_med(p["cuts_per_minute_by_quarter"][q] for p in P) for q in range(4)],
        "hook": {
            "seconds": _med(p["hook"]["seconds"] for p in P),
            "cuts": int(round(_med(p["hook"]["cuts"] for p in P))),
            "median_shot": _med(p["hook"]["median_shot"] for p in P),
            "first_cut": _med(p["hook"]["first_cut"] for p in P),
        },
    }

    colour = {k: _med(col(k)) for k in ("brightness", "contrast", "saturation", "warmth", "green_magenta",
                                         "black_point", "white_point")}
    colour["shadow_rgb"] = [int(_med(col(f"shadow_{c}")) or 0) for c in "rgb"]
    colour["highlight_rgb"] = [int(_med(col(f"highlight_{c}")) or 0) for c in "rgb"]

    by_views = sorted((r for r in use if r["meta"].get("views")), key=lambda r: -r["meta"]["views"])
    talking = [a for a in A if a.get("has_transcript") and a.get("words_per_minute")]
    speech = None
    if len(talking) >= max(3, len(A) // 3):
        hooks = [r.get("hook") for r in by_views if r.get("hook")]
        speech = {
            "words_per_minute": int(_med(a["words_per_minute"] for a in talking)),
            "words_per_minute_while_talking": int(_med(a.get("words_per_minute_while_talking") for a in talking) or 0),
            "longest_pause": _med(a.get("longest_pause") for a in talking),
            "first_word_at": _med(a.get("first_word_at") for a in talking),
            "hook_text": hooks[0] if hooks else "",
            "clips": len(talking),
        }

    def clip(r):
        return {"id": r["meta"]["id"], "title": r["meta"].get("title"), "views": r["meta"]["views"]}

    views = [r["meta"]["views"] for r in by_views]
    study = {
        "clips": len(use),
        "format": fmt,
        "thin": len(use) < MIN_CLIPS,
        "subscribers": next((r.get("subscribers") for r in use if r.get("subscribers")), None),
        "views_median": _med(views),
        "views_range": [min(views), max(views)] if views else None,
        "cuts_per_minute_iqr": _iqr(p["cuts_per_minute"] for p in P),
        "cuts_in_first_3s": _med(col("cuts_in_first_3s")),
        "text_share": _med(col("text_share")),
        "text_changes_per_10s": _med(col("text_changes_per_10s")),
        "captions_share": _share(1 if (a.get("text_changes_per_10s") or 0) >= 8 and (a.get("text_share") or 0) >= 0.4
                                 else 0 for a in A),
        "text_on_frame_1_share": _share(col("text_on_frame_1")),
        "text_position": _med(col("text_position")),
        "zoom_events_per_minute": _med(col("zoom_events_per_minute")),
        "letterbox_share": _med(col("letterbox_share")),
        "talking_share": _share(1 if a.get("has_transcript") and (a.get("speech_share") or 0) > 0.5 else 0 for a in A),
        "hook_types": {k: _share(col(f"hook_{k}")) for k in ("question", "number", "you", "me", "money", "warning")},
        "top": [clip(r) for r in by_views[:3]],
        "bottom": [clip(r) for r in by_views[-3:]] if len(by_views) > 3 else [],
    }
    out = {"source": "data/creator-study", "frame": frame, "cuts": [], "pacing": pace, "colour": colour,
           "audio": None, "study": study}
    if speech:
        out["speech"] = speech
    return out


def build(folder: str | Path, base: str | Path = ".", names: dict[str, str] | None = None) -> list[tuple[str, int]]:
    """Write one style per creator found in the study. Returns (name, clips) pairs."""
    groups: dict[str, list[dict]] = {}
    for r in load_records(folder):
        groups.setdefault(r["creator"], []).append(r)
    done = []
    for slug, recs in sorted(groups.items()):
        p = profile(recs, slug)
        label = (names or {}).get(slug, slug)
        n = p["study"]["clips"]
        save(slug, p, about=f"{label}: medians over {n} measured {p['study']['format']} clips", base=base)
        done.append((slug, n))
    return done


def study_lines(s: dict) -> list[str]:
    """Plain sentences for the `study` block of a profile."""
    n = s["clips"]
    lines = [f"Measured from {n} {s['format']} clips" + (" (thin: treat as a sketch)." if s.get("thin") else ".")]
    if s.get("views_median"):
        lo, hi = s["views_range"]
        lines.append(f"Views: median {s['views_median']:,.0f}, from {lo:,} to {hi:,}.")
    if s.get("cuts_per_minute_iqr"):
        a, b = s["cuts_per_minute_iqr"]
        lines.append(f"Half of the clips cut between {a:g} and {b:g} times a minute.")
    lines.append(f"On-screen text: on screen {(s.get('text_share') or 0) * 100:.0f}% of the time, "
                 f"word-by-word captions in {(s.get('captions_share') or 0) * 100:.0f}% of clips, "
                 f"text on the first frame in {(s.get('text_on_frame_1_share') or 0) * 100:.0f}% (n={n}).")
    hooks = {k: v for k, v in (s.get("hook_types") or {}).items() if v}
    if hooks:
        lines.append("Opening words: " + ", ".join(f"{k} {v * 100:.0f}%" for k, v in
                                                   sorted(hooks.items(), key=lambda kv: -kv[1])) + f" of clips (n={n}).")
    for label, key in (("Best", "top"), ("Worst", "bottom")):
        if s.get(key):
            lines.append(f"{label} by views: " + "; ".join(f"\"{c['title']}\" {c['views']:,}" for c in s[key]) + ".")
    return lines
