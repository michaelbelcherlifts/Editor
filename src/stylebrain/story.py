"""Story and hook checks that run on word timings.

The story comes before the look: a clip with nothing to find out does not
hold viewers however it is cut. These checks find what can be measured from
the transcript (and cut times when there is a video): a slow or empty start,
long sentences, stretches with no new question, "and then" narration. What
needs reading (what the viewer wants to find out, whether the promise is
paid off) is Claude's judgement, passed in or asked for by name.

Nothing here changes the edit. Every finding carries the second it happens.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .transcript import Word, _norm

# Words that carry no meaning at the start of a clip.
FILLERS = {"so", "um", "uh", "er", "okay", "ok", "alright", "right", "hey", "hi", "hello", "guys", "well",
           "yeah", "yo", "like", "now", "and", "whats", "what's", "up", "everyone", "everybody"}

# Openings that delay the point: greetings, self-introductions, "in this video".
SLOW_OPENERS = ("welcome back to the channel", "welcome back to my channel", "welcome to the channel",
                "welcome to my channel", "welcome back", "welcome to", "my name is", "in this video", "in today's video", "today i'm going to",
                "today we're going to", "before we start", "before we get into", "don't forget to", "make sure you",
                "what's up guys", "hey guys", "how's it going", "let's get into it", "without further ado")

QUESTION_CUES = ("?", "but ", "what if", "here's why", "here is why", "the reason", "find out", "can i ", "will i ",
                 "could i ", "is it ", "turns out", "the problem", "except", "until ", "the catch", "the question",
                 "which one", "guess", "wait", "not what", "the truth", "nobody tells", "the real", "secret")
CAUSE_JOINS = ("but", "so", "therefore", "because", "which meant", "that's why", "until", "except", "which is why")
FLAT_JOINS = ("and then", "then", "after that", "and also", "also", "next")

SENTENCE_GAP = 0.7  # a pause this long ends a sentence when punctuation is missing


@dataclass(frozen=True)
class Sentence:
    text: str
    start: float
    end: float
    words: int


@dataclass(frozen=True)
class Finding:
    at: float | None  # seconds; None for whole-clip notes
    kind: str         # dead_air, slow_opener, first_point, first_change, text, payoff, loop, sentence, ...
    text: str
    serious: bool = True

    def line(self) -> str:
        where = "overall" if self.at is None else f"{self.at:6.1f}s"
        return f"{where:>8}  [{self.kind}] {self.text}"


def sentences(words: list[Word], gap: float = SENTENCE_GAP) -> list[Sentence]:
    """Split word timings into sentences, at . ? ! or at a pause of `gap` seconds."""
    out: list[Sentence] = []
    cur: list[Word] = []

    def close() -> None:
        if cur:
            out.append(Sentence(" ".join(w.text for w in cur), cur[0].start, cur[-1].end, len(cur)))
            cur.clear()

    for i, w in enumerate(words):
        if cur and w.start - cur[-1].end >= gap:
            close()
        cur.append(w)
        if w.text.rstrip("\"')").endswith((".", "?", "!")):
            close()
    close()
    return out


def from_text(text: str, words_per_second: float = 2.8) -> list[Word]:
    """Approximate word timings for a written script, at a normal talking pace."""
    out, t, each = [], 0.0, 1 / words_per_second
    for line in text.splitlines():
        for w in line.split():
            out.append(Word(w, round(t, 3), round(t + each * 0.85, 3)))
            t += each
        if line.strip():
            t += 0.35  # a beat between lines
    return out


def first_real_word(words: list[Word]) -> Word | None:
    for w in words:
        if _norm(w.text) and _norm(w.text) not in FILLERS:
            return w
    return None


def _low(s: str) -> str:
    return " " + re.sub(r"\s+", " ", s.lower()) + " "


def _is_point(s: Sentence) -> bool:
    """A sentence that tells the viewer something: three or more real words once greetings and
    "in this video" set-ups are taken out."""
    low = _low(s.text)
    for o in sorted(SLOW_OPENERS, key=len, reverse=True):
        low = low.replace(o, " ")
    real = [t for t in (_norm(x) for x in low.split()) if t and t not in FILLERS]
    return len(real) >= 3


def first_useful_point(words: list[Word], at: float | None = None) -> float | None:
    """Seconds until the first sentence that says something. `at` overrides with Claude's own reading."""
    if at is not None:
        return float(at)
    for s in sentences(words):
        if _is_point(s):
            return s.start
    return None


def average_sentence_words(words: list[Word]) -> float:
    ss = sentences(words)
    return round(sum(s.words for s in ss) / len(ss), 1) if ss else 0.0


def longest_shot(cuts: list[float], duration: float) -> tuple[float, float]:
    """(length, start) of the longest stretch with no change of picture."""
    edges = [0.0, *sorted(c for c in cuts if 0 < c < duration), duration]
    return max(((round(b - a, 2), a) for a, b in zip(edges, edges[1:])), default=(duration, 0.0))


def _overlap(a: str, b: str) -> float:
    ta = {t for t in (_norm(x) for x in a.split()) if t and t not in FILLERS and len(t) > 2}
    tb = {t for t in (_norm(x) for x in b.split()) if t and t not in FILLERS and len(t) > 2}
    return len(ta & tb) / max(1, min(len(ta), len(tb)))


def hook_check(words: list[Word], duration: float, cuts: list[float] | None = None,
               judge: dict | None = None) -> list[Finding]:
    """Problems in the first seconds of a short, each with the second it happens.

    judge may hold `text_on_frame_1` (bool), `undelivered` (bool, the promise is
    never paid off) and `first_point` (seconds, Claude's reading of when the
    first useful point lands). Missing judgements are named, not guessed.
    """
    judge = judge or {}
    out: list[Finding] = []
    ss = sentences(words)
    first = first_real_word(words)
    if first is None:
        out.append(Finding(0.0, "dead_air", "Nobody says anything meaningful. A short needs a spoken or written hook."))
    else:
        before = [w.text for w in words if w.start < first.start]
        if first.start > 0.5 or before:
            said = f" ({' '.join(before)})" if before else ""
            out.append(Finding(0.0, "dead_air", f"The first meaningful word is at {first.start:.1f}s{said}. "
                               f"Trim to start on \"{first.text}\"."))
    if ss:
        low = _low(ss[0].text)
        slow = [o for o in SLOW_OPENERS if o in low]
        if slow:
            out.append(Finding(ss[0].start, "slow_opener", f"Opens with \"{slow[0]}\". Open on the stake, the payoff "
                               "or the doubt instead."))
    point = first_useful_point(words, judge.get("first_point"))
    if point is None:
        out.append(Finding(None, "first_point", "No sentence makes a point. What will the viewer find out?"))
    elif point > 3.0:
        out.append(Finding(point, "first_point", f"The first useful point lands at {point:.1f}s. In a short it "
                           "should land inside 3 seconds; move it to the front as a cold open."))
    if cuts is not None:
        c = min(cuts) if cuts else duration
        if c > 1.5:
            out.append(Finding(c, "first_change", f"The picture first changes at {c:.1f}s. Aim for under 1 second: "
                               "a punch-in, a text pop or starting mid-movement."))
    if "text_on_frame_1" not in judge:
        out.append(Finding(0.0, "text", "Not checked: is there a 3 to 8 word text hook on frame 1? Look at frame 1.",
                           serious=False))
    elif not judge["text_on_frame_1"]:
        out.append(Finding(0.0, "text", "No text hook on frame 1. Most viewers decide with the sound off."))
    if judge.get("undelivered"):
        out.append(Finding(None, "payoff", "The hook promises something the clip never pays off. Show the answer, "
                           "or change the hook to match what the clip delivers."))
    elif "undelivered" not in judge:
        out.append(Finding(None, "payoff", "Not checked: is the hook's promise answered on screen? Read the end.",
                           serious=False))
    if len(ss) >= 2:
        last = ss[-1]
        if _norm(last.text.split()[-1]) in {"yeah", "it", "guys", "bye", "peace", "out"} or "so yeah" in _low(last.text):
            out.append(Finding(last.start, "ending", f"Ends on \"{last.text}\". End on the payoff or a line that "
                               "leads back into the first one."))
        elif _overlap(ss[0].text, last.text) < 0.25:
            out.append(Finding(last.start, "loop", "The ending does not lead back into the opening, so replays "
                               "will not feel seamless. Optional: echo the first line's words in the last one.",
                               serious=False))
    for s in ss:
        if s.words > 25:
            out.append(Finding(s.start, "sentence", f"A {s.words}-word sentence. Split it; one idea per line.",
                               serious=False))
    return sorted(out, key=lambda f: (f.at is None, f.at or 0.0))


# ------------------------------------------------------------------ long-form

BEATS = ("hook", "setup", "escalation", "low point", "payoff", "next loop")


def question_moments(words: list[Word]) -> list[tuple[float, str]]:
    """Sentences that open a question or a turn: a ?, a but, a 'here's why', a 'can I'."""
    out = []
    for s in sentences(words):
        low = _low(s.text)
        if any(c in low for c in QUESTION_CUES) or s.text.rstrip().endswith("?"):
            out.append((s.start, s.text))
    return out


def and_then_stretches(words: list[Word], run: int = 3) -> list[tuple[float, float, int]]:
    """Runs of `run` or more sentences joined by "and then" with no cause between them.

    Returns (start, end, sentences). These are where a stake or a reason is missing.
    """
    out, ss = [], sentences(words)
    start, count = None, 0
    for prev, s in zip(ss, ss[1:]):
        head = _low(" ".join(s.text.split()[:3]))
        flat = any(head.startswith(f" {j} ") for j in FLAT_JOINS) or " and then " in head
        cause = any(head.startswith(f" {j} ") for j in CAUSE_JOINS)
        if flat and not cause:
            start = prev.start if start is None else start
            count += 1
            end = s.end
        else:
            if start is not None and count + 1 >= run:
                out.append((start, end, count + 1))
            start, count = None, 0
    if start is not None and count + 1 >= run:
        out.append((start, end, count + 1))
    return out


@dataclass
class BeatMap:
    beats: list[dict]          # {"label", "start", "end", "seconds"}
    questions: list[tuple[float, str]]
    dead: list[tuple[float, float]]   # stretches longer than the limit with no new question
    and_then: list[tuple[float, float, int]]
    problems: list[str]

    def text(self) -> str:
        lines = []
        if self.beats:
            lines.append("Beats:")
            for b in self.beats:
                lines.append(f"  {_clock(b['start'])} to {_clock(b['end'])}  {b['label']:<11} {b['seconds']:.0f}s")
        lines.append(f"{len(self.questions)} moments that open a question or a turn.")
        for a, b in self.dead:
            lines.append(f"  dead stretch {_clock(a)} to {_clock(b)}: {b - a:.0f}s with no new question. "
                         "Add a re-hook: a question, a reveal or a change of scene.")
        for a, b, n in self.and_then:
            lines.append(f"  \"and then\" run {_clock(a)} to {_clock(b)}: {n} sentences in a row with no but or "
                         "therefore. What is at stake, or what caused what?")
        for p in self.problems:
            lines.append(f"  beat order: {p}")
        if not self.dead and not self.and_then and not self.problems:
            lines.append("No dead stretches or \"and then\" runs found.")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {"beats": self.beats, "questions": [{"at": a, "text": t} for a, t in self.questions],
                "dead": [{"start": a, "end": b} for a, b in self.dead],
                "and_then": [{"start": a, "end": b, "sentences": n} for a, b, n in self.and_then],
                "problems": self.problems}


def _clock(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def beat_map(words: list[Word], duration: float | None = None, beats: list[dict] | None = None,
             extra_questions: list[float] | None = None, limit: float = 60.0) -> BeatMap:
    """Map a long-form transcript.

    beats: Claude's labels from reading the transcript, as [{"label", "start"}]
    with labels from BEATS; each beat runs to the next one's start. Questions
    are found in the transcript; extra_questions adds times Claude marked
    (a reveal or a change of scene that the words do not show).
    """
    if duration is None:
        duration = words[-1].end if words else 0.0
    qs = question_moments(words)
    times = sorted({round(t, 2) for t, _ in qs} | {round(float(t), 2) for t in (extra_questions or [])})
    edges = [0.0, *times, duration]
    dead = [(a, b) for a, b in zip(edges, edges[1:]) if b - a > limit]
    out, problems = [], []
    if beats:
        ordered = sorted(beats, key=lambda b: float(b["start"]))
        for b in ordered:
            if b["label"] not in BEATS:
                raise ValueError(f"unknown beat {b['label']!r}; use {', '.join(BEATS)}")
        for b, nxt in zip(ordered, [*ordered[1:], None]):
            s, e = float(b["start"]), float(nxt["start"]) if nxt else duration
            out.append({"label": b["label"], "start": s, "end": e, "seconds": round(e - s, 1)})
        labels = [b["label"] for b in out]
        for need in ("hook", "payoff"):
            if need not in labels:
                problems.append(f"no {need} marked")
        if labels and labels[0] != "hook":
            problems.append(f"starts with {labels[0]}, not the hook")
        if "payoff" in labels and "hook" in labels and labels.index("payoff") < labels.index("hook"):
            problems.append("the payoff comes before the hook")
        hook = next((b for b in out if b["label"] == "hook"), None)
        if hook and hook["seconds"] > 30:
            problems.append(f"the hook runs {hook['seconds']:.0f}s; in long-form it should be done by 30s")
        setup = sum(b["seconds"] for b in out if b["label"] == "setup")
        if duration and setup > duration * 0.25:
            problems.append(f"setup is {setup / duration:.0%} of the video; cut what does not raise the stakes")
    return BeatMap(out, qs, dead, and_then_stretches(words), problems)


# ------------------------------------------------------------------ hooks and scripts

HOOK_TYPES = {
    "mistake": ("Stop doing X like this", "Stop doing curls like this if you want bigger arms."),
    "contrarian": ("The common belief is wrong", "Cardio isn't why you're not losing fat."),
    "result": ("The result first, then how", "Six months ago I couldn't bench 225."),
    "number": ("A specific count", "The 3 exercises that added an inch to my arms."),
    "stakes": ("A goal, a deadline, a cost of failing", "I have 30 days to hit a 500 lb deadlift."),
    "curiosity": ("An answer held back", "This one cue fixed my squat instantly."),
    "pov": ("A situation the viewer has lived", "POV: someone takes your bench mid-set."),
    "proof": ("Someone with authority, or proof on screen", "I asked a powerlifting coach to fix my deadlift."),
    "question": ("A question the viewer answers in their head", "Are you actually training to failure?"),
    "challenge": ("Can I do X? A bar to clear, live", "Can a 182 lb powerlifter run a sub 6 mile?"),
    "test": ("A bet or a test on someone else", "If you can bench 225 once, I'll pay your gym fee."),
    "versus": ("Two tribes or two people head to head", "Powerlifter vs marathoner: who wins the 400?"),
    "how-many": ("How many X does it take: escalate until it breaks", "How many plates can a cheap barbell hold?"),
    "underdog": ("Someone underestimated, then the reveal", "They thought the big guy would walk the 5K."),
    "ranking": ("Rank a set of things, worst to best", "Ranking every powerlifting excuse."),
    "how-to": ("How to X in a few steps", "How to deadlift: 3 cues, 30 seconds."),
    "tribe": ("An in-joke only one group gets", "Powerlifters will genuinely defend this."),
    "constraint": ("A hard limit: money, time, calories, a rule", "Every mile I run buys 10 minutes of my phone."),
}

# Words and shapes that mark each hook type, for sorting a written or spoken
# opening. A hook can be more than one type; a weak hook matches none.
HOOK_MARKS = {
    "mistake": r"^stop\b|\bstop (doing|\w+ing)\b|\b(don'?t|never|wrong|mistakes?)\b",
    "contrarian": r"\b(isn'?t|aren'?t|not why|myth|overrated|lie|lying|actually|truth)\b",
    "result": r"\b(ago|went from|used to|couldn'?t|before and after)\b",
    "number": r"\b\d+ (things|ways|exercises|tips|mistakes|foods|steps|reasons|rules|cues|meals|accessories)\b",
    "stakes": r"\b\d+ (days|weeks|hours|months) to\b|\bor (i|else)\b|\bdeadline\b",
    "curiosity": r"\b(this one|the one|secret|nobody|not allowed|here'?s why|what happened|the reason)\b",
    "pov": r"^pov\b|\bwhen (you|someone|your|the)\b",
    "proof": r"\b(coach|seal|ranger|expert|doctor|asked an?|olympian|world record|record)\b",
    "question": r"\?[!.]*\s*$|^(are|do|does|is|have|would|should) (you|your)\b",
    "challenge": r"^(can|could|will|how fast can|how far can|how heavy can) (i|a|an|my)\b|\b(attempt|trying to|try to)\b",
    "test": r"\bif you (can|could)\b|\bi('?ll| will) (give|pay|fill|buy)\b|\btest(ing)? (if|whether)\b|\bbet\b",
    "versus": r"\bvs\.?\b|\bversus\b|\bhead to head\b",
    "how-many": r"\bhow many\b|\bhow (much|far|fast|long|heavy) (can|does|will)\b",
    "underdog": r"\b(pretend|disguis|undercover|thought i was|underestimat|didn'?t expect|nobody expected)",
    "ranking": r"\b(rank|ranking|ranked|tier list|best to worst|worst to best)\b",
    "how-to": r"^how to\b|\b\d+ (simple )?steps\b",
    "tribe": r"\bonly \w+ (understand|know|get)\b|\bwill (genuinely )?defend\b|\b\w+ers be like\b|\bevery \w+er\b",
    "constraint": r"\$\d|\bon a budget\b|\bcheap\b|\bfor \d+ (days|hours)\b|=\s*\d|\bonly (eat|ate|eating|use|using)\b",
}

HOOK_LIBRARY = Path("library/hooks")


def classify_hook(text: str) -> list[str]:
    """Hook types a line fits, most specific first. Empty when it fits none."""
    low = _low(text).strip()
    order = ["test", "how-many", "underdog", "versus", "challenge", "ranking", "how-to", "tribe", "constraint",
             "stakes", "result", "number", "mistake", "contrarian", "curiosity", "proof", "pov", "question"]
    return [k for k in order if re.search(HOOK_MARKS[k], low)]


def hook_library(path: str | Path = HOOK_LIBRARY) -> dict:
    """The researched hook patterns (library/hooks/patterns.json): each type with why it works,
    templates for Michael, and proven examples with their views."""
    f = Path(path) / "patterns.json" if Path(path).is_dir() or not str(path).endswith(".json") else Path(path)
    if not f.exists():
        return {"patterns": {}}
    return json.loads(f.read_text())


def proven_examples(kind: str | None = None, niche: str | None = None, path: str | Path = HOOK_LIBRARY,
                    limit: int = 5) -> list[dict]:
    """Researched examples, most viewed first, filtered by hook type and niche."""
    lib = hook_library(path).get("patterns", {})
    if kind and kind not in HOOK_TYPES:
        raise ValueError(f"unknown hook type {kind!r}; use {', '.join(HOOK_TYPES)}")
    out = []
    for k, pat in lib.items():
        if kind and k != kind:
            continue
        for ex in pat.get("examples", []):
            if niche and ex.get("niche") != niche:
                continue
            out.append({"type": k, **ex})
    out.sort(key=lambda e: -(e.get("views") or 0))
    return out[:limit] if limit else out

STORY_QUESTIONS = {
    "want": "Is there a clear want or goal, with a number or a deadline? 1 none, 5 unmistakable",
    "stakes": "Is there a reason it might fail, or a cost if it does? 1 none, 5 real doubt",
    "question": "Is there an open question the viewer needs answered, renewed before the old one closes? 1 no, 5 always",
    "causes": "Are beats joined by but or therefore rather than and then? 1 a list, 5 each beat causes the next",
    "payoff": "Is the question answered on screen, and is something different by the end? 1 never, 5 fully",
}


def story_points(answers: dict) -> float:
    """Story out of 25 from the five STORY_QUESTIONS answered 1 to 5 (missing ones count as 3)."""
    for k, v in answers.items():
        if k not in STORY_QUESTIONS:
            raise ValueError(f"unknown story question {k!r}; use {', '.join(STORY_QUESTIONS)}")
        if not 1 <= float(v) <= 5:
            raise ValueError(f"{k} is answered from 1 to 5")
    return round(sum(5 * (float(answers.get(k, 3)) - 1) / 4 for k in STORY_QUESTIONS), 1)


def check_hook_option(spoken: str, on_screen: str) -> list[str]:
    """Problems with one written hook: the spoken line and its on-screen text."""
    out = []
    toks = [_norm(t) for t in spoken.split() if _norm(t)]
    if not toks:
        return ["no spoken line"]
    if toks[0] in FILLERS:
        out.append(f"the spoken line starts with \"{spoken.split()[0]}\"; start on a word that means something")
    if any(o in _low(spoken) for o in SLOW_OPENERS):
        out.append("the spoken line greets or introduces instead of hooking")
    if len(toks) > 15:
        out.append(f"the spoken line is {len(toks)} words; keep it under 15 (about 3 seconds)")
    n = len(on_screen.split())
    if not 3 <= n <= 8:
        out.append(f"on-screen text is {n} words; use 3 to 8, readable in one glance")
    return out


def check_script(text: str) -> dict:
    """Measured checks on a written script: one spoken line per line of text.

    Returns the hook line's problems, sentence lengths, "and then" runs,
    where the new questions fall, whether there are concrete numbers, and
    whether the ending echoes the opening.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    words = from_text("\n".join(lines))
    duration = words[-1].end if words else 0.0
    ss = sentences(words)
    qs = question_moments(words)
    late = [t for t, _ in qs if duration and 0.45 <= t / duration <= 0.85]
    out = {
        "lines": len(lines),
        "seconds": round(duration, 1),
        "average_sentence_words": average_sentence_words(words),
        "long_sentences": [s.text for s in ss if s.words > 20],
        "hook_problems": check_hook_option(lines[0], " ".join(lines[0].split()[:8])) if lines else ["empty script"],
        "and_then_runs": len(and_then_stretches(words)),
        "question_moments": len(qs),
        "new_question_late": bool(late),
        "has_numbers": bool(re.search(r"\d", text)),
        "ending_echoes_opening": len(lines) > 1 and _overlap(lines[0], lines[-1]) >= 0.25,
    }
    notes = list(out["hook_problems"])
    if out["average_sentence_words"] > 14:
        notes.append(f"sentences average {out['average_sentence_words']} words; aim for 14 or fewer")
    if out["and_then_runs"]:
        notes.append("an \"and then\" run: join those lines with but or therefore, or cut one")
    if not out["new_question_late"]:
        notes.append("no new question or turn between 45% and 85% of the way through; add one about two thirds in")
    if not out["has_numbers"]:
        notes.append("no concrete numbers; a weight, a time or a count makes it feel true")
    out["notes"] = notes
    return out


def to_json(findings: list[Finding]) -> list[dict]:
    return [asdict(f) for f in findings]
