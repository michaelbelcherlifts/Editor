"""Learn which attributes of a clip go with it performing well.

Three pieces:

1. `attributes(...)` turns one clip into numbers: hook type, speech pace,
   pauses, cut rate, length, picture, sound, and Claude's judgements.
2. A dataset in `library/clips/`: one JSON file per clip holding its
   attributes and what happened to it (views, subscribers, retention).
3. `fit(...)`: a small ridge regression (numpy only, runs locally) that says
   which attributes go up with performance, checked by leaving each clip out
   in turn and predicting it. It also proposes new weights for the virality
   score from how well each part tracked real results.

What this can and cannot say. It finds what goes together in the clips it is
given; it does not prove cause. With few clips the result is noise, so `fit`
refuses under 12 clips and marks anything under 30 as a rough read.
"""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

from .edl import EditError
from .score import first_real_word, score
from .transcript import Word, _norm

MIN_CLIPS, SOLID_CLIPS = 12, 30

HOOKS = {
    "hook_question": lambda t, ws: "?" in t or ws[:1] in (["want"], ["why"], ["how"], ["what"], ["do"], ["are"], ["is"], ["can"], ["did"], ["have"]),
    "hook_number": lambda t, ws: any(re.fullmatch(r"\d+|one|two|three|four|five|six|seven|ten", w) for w in ws),
    "hook_warning": lambda t, ws: any(w in ("stop", "never", "dont", "don't", "mistake", "mistakes", "wrong", "worst") for w in ws),
    "hook_you": lambda t, ws: any(w in ("you", "your", "youre", "you're") for w in ws),
    "hook_me": lambda t, ws: any(w in ("i", "my", "me", "im", "i'm") for w in ws),
    "hook_superlative": lambda t, ws: any(w in ("best", "fastest", "perfect", "biggest", "only", "secret", "easiest") for w in ws),
}


def root(base: str | Path = ".") -> Path:
    return Path(base) / "library" / "clips"


def hook_line(words: list[Word], seconds: float = 3.0) -> str:
    return " ".join(w.text for w in words if w.start < seconds)


def attributes(words: list[Word], duration: float, cuts: list[float] | None = None, frame: dict | None = None,
               audio: dict | None = None, colour: dict | None = None, judge: dict | None = None) -> dict:
    """One clip as a flat dict of numbers. Anything not measured is left out."""
    out: dict[str, float] = {"seconds": round(duration, 2)}
    if words:
        first = first_real_word(words)
        gaps = [b.start - a.end for a, b in zip(words, words[1:])]
        text = hook_line(words)
        toks = [_norm(w) for w in text.split()]
        out.update({
            "first_word_at": round(first.start if first else duration, 2),
            "words_per_minute": round(len(words) / (duration / 60)),
            "longest_pause": round(max(gaps, default=0.0), 2),
            "pauses_over_300ms": sum(1 for g in gaps if g > 0.3),
            "hook_words": len(toks),
        })
        for name, test in HOOKS.items():
            out[name] = float(bool(test(text, toks)))
    if cuts is not None:
        out["cuts_per_minute"] = round(len(cuts) / (duration / 60), 1)
        out["first_cut_at"] = round(cuts[0] if cuts else duration, 2)
        out["cuts_in_first_3s"] = sum(1 for c in cuts if c < 3)
    if frame:
        out["vertical"] = float(frame["height"] > frame["width"])
    if audio and audio.get("loudness_lufs") is not None:
        out["loudness_lufs"] = audio["loudness_lufs"]
        out["quiet_share"] = audio.get("quiet_share", 0.0)
    for key in ("brightness", "contrast", "saturation", "warmth"):
        if colour and key in colour:
            out[key] = colour[key]
    for key, value in (judge or {}).items():
        out[f"judge_{key}"] = float(value)
    s = score(words, duration, cuts, frame, audio, judge)
    for p in s.parts:
        out["score_" + re.sub(r"[^a-z]+", "_", p.name.lower()).strip("_")] = round(p.points / p.out_of, 3)
    out["score_total"] = s.total
    return out


# ------------------------------------------------------------------ dataset

def _check(clip_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", clip_id):
        raise EditError("clip ids use letters, numbers, - and _ only")
    return clip_id


def add(clip_id: str, attrs: dict, outcome: dict | None = None, about: str = "", mine: bool = False,
        base: str | Path = ".") -> Path:
    """Save or update one clip. `outcome` may hold views, subscribers, retention, swiped_away, shares."""
    path = root(base) / f"{_check(clip_id)}.json"
    old = json.loads(path.read_text()) if path.exists() else {}
    record = {"id": clip_id, "about": about or old.get("about", ""), "mine": mine or old.get("mine", False),
              "attributes": {**old.get("attributes", {}), **attrs},
              "outcome": {**old.get("outcome", {}), **(outcome or {})}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n")
    return path


def load_all(base: str | Path = ".") -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(root(base).glob("*.json"))]


TARGETS = {
    "reach": "views divided by followers or subscribers, on a log scale (how far past the usual audience it went)",
    "views": "views on a log scale",
    "retention": "average percentage viewed",
    "kept": "share of viewers who did not swipe away",
    "sends": "shares per 1,000 accounts reached (Instagram's strongest signal for reaching new people)",
    "saves": "saves per 1,000 accounts reached",
    "likes": "likes per 1,000 accounts reached",
}


def target_value(outcome: dict, target: str) -> float | None:
    if target not in TARGETS:
        raise EditError(f"unknown target {target!r}; choose from {', '.join(TARGETS)}")
    try:
        if target == "reach":
            return math.log10(max(outcome["views"], 1) / max(outcome["subscribers"], 1))
        if target == "views":
            return math.log10(max(outcome["views"], 1))
        if target == "retention":
            return float(outcome["retention"])
        if target == "kept":
            return 100.0 - float(outcome["swiped_away"])
        per = {"sends": "shares", "saves": "saves", "likes": "likes"}[target]
        reached = outcome.get("reach") or outcome["views"]
        return 1000.0 * float(outcome[per]) / max(float(reached), 1.0)
    except (KeyError, TypeError, ValueError):
        return None


_COLUMNS = {
    "id": ("permalink", "content", "video id", "post id", "video"),
    "title": ("video title", "description", "title", "post text"),
    "views": ("views", "plays", "impressions"),
    "reach": ("reach", "accounts reached"),
    "retention": ("average percentage viewed",),
    "swiped_away": ("swiped away",),
    "shares": ("shares", "sends"),
    "saves": ("saves",),
    "likes": ("likes",),
    "comments": ("comments",),
    "follows": ("follows", "subscribers"),
    "seconds": ("duration (sec)", "duration"),
    "type": ("post type",),
}
_NUMBERS = ("views", "reach", "retention", "swiped_away", "shares", "saves", "likes", "comments", "follows", "seconds")


def _clip_id(raw: str) -> str | None:
    """A video id from a cell: an Instagram permalink's shortcode, or a bare id."""
    raw = raw.strip()
    m = re.search(r"instagram\.com/(?:[^/]+/)?(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)", raw)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{6,}", raw) and raw.lower() != "total":
        return raw
    return None


def import_analytics(csv_path: str | Path, subscribers: int | None = None, base: str | Path = ".",
                     reels_only: bool = True) -> list[str]:
    """Read a results export into the dataset. Returns the clip ids.

    Works with a Meta Business Suite content export for Instagram (Insights,
    Content, Export data) and a YouTube Studio content export. Columns are
    matched by name, loosely, since both change their wording from time to
    time. Rows are matched to clips by Instagram shortcode or video id; clips
    not yet in the dataset are created with results only, ready for
    attributes to be added. `subscribers` is the follower or subscriber count.
    """
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        text = f.read()
    text = text[text.find("\n") + 1:] if text.lower().startswith("sep=") else text
    rows = list(csv.DictReader(text.splitlines()))
    if not rows:
        raise EditError("the analytics file has no rows")
    heads = {h.lower().strip(): h for h in rows[0] if h}
    pick = {}
    for field, names in _COLUMNS.items():
        for name in names:
            match = next((orig for low, orig in heads.items() if low == name or low.startswith(name + " (")), None)
            if match:
                pick[field] = match
                break
    if "id" not in pick or "views" not in pick:
        raise EditError("could not find a link or id column and a views column. Columns in the file: "
                        + ", ".join(heads.values()))
    done = []
    for row in rows:
        vid = _clip_id(row.get(pick["id"]) or "")
        if not vid:
            continue
        kind = (row.get(pick.get("type", "")) or "").lower()
        if reels_only and kind and "reel" not in kind and "video" not in kind and "short" not in kind:
            continue
        outcome = {}
        for field in _NUMBERS:
            raw = row.get(pick.get(field, ""), "")
            try:
                outcome[field] = float(str(raw).replace(",", "").replace("%", ""))
            except ValueError:
                pass
        if subscribers:
            outcome["subscribers"] = subscribers
        add(vid, {}, outcome, about=(row.get(pick.get("title", "")) or "")[:120], mine=True, base=base)
        done.append(vid)
    if not done:
        raise EditError("no reels or videos found in the file")
    return done


# -------------------------------------------------------------------- model

def _rank(v):
    import numpy as np
    order = np.argsort(v, kind="stable")
    ranks = np.empty(len(v))
    ranks[order] = np.arange(len(v))
    return ranks


def _corr(a, b) -> float:
    import numpy as np
    if np.std(a) == 0 or np.std(b) == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _ridge(X, y, alpha: float):
    import numpy as np
    return np.linalg.solve(X.T @ X + alpha * np.eye(X.shape[1]), X.T @ y)


def fit(clips: list[dict], target: str = "reach", alpha: float | None = None, only_mine: bool = False) -> dict:
    """Fit the model. Returns what was learned, with how far to trust it."""
    import numpy as np

    rows = [(c, target_value(c.get("outcome", {}), target)) for c in clips if not only_mine or c.get("mine")]
    rows = [(c, t) for c, t in rows if t is not None and c.get("attributes")]
    if len(rows) < MIN_CLIPS:
        raise EditError(f"{len(rows)} clips have both attributes and a {target!r} result; "
                        f"{MIN_CLIPS} is the least worth fitting, {SOLID_CLIPS} or more for a result to rely on")
    n = len(rows)
    # Use attributes present in at least 80% of clips and that vary; fill the rest with the middle value.
    names = sorted({k for c, _ in rows for k in c["attributes"]} - {"score_total"})
    names = [k for k in names if sum(k in c["attributes"] for c, _ in rows) >= 0.8 * n]
    raw = np.array([[c["attributes"].get(k, np.nan) for k in names] for c, _ in rows], float)
    med = np.nanmedian(raw, axis=0)
    raw = np.where(np.isnan(raw), med, raw)
    keep = raw.std(axis=0) > 1e-9
    names, raw = [k for k, ok in zip(names, keep) if ok], raw[:, keep]
    if not names:
        raise EditError("no attribute varies between these clips")
    y = np.array([t for _, t in rows], float)

    def standardise(train, test):
        mu, sd = train.mean(axis=0), train.std(axis=0)
        sd = np.where(sd < 1e-9, 1.0, sd)
        return (train - mu) / sd, (test - mu) / sd

    def loo(a: float):
        preds = np.empty(n)
        for i in range(n):
            m = np.arange(n) != i
            Xt, Xv = standardise(raw[m], raw[i:i + 1])
            w = _ridge(Xt, y[m] - y[m].mean(), a)
            preds[i] = (Xv @ w)[0] + y[m].mean()
        return preds

    alphas = [alpha] if alpha is not None else [1.0, 3.0, 10.0, 30.0, 100.0]
    best = min(alphas, key=lambda a: float(((loo(a) - y) ** 2).sum()))
    preds = loo(best)
    ss_res, ss_tot = float(((preds - y) ** 2).sum()), float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    rank = _corr(_rank(preds), _rank(y))

    X, _ = standardise(raw, raw)
    w = _ridge(X, y - y.mean(), best)
    # How steady is each sign when the clips are resampled?
    rng = np.random.default_rng(0)
    signs = np.zeros(len(names))
    rounds = 200
    for _ in range(rounds):
        idx = rng.integers(0, n, n)
        Xb, _ = standardise(raw[idx], raw[idx])
        signs += np.sign(_ridge(Xb, y[idx] - y[idx].mean(), best)) == np.sign(w)
    effects = sorted(({"attribute": k, "effect": round(float(c), 3), "steady": round(float(s / rounds), 2),
                       "alone": round(_corr(raw[:, j], y), 2)}
                      for j, (k, c, s) in enumerate(zip(names, w, signs))), key=lambda e: -abs(e["effect"]))

    trust = ("no better than guessing the average" if r2 <= 0.05 else
             "a rough read; treat as hints" if n < SOLID_CLIPS or r2 < 0.25 else "a usable signal")
    return {"target": target, "clips": n, "attributes": len(names), "alpha": best,
            "predicts_unseen_r2": round(r2, 2), "predicts_unseen_rank": round(rank, 2), "trust": trust,
            "effects": effects, "weights": propose_weights(rows, y)}


PARTS = {"hook": 25, "pacing": 20, "payoff": 15, "value_emotion": 15, "shareability": 10, "trend_fit": 10, "craft": 5}


def propose_weights(rows, y) -> dict | None:
    """New weights for the virality score, from how well each part tracked results.

    Each part's weight moves halfway from its current value toward its share
    of the (positive) correlations, so one batch of clips cannot swing it wildly.
    """
    import numpy as np
    cors = {}
    for part in PARTS:
        col = [c["attributes"].get(f"score_{part}") for c, _ in rows]
        if any(v is None for v in col):
            return None
        cors[part] = max(_corr(np.array(col, float), y), 0.0)
    total = sum(cors.values())
    if total <= 0:
        return None
    out = {p: (PARTS[p] + 100 * cors[p] / total) / 2 for p in PARTS}
    scale = 100 / sum(out.values())
    return {p: round(v * scale, 1) for p, v in out.items()}


def report(result: dict, top: int = 10) -> str:
    lines = [f"Learned from {result['clips']} clips, {result['attributes']} attributes, target: {TARGETS[result['target']]}.",
             f"On clips it had not seen: R2 {result['predicts_unseen_r2']:g}, rank agreement "
             f"{result['predicts_unseen_rank']:g}. Verdict: {result['trust']}.",
             "Goes with doing better (+) or worse (-), strongest first:"]
    for e in result["effects"][:top]:
        mark = "" if e["steady"] >= 0.9 else "  (unsteady)" if e["steady"] < 0.75 else "  (fairly steady)"
        lines.append(f"  {'+' if e['effect'] > 0 else '-'} {e['attribute']:<22} effect {e['effect']:+.2f}, alone {e['alone']:+.2f}{mark}")
    if result["weights"]:
        lines.append("Suggested virality score weights (now -> suggested):")
        lines += [f"  {p:<14}{PARTS[p]:>4} -> {v:g}" for p, v in result["weights"].items()]
    lines.append("This shows what goes together in these clips, not what causes what.")
    return "\n".join(lines)
