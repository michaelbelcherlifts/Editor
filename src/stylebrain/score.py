"""Score a short clip from 0 to 100 on the virality rubric.

Seven weighted parts, then penalties. Some parts are measured (word timings,
cuts, length, frame shape, loudness). Others are judgements that Claude makes
by reading the transcript and looking at frames, passed in as numbers from 1
to 5. Every part is listed with its points and the reason, so the total can
be checked rather than trusted.

The weights are a starting proposal. Until they are tuned against real
analytics the score ranks clips against each other; it does not predict views.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .edl import EditError
from .transcript import Word, _norm

FILLERS = {"so", "um", "uh", "er", "okay", "ok", "alright", "right", "hey", "hi", "hello", "guys", "well",
           "yeah", "yo", "like", "now", "and", "whats", "what's", "up", "everyone", "everybody"}

JUDGEMENTS = {
    "promise": "Is it clear in the first line what the viewer will get? 1 no idea, 5 unmistakable",
    "payoff": "Is the opening promise answered on screen, and does the end land or loop? 1 never, 5 fully",
    "value": "Does the viewer learn a usable thing or feel something? 1 nothing, 5 strongly",
    "share": "Is there a clear reason to send this to someone or argue in comments? 1 none, 5 obvious",
    "trend": "Does the topic, format or sound match what is rising now? 1 stale, 5 on trend (3 if unknown)",
}
FLAGS = {
    "text_on_frame_1": "A text hook is on screen in the first frame",
    "captions": "Captions are present and inside the safe area",
    "needs_context": "Only makes sense with the long video it came from (minus 15)",
    "undelivered": "The hook promises something the clip never delivers (minus 10)",
    "mid_sentence": "Starts or ends mid-sentence (minus 5)",
}


@dataclass(frozen=True)
class Part:
    name: str
    points: float
    out_of: float
    why: str
    judged: bool = True  # False when a judgement was missing and a neutral value was used


@dataclass
class Score:
    parts: list[Part] = field(default_factory=list)
    penalties: list[tuple[str, float]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return max(0, min(100, round(sum(p.points for p in self.parts) - sum(v for _, v in self.penalties))))

    @property
    def verdict(self) -> str:
        return "post first" if self.total >= 80 else "worth posting after one fix" if self.total >= 60 else "skip or recut"

    @property
    def weakest(self) -> Part:
        return min(self.parts, key=lambda p: p.points / p.out_of)

    def text(self) -> str:
        lines = [f"{self.total} / 100: {self.verdict}"]
        for p in self.parts:
            lines.append(f"  {p.name:<13}{p.points:>5.1f} / {p.out_of:<3g} {p.why}" + ("" if p.judged else "  (not judged, neutral used)"))
        for why, v in self.penalties:
            lines.append(f"  penalty      -{v:g}  {why}")
        w = self.weakest
        lines.append(f"  weakest part: {w.name}")
        unjudged = [p.name for p in self.parts if not p.judged]
        if unjudged:
            lines.append(f"  not fully judged: {', '.join(unjudged)}. Give --video and --judge to complete the score.")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {"total": self.total, "verdict": self.verdict, "weakest": self.weakest.name,
                "parts": [asdict(p) for p in self.parts],
                "penalties": [{"why": w, "points": v} for w, v in self.penalties]}


def _ramp(value: float, full: float, zero: float) -> float:
    """1.0 at `full`, 0.0 at `zero`, straight line between."""
    if full == zero:
        return 1.0 if value == full else 0.0
    return max(0.0, min(1.0, (value - zero) / (full - zero)))


def first_real_word(words: list[Word]) -> Word | None:
    for w in words:
        if _norm(w.text) and _norm(w.text) not in FILLERS:
            return w
    return None


def score(words: list[Word], duration: float, cuts: list[float] | None = None, frame: dict | None = None,
          audio: dict | None = None, judge: dict | None = None) -> Score:
    """Score one clip.

    words: word timings of the clip. duration: clip length in seconds.
    cuts: times of visual changes (None when there is no video to measure).
    frame: {"width", "height"}; audio: {"loudness_lufs"} as measured by style.py.
    judge: Claude's judgements (JUDGEMENTS keys, 1 to 5) and FLAGS (true/false).
    """
    if duration <= 0:
        raise EditError("the clip has no length")
    judge = dict(judge or {})
    for key in judge:
        if key not in JUDGEMENTS and key not in FLAGS:
            raise EditError(f"unknown judgement {key!r}; use {', '.join([*JUDGEMENTS, *FLAGS])}")
    for key in JUDGEMENTS:
        if key in judge and not 1 <= float(judge[key]) <= 5:
            raise EditError(f"{key} is scored from 1 to 5")

    def rated(key: str) -> tuple[float, bool]:
        if key in judge:
            return (float(judge[key]) - 1) / 4, True
        return 0.5, False

    out = Score()

    # Hook, 25: first meaningful word (10), first visual change (5), text on frame 1 (5), clear promise (5)
    # A clip with no speech (music and pictures only) is judged on its pictures: the 10 points
    # for the first word go to how soon the picture changes instead.
    first = first_real_word(words)
    silent = not words
    judged = True
    if silent:
        why = ["no speech, so the opening is judged on the picture"]
        word_pts = 0.0
    else:
        t = first.start if first else duration
        word_pts = 10 * _ramp(t, 0.3, 3.0)
        why = [f"first real word at {t:.1f}s"]
    change_max = 15 if silent else 5
    if cuts is None:
        change_pts = change_max / 2
        why.append("first visual change not measured")
        judged = False
    else:
        c = cuts[0] if cuts else duration
        change_pts = change_max * _ramp(c, 1.0, 4.0)
        why.append(f"first cut at {c:.1f}s" if cuts else "picture never cuts")
    if "text_on_frame_1" in judge:
        text_pts = 5.0 if judge["text_on_frame_1"] else 0.0
        why.append("text on frame 1" if judge["text_on_frame_1"] else "no text on frame 1")
    else:
        text_pts, judged = 2.5, False
    promise, ok = rated("promise")
    judged &= ok
    out.parts.append(Part("Hook", round(word_pts + change_pts + text_pts + 5 * promise, 1), 25, "; ".join(why), judged))

    # Pacing, 20: pauses (8), a change every 2 to 4 s (7), length 15 to 45 s (5)
    judged = True
    if silent:
        pause_pts, why = 8.0, ["no speech"]
    else:
        gaps = [b.start - a.end for a, b in zip(words, words[1:])]
        worst = max(gaps, default=0.0)
        pause_pts = 8 * _ramp(worst, 0.3, 1.5)
        why = [f"longest pause {worst:.1f}s"]
    if cuts is None:
        change_pts, judged = 3.5, False
        why.append("visual changes not measured")
    else:
        every = duration / (len(cuts) + 1)
        change_pts = 7 * (_ramp(every, 4.0, 10.0) if every > 4 else _ramp(every, 2.0, 0.5) if every < 2 else 1.0)
        why.append(f"a change every {every:.1f}s")
    length_pts = 5 * (1.0 if 15 <= duration <= 45 else _ramp(duration, 15, 5) if duration < 15 else _ramp(duration, 45, 90))
    why.append(f"{duration:.0f}s long")
    out.parts.append(Part("Pacing", round(pause_pts + change_pts + length_pts, 1), 20, "; ".join(why), judged))

    for name, key, weight in (("Payoff", "payoff", 15), ("Value/emotion", "value", 15), ("Shareability", "share", 10),
                              ("Trend fit", "trend", 10)):
        r, ok = rated(key)
        out.parts.append(Part(name, round(weight * r, 1), weight, f"judged {judge[key]:g} of 5" if ok else "", ok))

    # Craft, 5: vertical frame (2), loudness (1.5), captions (1.5)
    why, judged, pts = [], True, 0.0
    if frame:
        ratio = frame["height"] / frame["width"]
        pts += 2 * _ramp(ratio, 16 / 9, 1.0)
        why.append("vertical" if ratio >= 1.7 else "not 9:16")
    else:
        pts, judged = pts + 1.0, False
    if audio and audio.get("loudness_lufs") is not None:
        off = abs(audio["loudness_lufs"] + 14)
        pts += 1.5 * _ramp(off, 2.0, 8.0)
        why.append(f"{audio['loudness_lufs']:g} LUFS")
    else:
        pts, judged = pts + 0.75, False
    if "captions" in judge:
        pts += 1.5 if judge["captions"] else 0.0
        why.append("captions" if judge["captions"] else "no captions")
    else:
        pts, judged = pts + 0.75, False
    out.parts.append(Part("Craft", round(pts, 1), 5, "; ".join(why), judged))

    for key, points in (("needs_context", 15), ("undelivered", 10), ("mid_sentence", 5)):
        if judge.get(key):
            out.penalties.append((FLAGS[key].split(" (")[0], points))
    if duration > 60:
        late = [c for c in (cuts or []) if c > 30]
        if cuts is not None and not late:
            out.penalties.append(("Over 60 seconds with no new beat after 30 s", 5))
    return out
