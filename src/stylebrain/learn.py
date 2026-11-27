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
from datetime import datetime
import re
from pathlib import Path

from .edl import EditError
from .score import first_real_word, score
from .story import average_sentence_words, first_useful_point, longest_shot
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
            "sentence_words": average_sentence_words(words),
            "first_point_at": round(first_useful_point(words, (judge or {}).get("first_point")) or duration, 2),
        })
        for name, test in HOOKS.items():
            out[name] = float(bool(test(text, toks)))
    if cuts is not None:
        out["cuts_per_minute"] = round(len(cuts) / (duration / 60), 1)
        out["first_cut_at"] = round(cuts[0] if cuts else duration, 2)
        out["cuts_in_first_3s"] = sum(1 for c in cuts if c < 3)
        out["longest_shot"] = longest_shot(cuts, duration)[0]
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


def pull(folder: str | Path, base: str | Path = ".") -> int:
    """Copy clip records from a shared folder into the learning set. Returns how many were taken."""
    folder = Path(folder)
    if not folder.is_dir():
        raise EditError(f"cannot find the folder {folder}")
    n = 0
    for p in sorted(folder.glob("*.json")):
        record = json.loads(p.read_text())
        if not isinstance(record, dict) or "id" not in record or not isinstance(record.get("attributes"), dict):
            continue
        dest = root(base) / f"{_check(str(record['id']))}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(record, indent=2) + "\n")
        n += 1
    return n


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
    "follows": "new followers per 1,000 accounts reached (what turns reach into an audience)",
    "reached": "accounts reached on a log scale",
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
        if target == "reached":
            return math.log10(max(float(outcome["reach"]), 1))
        per = {"sends": "shares", "saves": "saves", "likes": "likes", "follows": "follows"}[target]
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
    "posted": ("publish time", "video publish time", "date posted"),
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


def _when(raw: str):
    """A publish time from an export cell, or None."""
    raw = (raw or "").strip()
    for fmt in ("%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%b %d, %Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass
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
    if "id" not in pick or not any(f in pick for f in _NUMBERS if f != "seconds"):
        raise EditError("could not find a link or id column and a results column such as views or likes. Columns in the file: "
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
        if not any(f in outcome for f in _NUMBERS if f != "seconds"):
            continue
        when = _when(row.get(pick.get("posted", ""), ""))
        attrs = {}
        if when:
            outcome["posted"] = when.isoformat(timespec="minutes")
            attrs["age_days"] = max((datetime.now() - when).days, 0)
        add(vid, attrs, outcome, about=(row.get(pick.get("title", "")) or "")[:120], mine=True, base=base)
        done.append(vid)
    if not done:
        raise EditError("no reels or videos found in the file")
    return done


# What a reel is, as opposed to how it is cut. Fixed lists, so tags can be compared and backtested.
TAGS: dict[str, tuple[str, ...]] = {
    "format": ("skit", "how_to", "lift_clip", "talking", "borrowed_sound", "challenge", "vlog", "other"),
    "topic": ("bench", "squat", "deadlift", "meet", "nutrition", "running", "army", "looks_humour", "gym_culture",
              "motivation", "other"),
    "hook": ("question", "claim", "joke_premise", "mystery", "challenge", "none"),
}
TAG_FLAGS = ("series", "teaches", "about_him", "punchline_end", "face_to_camera", "text_on_frame_1", "other_people")
TAG_HELP = {
    "format": "skit (acted joke), how_to (shows a cue, tip or method), lift_clip (a lift with a title or counter), "
              "talking (him to camera: opinion or story), borrowed_sound (someone else's audio with his picture or text), "
              "challenge (a counted or dared attempt), vlog (a day, a prep, a recap)",
    "topic": "what it is about; looks_humour covers looksmaxxing, aura and similar jokes",
    "hook": "how the first two seconds pull: a question, a claim, the premise of a joke, a mystery held back, a challenge, or none",
    "series": "it is marked as part of a run (pt. 4, day 3, a recurring title)",
    "teaches": "a viewer could do something differently after watching",
    "about_him": "it is about who he is (Army, West Point, his numbers) more than about a lift or a joke",
    "punchline_end": "the last line or shot is the laugh or the reveal",
    "face_to_camera": "he talks to the camera",
    "text_on_frame_1": "there is readable text on the first frame",
    "other_people": "someone else is on screen as part of the bit",
}


def tag_attributes(tags: dict) -> dict:
    """Tags as attributes the model can use: one 0/1 column per choice and per flag.

    Tag from the video and the words only. Whoever tags must not have seen the
    clip's results, or anything learned from the tags is leaked.
    """
    unknown = set(tags) - set(TAGS) - set(TAG_FLAGS)
    if unknown:
        raise EditError(f"unknown tag {sorted(unknown)[0]!r}; use {', '.join([*TAGS, *TAG_FLAGS])}")
    out = {}
    for field, choices in TAGS.items():
        if field in tags:
            if tags[field] not in choices:
                raise EditError(f"{field} is one of {', '.join(choices)}")
            out.update({f"tag_{field}_{c}": int(c == tags[field]) for c in choices})
    out.update({f"tag_{flag}": int(bool(tags[flag])) for flag in TAG_FLAGS if flag in tags})
    return out


def unmeasured(clip: dict) -> bool:
    """True when a clip has results but nothing measured from the video or transcript yet."""
    return not (set(clip.get("attributes", {})) - CONTROLS)


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


CONTROLS = {"age_days"}     # things that move results but are not editing choices; held steady, reported apart
LOGGED = {"age_days"}       # long-tailed; used on a log scale


def group_of(clip: dict) -> str:
    """Whose clip it is: the record's `group`, else the name before the first comma of `about`."""
    return str(clip.get("group") or clip.get("about", "").split(",")[0]).strip()


def fit(clips: list[dict], target: str = "reach", alpha: float | None = None, only_mine: bool = False,
        within: bool | None = None) -> dict:
    """Fit the model. Returns what was learned, with how far to trust it.

    within: compare each clip with its own creator's usual, and test on creators
    the model has not seen. Without it a mixed set mostly learns who the creator
    is. Left as None it is used whenever the clips come from two or more creators.
    """
    import numpy as np

    rows = [(c, target_value(c.get("outcome", {}), target)) for c in clips if not only_mine or c.get("mine")]
    rows = [(c, t) for c, t in rows if t is not None and not unmeasured(c)]
    sizes: dict[str, int] = {}
    for c, _ in rows:
        sizes[group_of(c)] = sizes.get(group_of(c), 0) + 1
    big = {g for g, k in sizes.items() if g and k >= 3}
    if within is None:
        within = len(big) >= 2
    dropped = 0
    if within:
        if len(big) < 2:
            raise EditError("comparing within creators needs two or more creators with three or more clips each")
        dropped = sum(group_of(c) not in big for c, _ in rows)
        rows = [(c, t) for c, t in rows if group_of(c) in big]
    if len(rows) < MIN_CLIPS:
        raise EditError(f"{len(rows)} clips have both attributes and a {target!r} result; "
                        f"{MIN_CLIPS} is the least worth fitting, {SOLID_CLIPS} or more for a result to rely on")
    n = len(rows)
    # Use attributes present in at least 80% of clips and that vary; fill the rest with the middle value.
    names = sorted({k for c, _ in rows for k in c["attributes"]} - {"score_total"})
    names = [k for k in names if sum(k in c["attributes"] for c, _ in rows) >= 0.8 * n]
    raw = np.array([[c["attributes"].get(k, np.nan) for k in names] for c, _ in rows], float)
    for j, k in enumerate(names):
        if k in LOGGED:
            raw[:, j] = np.log1p(np.maximum(raw[:, j], 0))
    med = np.nanmedian(raw, axis=0)
    raw = np.where(np.isnan(raw), med, raw)
    y = np.array([t for _, t in rows], float)
    groups = np.array([group_of(c) for c, _ in rows])
    if within:                                     # everything becomes "compared with this creator's usual"
        for g in set(groups):
            m = groups == g
            raw[m] -= raw[m].mean(axis=0)
            y[m] -= y[m].mean()
    keep = raw.std(axis=0) > 1e-9
    names, raw = [k for k, ok in zip(names, keep) if ok], raw[:, keep]
    if not names:
        raise EditError("no attribute varies between these clips")
    folds = [groups == g for g in sorted(set(groups))] if within else [np.arange(n) == i for i in range(n)]

    def standardise(train, test):
        mu, sd = train.mean(axis=0), train.std(axis=0)
        sd = np.where(sd < 1e-9, 1.0, sd)
        return (train - mu) / sd, (test - mu) / sd

    def held_out(a: float, cols=slice(None)):
        preds = np.empty(n)
        for test in folds:
            m = ~test
            Xt, Xv = standardise(raw[m][:, cols], raw[test][:, cols])
            w = _ridge(Xt, y[m] - y[m].mean(), a)
            preds[test] = Xv @ w + y[m].mean()
        return preds

    def r2_of(preds) -> float:
        ss_res, ss_tot = float(((preds - y) ** 2).sum()), float(((y - y.mean()) ** 2).sum())
        return 1 - ss_res / ss_tot if ss_tot else 0.0

    alphas = [alpha] if alpha is not None else [1.0, 3.0, 10.0, 30.0, 100.0, 300.0]
    best = min(alphas, key=lambda a: float(((held_out(a) - y) ** 2).sum()))
    preds = held_out(best)
    r2 = r2_of(preds)
    rank = _corr(_rank(preds), _rank(y))
    # How much of that is the controls alone (a clip's age, say) and not the edit?
    control_cols = [j for j, k in enumerate(names) if k in CONTROLS]
    r2_controls = r2_of(held_out(best, control_cols)) if control_cols else None

    X, _ = standardise(raw, raw)
    w = _ridge(X, y - y.mean(), best)
    # How steady is each sign when the clips (or whole creators) are resampled?
    rng = np.random.default_rng(0)
    signs = np.zeros(len(names))
    rounds = 200
    members = [np.flatnonzero(f) for f in folds]
    for _ in range(rounds):
        if within:
            idx = np.concatenate([members[i] for i in rng.integers(0, len(members), len(members))])
        else:
            idx = rng.integers(0, n, n)
        Xb, _ = standardise(raw[idx], raw[idx])
        signs += np.sign(_ridge(Xb, y[idx] - y[idx].mean(), best)) == np.sign(w)
    effects = sorted(({"attribute": k, "effect": round(float(c), 3), "steady": round(float(s / rounds), 2),
                       "alone": round(_corr(raw[:, j], y), 2), "control": k in CONTROLS}
                      for j, (k, c, s) in enumerate(zip(names, w, signs))), key=lambda e: -abs(e["effect"]))

    gain = r2 - max(r2_controls or 0.0, 0.0)
    trust = ("no better than guessing the average" if r2 <= 0.05 or gain <= 0.02 else
             "a rough read; treat as hints" if n < SOLID_CLIPS or gain < 0.25 else "a usable signal")
    return {"target": target, "clips": n, "attributes": len(names), "alpha": best,
            "within": bool(within), "groups": len(set(groups)) if within else 0, "left_out": dropped,
            "predicts_unseen_r2": round(r2, 2), "predicts_unseen_rank": round(rank, 2),
            "controls_alone_r2": None if r2_controls is None else round(r2_controls, 2), "trust": trust,
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
        if any(v is None for v in col) or np.std(np.array(col, float)) < 1e-9:
            return None                      # a part never judged (the same value on every clip) says nothing
        cors[part] = max(_corr(np.array(col, float), y), 0.0)
    total = sum(cors.values())
    if total <= 0:
        return None
    out = {p: (PARTS[p] + 100 * cors[p] / total) / 2 for p in PARTS}
    scale = 100 / sum(out.values())
    return {p: round(v * scale, 1) for p, v in out.items()}


def report(result: dict, top: int = 10) -> str:
    lines = [f"Learned from {result['clips']} clips, {result['attributes']} attributes, target: {TARGETS[result['target']]}."]
    if result.get("within"):
        lines.append(f"Each clip is compared with its own creator's usual ({result['groups']} creators), and the test "
                     "is on creators the model had not seen."
                     + (f" {result['left_out']} clips from creators with under three clips were left out."
                        if result.get("left_out") else ""))
    lines.append(f"On clips it had not seen: R2 {result['predicts_unseen_r2']:g}, rank agreement "
                 f"{result['predicts_unseen_rank']:g}. Verdict: {result['trust']}.")
    if result.get("controls_alone_r2") is not None:
        lines.append(f"A clip's age alone gets R2 {result['controls_alone_r2']:g}, so the edit adds "
                     f"{result['predicts_unseen_r2'] - max(result['controls_alone_r2'], 0):+.2f}.")
    lines.append("Goes with doing better (+) or worse (-), strongest first:")
    shown = [e for e in result["effects"] if not e.get("control")][:top]
    for e in shown:
        mark = "" if e["steady"] >= 0.9 else "  (unsteady)" if e["steady"] < 0.75 else "  (fairly steady)"
        lines.append(f"  {'+' if e['effect'] > 0 else '-'} {e['attribute']:<22} effect {e['effect']:+.2f}, alone {e['alone']:+.2f}{mark}")
    for e in result["effects"]:
        if e.get("control"):
            lines.append(f"  held steady: {e['attribute']} (effect {e['effect']:+.2f})")
    if result["weights"] and "guessing" in result["trust"]:
        lines.append("No score weights suggested: the model does no better than guessing on these clips.")
    elif result["weights"]:
        lines.append("Suggested virality score weights (now -> suggested):")
        lines += [f"  {p:<14}{PARTS[p]:>4} -> {v:g}" for p, v in result["weights"].items()]
    lines.append("This shows what goes together in these clips, not what causes what.")
    return "\n".join(lines)


def backtest(clips: list[dict], target: str = "reached", first: int | None = None, step: int = 10,
             top: float = 0.2, alpha: float = 30.0, only_mine: bool = True) -> dict:
    """Would what the model learned have worked on the posts that came next?

    Clips are put in the order they were posted. The model is fitted on the
    first `first` of them and used to predict the next `step`; then those are
    added and it predicts the next `step`, and so on. Every prediction is for
    a clip the model had not seen and that was posted later, the way a rule
    would have been used at the time. Returns how well the predictions ranked
    the later clips, how the model's top picks did against posting everything,
    and which single attributes kept their direction on later clips.
    """
    import numpy as np

    rows = [(c, target_value(c.get("outcome", {}), target)) for c in clips if not only_mine or c.get("mine")]
    rows = [(c, t) for c, t in rows if t is not None and not unmeasured(c) and c.get("outcome", {}).get("posted")]
    rows.sort(key=lambda r: r[0]["outcome"]["posted"])
    n = len(rows)
    first = first or max(MIN_CLIPS, int(n * 0.4))
    if n < first + step:
        raise EditError(f"{n} clips have attributes, a {target!r} result and a posting date; a backtest needs "
                        f"at least {first + step} (import an analytics export with a publish time column)")
    names = sorted({k for c, _ in rows for k in c["attributes"]} - {"score_total"} - CONTROLS)
    names = [k for k in names if sum(k in c["attributes"] for c, _ in rows) >= 0.8 * n]
    raw = np.array([[c["attributes"].get(k, np.nan) for k in names] for c, _ in rows], float)
    y = np.array([t for _, t in rows], float)
    preds, single = np.full(n, np.nan), np.full((n, len(names)), np.nan)
    for start in range(first, n, step):
        tr, te = slice(0, start), slice(start, min(start + step, n))
        med = np.nanmedian(raw[tr], axis=0)
        med = np.where(np.isnan(med), 0.0, med)
        A, B = np.where(np.isnan(raw[tr]), med, raw[tr]), np.where(np.isnan(raw[te]), med, raw[te])
        mu, sd = A.mean(axis=0), A.std(axis=0)
        sd = np.where(sd < 1e-9, 1.0, sd)
        A, B = (A - mu) / sd, (B - mu) / sd
        preds[te] = B @ _ridge(A, y[tr] - y[tr].mean(), alpha) + y[tr].mean()
        for j in range(len(names)):               # one attribute at a time: the direction seen so far, applied forward
            single[te, j] = np.sign(_corr(_rank(A[:, j]), _rank(y[tr]))) * B[:, j]
    m = ~np.isnan(preds)
    yt, pt = y[m], preds[m]
    cut = np.quantile(yt, 1 - top)
    k = max(1, int(round(top * len(yt))))
    picks = np.argsort(-pt)[:k]
    rules = sorted(({"attribute": name, "rank": round(_corr(_rank(single[m, j]), _rank(yt)), 2)}
                    for j, name in enumerate(names) if np.std(single[m, j]) > 0), key=lambda r: -r["rank"])
    return {"target": target, "clips": n, "trained_on_first": first, "predicted": int(m.sum()), "step": step,
            "attributes": len(names), "rank": round(_corr(_rank(pt), _rank(yt)), 2),
            "top_share": top, "picks": int(k), "pick_hit_rate": round(float((yt[picks] >= cut).mean()), 2),
            "base_hit_rate": round(float((yt >= cut).mean()), 2),
            "pick_median": round(float(np.median(yt[picks])), 3), "all_median": round(float(np.median(yt)), 3),
            "noise_rank": round(2.0 / math.sqrt(max(int(m.sum()), 1)), 2), "rules": rules}


def backtest_report(b: dict, top: int = 8) -> str:
    logged = b["target"] in ("reached", "views", "reach")
    show = (lambda v: f"{10 ** v:,.0f}") if logged else (lambda v: f"{v:.2f}")
    lines = [f"Backtest on {b['clips']} clips in posting order, target: {TARGETS[b['target']]}.",
             f"Fitted on the first {b['trained_on_first']}, then predicted each next {b['step']} before seeing them "
             f"({b['predicted']} predictions, {b['attributes']} attributes).",
             f"Predictions ranked the later clips with agreement {b['rank']:+.2f} "
             f"(anything inside ±{b['noise_rank']:.2f} is noise at this size).",
             f"The model's top {b['picks']} picks: {b['pick_hit_rate']:.0%} were hits, against {b['base_hit_rate']:.0%} "
             f"for posting everything; their median was {show(b['pick_median'])} against {show(b['all_median'])}.",
             "Single attributes, using only the direction seen up to each point:"]
    for r in b["rules"][:top]:
        lines.append(f"  {r['rank']:+.2f}  {r['attribute']}")
    lines.append(f"With {b['attributes']} attributes tried, the best few will look good by luck. A rule counts once it "
                 "holds on the next export too.")
    return "\n".join(lines)
