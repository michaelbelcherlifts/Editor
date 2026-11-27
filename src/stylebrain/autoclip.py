"""Auto-clipping: cut a long recording into ranked, scored vertical reel candidates.

Three steps, each a command, so Claude (or several Claude agents at once) can
do the reading in the middle:

1. `find`: read the transcript and propose moments of 15 to 60 seconds that
   start on a whole sentence that does not lean on what came before, hold a
   question and its answer, and end on a finished sentence. Each gets a rough
   rank from the words alone. Moments never overlap and repeats of the same
   topic are dropped.
2. Judging (not code): read each candidate's lines and answer the virality
   score's questions (story, promise, payoff, value, share, trend, needs
   context, ...), choose the strongest line to open cold on, and write a
   short text hook. Saved as `judgements.json`.
3. `cut`: for each candidate build an edit (cold open, the moment, pauses
   tightened), frame it 9:16 on the subject, place captions and the text hook,
   render it, measure it and score it on the full rubric. Then rank, and
   write a review sheet with the score by part, the one fix that would help
   most, every cut made, and a preview.

Nothing is posted. Story comes before the look: the rough rank only decides
what is worth judging; the order on the sheet comes from the full score.
"""

from __future__ import annotations

import html
import itertools
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .edl import EditError, EditList, Overlay, Segment
from .story import (
    FILLERS,
    QUESTION_CUES,
    SLOW_OPENERS,
    Sentence,
    _overlap,
    classify_hook,
    proven_examples,
    sentences,
)
from .transcript import Word, _norm, find_silences

MIN_SECONDS = 15.0
MAX_SECONDS = 60.0
IDEAL = (20.0, 45.0)

# A first word that leans on something said before: the viewer will not know what it points at.
LEANS_BACK = {"and", "but", "so", "because", "then", "also", "which", "or", "plus", "anyway", "again", "too",
              "it", "it's", "its", "that", "that's", "these", "those", "they", "they're", "them", "he", "he's",
              "she", "she's", "him", "her", "there", "there's", "yeah", "yes", "no", "otherwise", "anyways",
              "meanwhile", "still", "besides", "instead"}
SOFT_STARTS = {"um", "uh", "like", "okay", "ok", "alright", "right", "well", "oh"}

HOOK_WORDS = {"never", "always", "biggest", "worst", "best", "mistake", "mistakes", "secret", "truth", "nobody",
              "everyone", "stop", "why", "how", "what", "wrong", "actually", "insane", "crazy", "hardest", "easiest",
              "most", "only", "first", "last", "real", "honest", "honestly", "myth", "lie", "lied", "failed", "fail",
              "pr", "record", "max", "heaviest", "strongest", "dangerous", "should", "shouldn't", "don't", "can't",
              "if", "you", "your", "tried", "test", "happens", "happened", "results", "result", "difference"}
PAYOFF_CUES = ("turns out", "the answer", "the result", "so that's", "that's why", "which means", "the lesson",
               "the reason", "the difference", "the point", "bottom line", "at the end of the day", "the key",
               "and it worked", "the verdict", "the takeaway", "here's the thing", "in the end", "finally")

FIXES = {
    "Hook": "Open on the strongest line (cold open) and put a sharper text hook on the first frame.",
    "Pacing": "Tighten what is left: shorter pauses, and a punch-in or cut every 2 to 4 seconds.",
    "Payoff": "End on the answer: cut whatever comes after it, or move the payoff line to the end.",
    "Value/emotion": "Keep the line where the lesson or the feeling lands and cut set-up before it.",
    "Shareability": "Lead with the most arguable or surprising claim in the clip.",
    "Trend fit": "Pair it with a format or sound that is rising now.",
    "Craft": "Check the captions, the 9:16 frame and the loudness.",
}

SCORE_KEYS = {"story", "promise", "payoff", "value", "share", "trend", "first_point", "needs_context",
              "undelivered", "mid_sentence"}
CUT_KEYS = {"cold_open", "start", "end", "hook_text", "title", "skip", "drop"}


@dataclass
class Candidate:
    id: str
    start: float           # source seconds
    end: float
    rough: float           # 0 to 100, from the words alone; only decides what is worth judging
    reasons: list[str] = field(default_factory=list)
    lines: list[dict] = field(default_factory=list)   # [{"start", "end", "text"}] in source seconds

    @property
    def seconds(self) -> float:
        return round(self.end - self.start, 2)

    @property
    def text(self) -> str:
        return " ".join(line["text"] for line in self.lines)

    def to_dict(self) -> dict:
        return {**asdict(self), "seconds": self.seconds}

    @classmethod
    def from_dict(cls, d: dict) -> Candidate:
        return cls(d["id"], d["start"], d["end"], d["rough"], list(d.get("reasons", [])), list(d.get("lines", [])))


# ------------------------------------------------------------------ finding

def _first_token(s: Sentence) -> str:
    for tok in s.text.split():
        t = _norm(tok)
        if t:
            return t
    return ""


def _real_words(s: Sentence) -> list[str]:
    return [t for t in (_norm(x) for x in s.text.split()) if t and t not in FILLERS]


def _is_question(s: Sentence) -> bool:
    low = " " + s.text.lower() + " "
    return s.text.rstrip().endswith("?") or any(c in low for c in QUESTION_CUES if c != "?")


def _hook_strength(s: Sentence) -> tuple[float, str]:
    """0 to 1: how much the first line makes you want the rest."""
    low = s.text.lower()
    if any(o in low for o in SLOW_OPENERS):
        return 0.0, "opens on a greeting or set-up"
    real = _real_words(s)
    if len(real) < 3:
        return 0.15, "first line says almost nothing"
    pts, why = 0.25, []
    if s.text.rstrip().endswith("?"):
        pts += 0.3
        why.append("opens on a question")
    hits = {t for t in real if t in HOOK_WORDS}
    if hits:
        pts += min(0.3, 0.1 * len(hits))
        why.append("hook words: " + ", ".join(sorted(hits)[:4]))
    kinds = classify_hook(s.text)
    if kinds:
        pts += 0.15
        why.append(f"a {kinds[0]} hook")
    if re.search(r"\d", s.text):
        pts += 0.15
        why.append("a number up front")
    if s.words > 22:
        pts -= 0.2
        why.append("long first sentence")
    return max(0.0, min(1.0, pts)), "; ".join(why) or "plain first line"


def _rough(group: list[Sentence], after_gap: float) -> tuple[float, list[str]]:
    """0 to 100 from the words alone. Only decides which moments are worth a full judgement."""
    first, last = group[0], group[-1]
    seconds = last.end - first.start
    reasons = []
    total = 0.0

    # Stands alone (20)
    tok = _first_token(first)
    if tok in LEANS_BACK:
        stand = 0.2
        reasons.append(f"starts on \"{tok}\", which leans on what came before")
    elif tok in SOFT_STARTS:
        stand = 0.6
        reasons.append(f"starts on a filler (\"{tok}\")")
    else:
        stand = 1.0
    total += 20 * stand

    # Hook (20)
    hook, why = _hook_strength(first)
    total += 20 * hook
    reasons.append(f"hook: {why}")

    # A real question and its answer inside the clip (15), and a payoff line late on (10)
    early = [k for k, s in enumerate(group)
             if _is_question(s) and len(_real_words(s)) >= 4 and s.start - first.start <= 0.5 * seconds]
    if early and len(group) - early[0] >= 3:
        total += 15
        reasons.append(f"asks at {group[early[0]].start - first.start:.0f}s and keeps going to an answer")
    elif early:
        total += 6
    late = [s for s in group[len(group) // 2:] if any(c in s.text.lower() for c in PAYOFF_CUES)]
    if late:
        total += 10 if late[-1] is group[-1] else 7 if late[-1] in group[-2:] else 5
        reasons.append(f"a payoff line late on: \"{late[-1].text[:50]}\"")

    # Holds together (15): whole sentences, not banter fragments
    whole = sum(1 for s in group if len(_real_words(s)) >= 5) / len(group)
    total += 15 * whole
    if whole < 0.5:
        reasons.append("mostly short fragments (banter)")

    # Talk density (10): steady talking, no dead air
    spoken = sum(s.end - s.start for s in group)
    gaps = [b.start - a.end for a, b in itertools.pairwise(group)]
    worst = max(gaps, default=0.0)
    total += 10 * min(1.0, spoken / seconds / 0.8) * (1.0 if worst < 2.0 else 0.6 if worst < 4.0 else 0.3)
    if worst >= 2.0:
        reasons.append(f"a {worst:.0f}s gap with no talking")

    # Ends cleanly (5) and length (5)
    ends = last.text.rstrip().endswith((".", "!", "?")) or after_gap >= 0.6
    total += 5 if ends else 1
    if not ends:
        reasons.append("ends mid-sentence")
    lo, hi = IDEAL
    total += 5 if lo <= seconds <= hi else 2
    return round(total, 1), reasons


LONGEST_LINE = 22  # words; a line longer than this in an unpunctuated transcript is split at its longest pause


def _punctuated(words: list[Word]) -> bool:
    ends = sum(1 for w in words if w.text.rstrip("\"')").endswith((".", "?", "!")))
    return bool(words) and ends / len(words) >= 0.02


def _split_long(ws: list[Word]) -> list[list[Word]]:
    if len(ws) <= LONGEST_LINE:
        return [ws]
    lo, hi = len(ws) // 4, len(ws) - len(ws) // 4      # never leave a stub of a few words
    k = max(range(lo, hi), key=lambda i: ws[i].start - ws[i - 1].end)
    return _split_long(ws[:k]) + _split_long(ws[k:])


def spoken_lines(words: list[Word]) -> list[Sentence]:
    """Sentences, or for a transcript with no punctuation (some YouTube captions), lines split at
    short pauses and kept under LONGEST_LINE words, so moments can still start and end cleanly."""
    if _punctuated(words):
        return sentences(words)
    out = []
    for s in sentences(words, gap=0.4):
        ws = [w for w in words if s.start <= w.start <= s.end][: s.words]
        for part in _split_long(ws):
            out.append(Sentence(" ".join(w.text for w in part), part[0].start, part[-1].end, len(part)))
    return out


def find(words: list[Word], count: int = 8, min_seconds: float = MIN_SECONDS, max_seconds: float = MAX_SECONDS,
         skip_before: float = 0.0, same_topic: float = 0.55) -> list[Candidate]:
    """Propose up to `count` moments, best rough rank first, none overlapping.

    `skip_before` leaves out the opening of the recording (an intro). Moments whose words
    overlap a better one's by `same_topic` or more are dropped as repeats.
    """
    if min_seconds <= 0 or max_seconds <= min_seconds:
        raise EditError("the shortest clip must be above 0 and below the longest")
    ss = [s for s in spoken_lines(words) if s.start >= skip_before]
    if not ss:
        raise EditError("no speech found to cut clips from")
    options: list[tuple[float, int, int, list[str]]] = []
    for i in range(len(ss)):
        best = None
        for j in range(i, len(ss)):
            seconds = ss[j].end - ss[i].start
            if seconds > max_seconds:
                break
            if seconds < min_seconds:
                continue
            after = ss[j + 1].start - ss[j].end if j + 1 < len(ss) else 9.0
            rough, reasons = _rough(ss[i:j + 1], after)
            if best is None or rough > best[0]:    # a tie goes to the shorter, tighter one
                best = (rough, i, j, reasons)
        if best:
            options.append(best)
    options.sort(key=lambda o: (-o[0], ss[o[1]].start))
    picked: list[tuple[float, int, int, list[str]]] = []
    for opt in options:
        _, i, j = opt[:3]
        a, b = ss[i].start, ss[j].end
        if any(a < ss[pj].end and ss[pi].start < b for _, pi, pj, _ in picked):
            continue
        text = " ".join(s.text for s in ss[i:j + 1])
        if any(_overlap(text, " ".join(s.text for s in ss[pi:pj + 1])) >= same_topic for _, pi, pj, _ in picked):
            continue
        picked.append(opt)
        if len(picked) >= count:
            break
    out = []
    for n, (rough, i, j, reasons) in enumerate(picked, 1):
        lines = [{"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text} for s in ss[i:j + 1]]
        out.append(Candidate(f"c{n:02d}", round(ss[i].start, 3), round(ss[j].end, 3), rough, reasons, lines))
    return out


# ------------------------------------------------------------------ cutting

def _subtract(spans: list[tuple[float, float]], holes: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out = []
    for a, b in spans:
        pieces = [(a, b)]
        for h0, h1 in holes:
            nxt = []
            for p0, p1 in pieces:
                if h1 <= p0 or h0 >= p1:
                    nxt.append((p0, p1))
                    continue
                if h0 > p0:
                    nxt.append((p0, h0))
                if h1 < p1:
                    nxt.append((h1, p1))
            pieces = nxt
        out += [(p0, p1) for p0, p1 in pieces if p1 - p0 > 0.04]
    return out


def _said(words: list[Word], a: float, b: float, limit: int = 70) -> str:
    text = " ".join(w.text for w in words if a <= w.start < b)
    return text[:limit] + ("..." if len(text) > limit else "")


def plan_cut(cand: Candidate, words: list[Word], judge: dict | None = None, min_gap: float = 0.5,
             pad: float = 0.12, lead: float = 0.1, tail: float = 0.25) -> tuple[list[tuple[float, float]], list[str]]:
    """The source spans to play, in order, and a line for every cut made.

    judge may move the edges (`start`, `end`) and name a line to open cold on
    (`cold_open`: [start, end] in source seconds). That line plays first and is taken
    out of the body, so it is not heard twice.
    """
    judge = judge or {}
    a = float(judge.get("start", cand.start))
    b = float(judge.get("end", cand.end))
    if b - a < 3:
        raise EditError(f"{cand.id}: start and end leave under 3 seconds")
    a, b = max(0.0, a - lead), b + tail
    log = [f"kept source {a:.2f}s to {b:.2f}s of the recording"]
    inside = [w for w in words if a <= w.start < b]
    cold = judge.get("cold_open")
    body = [(a, b)]
    head: list[tuple[float, float]] = []
    if cold:
        c0, c1 = float(cold[0]), float(cold[1])
        if not (c1 > c0 and c1 - c0 <= 12):
            raise EditError(f"{cand.id}: the cold open must be a line of 12 seconds or less")
        c0, c1 = max(0.0, c0 - 0.05), c1 + 0.15
        head = [(c0, c1)]
        log.append(f"cold open: moved source {c0:.2f}s to {c1:.2f}s to the front: \"{_said(words, c0, c1)}\"")
        if a < c1 and c0 < b:
            body = _subtract(body, head)
        inside_cold = [w for w in words if c0 <= w.start < c1]
    else:
        inside_cold = []
    holes = []
    for group, spans in ((inside_cold, head), (inside, body)):
        for s0, s1 in spans:
            ws = [w for w in group if s0 <= w.start < s1]
            for lo, hi in find_silences([Word(w.text, w.start - s0, w.end - s0) for w in ws], min_gap, s1 - s0):
                lo2 = lo + pad if lo > 0 else lo
                hi2 = hi - pad if hi < s1 - s0 else hi
                if hi2 - lo2 > 0.04:
                    holes.append((s0 + lo2, s0 + hi2))
    for h0, h1 in sorted(holes):
        log.append(f"pause cut: source {h0:.2f}s to {h1:.2f}s ({h1 - h0:.1f}s)")
    spans = _subtract(head, holes) + _subtract(body, holes)
    if not spans:
        raise EditError(f"{cand.id}: nothing left to play")
    return spans, log


def build_edit(source: str, fps: float, spans: list[tuple[float, float]], total_frames: int | None = None) -> EditList:
    segs = []
    for a, b in spans:
        i, o = round(a * fps), round(b * fps)
        if total_frames is not None:
            o = min(o, total_frames)
        if o > i:
            segs.append(Segment(source, i, o))
    if not segs:
        raise EditError("nothing to play")
    return EditList(fps=fps, segments=tuple(segs), fill=True)


def timeline_words(edit: EditList, words: list[Word]) -> list[Word]:
    """Words heard in the cut, with times on the cut. A word in a cold open and the body is heard once."""
    out = []
    for start, seg in edit.pieces():
        a, b = seg.src_in / edit.fps, seg.src_out / edit.fps
        for w in words:
            if a <= w.start < b:
                t = start / edit.fps + (w.start - a)
                out.append(Word(w.text, round(t, 3), round(t + min(w.end, b) - w.start, 3)))
    return sorted(out, key=lambda w: w.start)


@dataclass
class Made:
    candidate: Candidate
    judge: dict
    score: dict | None = None
    file: str = ""
    seconds: float = 0.0
    cuts: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    skipped: str = ""

    @property
    def total(self) -> int:
        return self.score["total"] if self.score else -1

    def to_dict(self) -> dict:
        return {"id": self.candidate.id, "candidate": self.candidate.to_dict(), "judge": self.judge,
                "score": self.score, "file": self.file, "seconds": self.seconds, "cuts": self.cuts,
                "notes": self.notes, "skipped": self.skipped}


def make(cand: Candidate, source: str, words: list[Word], out_dir: str | Path, judge: dict | None = None,
         width: int = 1080, height: int = 1920, render: bool = True, captions: bool = True,
         reframe: bool = True, hook_seconds: float | None = None, fps: float | None = None,
         total_frames: int | None = None, steps=None, punch: bool = False) -> Made:
    """Cut, frame, caption, render and score one candidate.

    `steps` replaces the heavy parts in tests: a dict with any of "reframe", "captions",
    "hook", "export", "measure".
    """
    from . import score as sc

    judge = dict(judge or {})
    unknown = set(judge) - SCORE_KEYS - CUT_KEYS
    if unknown:
        raise EditError(f"{cand.id}: unknown judgement {', '.join(sorted(unknown))}")
    made = Made(cand, judge)
    if judge.get("skip") or judge.get("drop"):
        made.skipped = str(judge.get("skip") or judge.get("drop"))
        return made
    steps = steps or {}
    if fps is None or total_frames is None:
        from .media import probe
        fps, total_frames = probe(source)
    spans, made.cuts = plan_cut(cand, words, judge)
    edit = build_edit(str(source), fps, spans, total_frames)
    heard = timeline_words(edit, words)
    made.seconds = round(edit.duration / fps, 2)

    if reframe:
        if "reframe" in steps:
            edit, lines = steps["reframe"](edit, width, height)
        else:
            from .reframe import plan
            edit, lines = plan(edit, width, height)
        made.notes += [f"framing {line.strip()}" for line in lines]
    if punch:
        edit, lines = punch_ins(edit, heard)
        made.cuts += lines
    if captions and heard:
        if "captions" in steps:
            edit = steps["captions"](edit, heard, width, height)
        else:
            from .autopilot import place_captions
            edit = place_captions(edit, heard, width, height, breaks=_joins(edit, jumps_only=True))
    hook = (judge.get("hook_text") or "").strip()
    if hook:
        secs = min(hook_seconds or made.seconds, made.seconds)
        if "hook" in steps:
            path = steps["hook"](hook, secs, fps, width, height)
        else:
            from .effects import render_template
            path = render_template("title_bar", {"text": hook, "duration": secs, "y": 0.1}, None, fps, width, height,
                                   f"hook-{cand.id}").path
        edit = edit.add_overlay(Overlay("text hook", str(Path(path).resolve()), 0, round(secs * fps), 3))

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{cand.id}.edit.json").write_text(json.dumps(edit.to_dict(), indent=2) + "\n")
    from .transcript import to_srt
    (out_dir / f"{cand.id}.srt").write_text(to_srt(heard))

    cuts = frame = audio = None
    if render:
        target = out_dir / f"{cand.id}.mp4"
        if "export" in steps:
            steps["export"](edit, target, width, height)
        else:
            from .export import render as export_render
            export_render(edit, target, width, height)
        made.file = target.name
        if "measure" in steps:
            m = steps["measure"](target)
        else:
            from . import style
            m = style.measure(str(target), None)
        # Scene detection misses jump cuts, so the joins in the edit count as changes too.
        cuts = sorted(set(m["cuts"]) | set(_joins(edit)))
        cuts = [t for k, t in enumerate(cuts) if k == 0 or t - cuts[k - 1] >= 0.2]
        frame, audio = m["frame"], m["audio"]
        made.seconds = round(m["frame"].get("seconds", made.seconds), 2)
    else:
        cuts = [b for b in _joins(edit)]       # where the picture jumps: every cut in the edit
        frame = {"width": width, "height": height} if reframe else None
    rubric = {k: v for k, v in judge.items() if k in SCORE_KEYS}
    if "mid_sentence" not in rubric:
        punctuated = any(ln["text"].rstrip().endswith((".", "!", "?")) for ln in cand.lines)
        ends = not punctuated or cand.lines[-1]["text"].rstrip().endswith((".", "!", "?"))
        rubric["mid_sentence"] = not ends
    rubric["captions"] = bool(captions and heard)
    rubric["text_on_frame_1"] = bool(hook)
    result = sc.score(heard, made.seconds, cuts, frame, audio, rubric)
    made.score = result.to_dict()
    made.score["text"] = "\n".join(line for line in result.text().splitlines() if "Give --video" not in line)
    return made


def punch_ins(edit: EditList, heard: list[Word], zoom: float = 1.15, every: float = 2.5) -> tuple[EditList, list[str]]:
    """Alternate a punch-in on and off at sentence starts at least `every` seconds apart, so a
    talking shot changes every few seconds. Keeps each shot's framing; only the zoom changes."""
    starts = [0.0]
    for a, b in itertools.pairwise(heard):
        if a.text.rstrip("\"')").endswith((".", "?", "!")) and b.start - starts[-1] >= every:
            starts.append(b.start)
    end = edit.duration / edit.fps
    lines = []
    for k, (a, b) in enumerate(itertools.pairwise([*starts, end])):
        if k % 2 and b - a > 0.5:
            f0, f1 = round(a * edit.fps), min(round(b * edit.fps), edit.duration)
            if f1 > f0:
                cur = max((seg.zoom for t, seg in edit.pieces() if t <= f0 < t + seg.duration), default=1.0)
                edit = edit.reframe(f0, f1, zoom=min(4.0, cur * zoom))
                lines.append(f"punch-in: {a:.1f}s to {b:.1f}s at {zoom:g}x")
    return edit, lines


def _joins(edit: EditList, jumps_only: bool = False) -> list[float]:
    """Timeline seconds where one piece ends and a piece from elsewhere in the source begins.
    `jumps_only` keeps only jumps of more than a few seconds (a cold open, not a tightened pause)."""
    out = []
    prev = None
    for start, seg in edit.pieces():
        jump = prev is not None and (seg.source != prev.source or seg.src_in != prev.src_out)
        far = prev is not None and (seg.source != prev.source or abs(seg.src_in - prev.src_out) > 3 * edit.fps)
        if jump and (far or not jumps_only):
            out.append(round(start / edit.fps, 3))
        prev = seg
    return out


# ------------------------------------------------------------------ ranking and the sheet

def rank(made: list[Made], same_topic: float = 0.55) -> list[Made]:
    """Best score first. A clip whose words mostly repeat a better one's is marked as a repeat."""
    done = sorted([m for m in made if m.score], key=lambda m: -m.total)
    kept: list[Made] = []
    for m in done:
        twin = next((k for k in kept if _overlap(m.candidate.text, k.candidate.text) >= same_topic), None)
        if twin:
            m.skipped = f"repeats {twin.candidate.id}"
        else:
            kept.append(m)
    return kept + [m for m in done if m.skipped] + [m for m in made if not m.score]


def _clock(t: float) -> str:
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t // 60 % 60):02d}:{t % 60:04.1f}" if t >= 3600 else f"{int(t // 60)}:{t % 60:04.1f}"


def _said_lines(c: Candidate, span) -> str:
    a, b = float(span[0]), float(span[1])
    return " ".join(ln["text"] for ln in c.lines if ln["end"] > a and ln["start"] < b) or ""


def fix_for(made: Made) -> str:
    if not made.score:
        return ""
    parts = made.score["parts"]
    w = min(parts, key=lambda p: p["points"] / p["out_of"])
    if made.score.get("cap"):
        return "The story is too thin to carry it: find a version with a clearer question and answer, or skip it."
    pen = [p["why"] for p in made.score.get("penalties", [])]
    if any("context" in p for p in pen):
        return "Add the missing context in the first line (or a text hook that sets it up), or skip it."
    if any("mid-sentence" in p for p in pen):
        return "Move the end to the end of a sentence."
    return f"{w['name']}: {FIXES.get(w['name'], '')}"


def sheet(made: list[Made], out: str | Path, source: str, title: str = "") -> Path:
    """An HTML review sheet: one card per clip, best first."""
    out = Path(out)
    cards = []
    for n, m in enumerate(made, 1):
        c = m.candidate
        head = html.escape(m.judge.get("title") or m.judge.get("hook_text") or c.lines[0]["text"][:80])
        if not m.score:
            cards.append(f"<section class='card dim'><h2>{c.id} · not cut</h2><p>{html.escape(m.skipped or 'not cut')}</p>"
                         f"<p class='src'>source {_clock(c.start)} to {_clock(c.end)}</p><p class='tx'>{html.escape(c.text)}</p></section>")
            continue
        s = m.score
        opening = (_said_lines(c, m.judge.get("cold_open")) if m.judge.get("cold_open") else
                   c.lines[0]["text"] if c.lines else "")
        kind = hook_type(opening) if opening else None
        kind_html = f" · opens as a {html.escape(kind['type'])} hook" if kind else " · opening fits no researched hook type"
        rows = "".join(f"<tr><td>{html.escape(p['name'])}</td><td class='n'>{p['points']:g} / {p['out_of']:g}</td>"
                       f"<td><div class='bar'><i style='width:{100 * p['points'] / p['out_of']:.0f}%'></i></div></td>"
                       f"<td class='why'>{html.escape(p['why'])}{'' if p['judged'] else ' (neutral, not judged)'}</td></tr>"
                       for p in s["parts"])
        rows += "".join(f"<tr><td>penalty</td><td class='n'>-{p['points']:g}</td><td></td><td class='why'>{html.escape(p['why'])}</td></tr>"
                        for p in s["penalties"])
        if s.get("cap"):
            rows += f"<tr><td>capped</td><td class='n'>{s['cap']['at']}</td><td></td><td class='why'>{html.escape(s['cap']['why'])}</td></tr>"
        video = (f"<video src='{html.escape(m.file)}' controls preload='metadata' playsinline></video>" if m.file
                 else "<div class='novid'>not rendered</div>")
        cuts = "".join(f"<li>{html.escape(x)}</li>" for x in m.cuts)
        notes = "".join(f"<li>{html.escape(x)}</li>" for x in m.notes)
        rep = f"<p class='rep'>{html.escape(m.skipped)}</p>" if m.skipped else ""
        cards.append(
            f"<section class='card{' dim' if m.skipped else ''}'>{video}<div class='body'>"
            f"<h2><span class='rank'>#{n}</span> {head}</h2>"
            f"<p class='big'><b>{s['total']}</b> / 100 · {html.escape(s['verdict'])} · {m.seconds:.0f}s · {c.id}</p>{rep}"
            f"<p class='fix'><b>One fix:</b> {html.escape(fix_for(m))}</p>"
            f"<p class='src'>source {_clock(c.start)} to {_clock(c.end)} · rough rank {c.rough:g}{kind_html}"
            f"{' · hook: “' + html.escape(m.judge['hook_text']) + '”' if m.judge.get('hook_text') else ''}</p>"
            f"<table>{rows}</table>"
            f"<details><summary>What was said</summary><p class='tx'>{html.escape(c.text)}</p></details>"
            f"<details><summary>Every cut ({len(m.cuts)})</summary><ul>{cuts}</ul></details>"
            + (f"<details><summary>Framing</summary><ul>{notes}</ul></details>" if notes else "")
            + "</div></section>")
    css = ("body{font:15px/1.45 system-ui,sans-serif;background:#111;color:#eee;margin:0;padding:24px}"
           "h1{font-size:22px;margin:0 0 4px}.sub{color:#aaa;margin:0 0 20px}"
           ".card{display:flex;gap:20px;background:#1c1c1f;border-radius:14px;padding:16px;margin:0 0 18px}"
           ".card.dim{opacity:.55}.card video,.novid{width:270px;height:480px;background:#000;border-radius:10px;flex:none}"
           ".novid{display:flex;align-items:center;justify-content:center;color:#666}.body{flex:1;min-width:0}"
           "h2{font-size:18px;margin:0 0 6px}.rank{color:#ffe14a}.big b{font-size:26px;color:#ffe14a}"
           ".fix{background:#2a2a10;border-left:4px solid #ffe14a;padding:6px 10px}.src,.why{color:#aaa;font-size:13px}"
           "table{border-collapse:collapse;width:100%;margin:8px 0}td{padding:3px 8px 3px 0;vertical-align:top}"
           "td.n{white-space:nowrap}.bar{width:90px;height:8px;background:#333;border-radius:4px;margin-top:6px}"
           ".bar i{display:block;height:100%;background:#4ac26b;border-radius:4px}.tx{color:#ccc}.rep{color:#f88}"
           "summary{cursor:pointer;color:#9cf;margin-top:6px}ul{color:#bbb;font-size:13px}")
    doc = (f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{html.escape(title or 'Clip review')}</title>"
           f"<style>{css}</style></head><body><h1>{html.escape(title or 'Clip review')}</h1>"
           f"<p class='sub'>From {html.escape(Path(source).name)}. {sum(1 for m in made if m.score and not m.skipped)} clips, "
           "best first. Nothing has been posted. Scores rank clips against each other; they do not predict views.</p>"
           + "".join(cards) + "</body></html>")
    out.write_text(doc, encoding="utf-8")
    return out


# ------------------------------------------------------------------ files

def save_candidates(out_dir: str | Path, source: str, transcript: str, cands: list[Candidate], settings: dict) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "candidates.json"
    path.write_text(json.dumps({"source": str(Path(source).resolve()), "transcript": str(Path(transcript).resolve()),
                                "settings": settings, "candidates": [c.to_dict() for c in cands]}, indent=2) + "\n")
    return path


def load_candidates(out_dir: str | Path) -> tuple[dict, list[Candidate]]:
    path = Path(out_dir) / "candidates.json"
    if not path.exists():
        raise EditError(f"no candidates.json in {out_dir}; run `stylebrain clip-find` first")
    data = json.loads(path.read_text())
    return data, [Candidate.from_dict(c) for c in data["candidates"]]


def extra_candidates(words: list[Word], cands: list[Candidate], judgements: dict) -> list[Candidate]:
    """Moments the judge added that the finder missed: any id in the judgements that is not a
    candidate and gives `start` and `end` (source seconds)."""
    known = {c.id for c in cands}
    out = []
    for cid, j in judgements.items():
        if cid in known or not isinstance(j, dict):
            continue
        if "start" not in j or "end" not in j:
            raise EditError(f"{cid} is not a candidate; to add a moment give its start and end")
        a, b = float(j["start"]), float(j["end"])
        lines = [{"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text}
                 for s in spoken_lines([w for w in words if a <= w.start < b])]
        if not lines:
            raise EditError(f"{cid}: nothing is said between {a:g}s and {b:g}s")
        out.append(Candidate(cid, a, b, 0.0, ["added by the judge"], lines))
    return out


def hook_type(text: str) -> dict | None:
    """The hook type a line reads as, with the most viewed researched example of that type."""
    kinds = classify_hook(text)
    if not kinds:
        return None
    out = {"type": kinds[0]}
    try:
        ex = proven_examples(kinds[0], limit=1)
    except ValueError:
        ex = []
    if ex:
        line = ex[0].get("opening") or ex[0].get("title") or ""
        if line:
            out.update(example=line[:90], views=int(ex[0].get("views") or 0))
    return out


def judging_brief(cands: list[Candidate]) -> str:
    """What a judge (Claude, or one agent per clip) reads: each candidate's timed lines and the questions."""
    from .score import FLAGS, JUDGEMENTS
    lines = ["Judge each clip as a stand-alone reel. Answer 1 to 5 for: "
             + "; ".join(f"{k} ({v})" for k, v in JUDGEMENTS.items()),
             "Flags (true/false): " + "; ".join(f"{k} ({v})" for k, v in FLAGS.items()
                                                if k in ("needs_context", "undelivered", "mid_sentence")),
             ("Cut choices: cold_open [start, end] (source seconds of the strongest line to open on, 12 s or less, "
              "or leave out); start / end (move the edges, source seconds); hook_text (on-screen hook, 8 words or less); "
              "title; skip (a reason, to leave the clip out). A moment the finder missed can be added under a new id "
              "with its start and end."), ""]
    lines.insert(-1, "From his own 2026 Instagram results (hypotheses, not rules): shares mark the hits; useful "
                     "\"here is how\" clips earn follows, sendable jokes earn reach; 11 to 15 s reels hit most often.")
    for c in cands:
        lines.append(f"== {c.id}  source {_clock(c.start)} to {_clock(c.end)} ({c.seconds:.0f}s), rough {c.rough:g}")
        kind = hook_type(c.lines[0]["text"]) if c.lines else None
        if kind:
            lines.append(f"   opening line reads as a {kind['type']} hook" + (
                f"; proven example: \"{kind['example']}\" ({kind['views']:,} views)" if kind.get("example") else ""))
        for ln in c.lines:
            lines.append(f"  [{ln['start']:.2f}-{ln['end']:.2f}] {ln['text']}")
        lines.append("")
    return "\n".join(lines)
