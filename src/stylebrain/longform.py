"""Long-form YouTube structure: chapters, the opening, re-hooks and where the payoff lands.

Targets come from a study of 10 to 20 minute videos by Jeff Nippard, Chris
Bumstead, Sam Sulek, Noah Anderson, Jun Yuh and TOGI (37 videos with chapters,
7 transcripts read, November 2026; see docs/long-form.md). They describe what
those channels do, not proof of what makes a video hold viewers; recalibrate
once Michael's own YouTube retention is in.

Nothing here changes the edit. Findings carry the second they happen and reuse
`story.Finding`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .story import (QUESTION_CUES, SLOW_OPENERS, Finding, _low, and_then_stretches, first_real_word,
                    question_moments, sentences)
from .transcript import Word

# What the studied channels do (medians across 37 chaptered videos of 8 to 25 minutes).
TARGETS = {
    "intro_median": 79,         # seconds before the first chapter after 0:00 (quartiles 50 to 122)
    "intro_max": 120,           # past this the set-up is longer than three in four studied videos
    "chapter_median": 131,      # seconds per chapter (three in four under 175)
    "chapter_max": 300,         # the longest chapter in a typical video is about 4 minutes
    "chapters": (4, 10),        # chapters in a 10 to 20 minute video (median 7)
    "premise_by": 30,           # the question or stake is said inside 30 seconds (every studied hook did)
    "loop_by": 90,              # an open loop ("later in the video") is promised early
    "words_per_minute": (165, 245),  # studied talking pace: Noah 169, CBum 175, Jeff 190 to 204, Jun 244
    "payoff_from": 0.6,         # the big answer lands in the last 40% (Jeff's results at 73%, blood tests at 75%)
    "outro_max": 90,            # seconds from the payoff to the end
    "silence": 4.0,             # seconds with nobody talking that are worth a look
    "dead_stretch": 90,         # seconds with no new question or turn
}

# YouTube's own rules for chapters in a description.
YT_MIN_CHAPTERS, YT_MIN_SECONDS = 3, 10

LOOP_CUES = ("later in the video", "later in this video", "at the end", "stick around", "stay tuned", "but first",
             "before we get to", "we'll get to", "we will get to", "more on that", "coming up", "by the end",
             "spoiler", "you'll see", "you will see", "find out", "wait until", "wait till")

CTA_CUES = ("link in the description", "link below", "use code", "promo code", "sponsor", "coaching", "apply",
            "subscribe", "first link", "check out my")


def clock(t: float) -> str:
    t = int(round(t))
    h, m, s = t // 3600, t % 3600 // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ------------------------------------------------------------------ chapters

@dataclass
class ChapterReport:
    lines: list[str]      # the block to paste into the YouTube description
    problems: list[str]   # YouTube will not show chapters until these are fixed
    notes: list[str]      # against the studied targets; worth a look, not rules

    def text(self) -> str:
        out = list(self.lines) or ["(no chapters)"]
        out += [f"YouTube: {p}" for p in self.problems]
        out += [f"note: {n}" for n in self.notes]
        if not self.problems:
            out.append("YouTube will show these chapters.")
        return "\n".join(out)


def check_chapters(items: list[tuple[float | None, str]], duration: float) -> ChapterReport:
    """items: (seconds on the timeline or None if its moment was cut, title)."""
    lost = [t for at, t in items if at is None]
    live = sorted((float(at), t.strip()) for at, t in items if at is not None)
    problems, notes = [], []
    for t in lost:
        problems.append(f"chapter {t!r} sits on a moment that was cut; add it again where it now starts")
    if live and live[0][0] > 0:
        notes.append(f"the first chapter starts at {clock(live[0][0])}; it is listed at 0:00, so the opening joins it")
        live[0] = (0.0, live[0][1])
    lines = [f"{clock(at)} {title}" for at, title in live]
    if len(live) < YT_MIN_CHAPTERS:
        problems.append(f"{len(live)} chapters; YouTube needs at least {YT_MIN_CHAPTERS}, the first at 0:00")
    ends = [at for at, _ in live[1:]] + [duration]
    for (at, title), end in zip(live, ends):
        if end - at < YT_MIN_SECONDS:
            problems.append(f"{title!r} runs {end - at:.0f}s; YouTube needs every chapter to be {YT_MIN_SECONDS}s or more")
    if len(live) >= 2 and live[1][0] > TARGETS["intro_max"]:
        notes.append(f"the opening runs {clock(live[1][0])} before the first chapter; the studied median is "
                     f"{TARGETS['intro_median']}s and three in four were under {TARGETS['intro_max']}s")
    for (at, title), end in zip(live[1:], ends[1:]):
        if end - at > TARGETS["chapter_max"]:
            notes.append(f"{title!r} runs {clock(end - at)}; studied chapters are about {clock(TARGETS['chapter_median'])}. "
                         "Split it, or put a turn in the middle")
    lo, hi = TARGETS["chapters"]
    if duration >= 480 and live and not lo <= len(live) <= hi:
        notes.append(f"{len(live)} chapters; the studied 10 to 20 minute videos had {lo} to {hi}")
    return ChapterReport(lines, problems, notes)


# ------------------------------------------------------------------ structure

def _has(text: str, cues) -> bool:
    low = _low(text)
    return any(c in low for c in cues)


def _window(words: list[Word], a: float, b: float) -> str:
    return " ".join(w.text for w in words if a <= w.start < b)


def structure_check(words: list[Word], duration: float, chapters: list[tuple[float, str]] | None = None,
                    cuts: list[float] | None = None, payoff_at: float | None = None,
                    cta_at: list[float] | None = None) -> list[Finding]:
    """Problems with a long-form cut, each with the second it happens.

    chapters: (seconds, title) on the timeline. payoff_at: Claude's or
    Michael's reading of when the video's main question is answered.
    cta_at: when a pitch (coaching, a product, subscribe) runs; found in the
    words when not given.
    """
    out: list[Finding] = []
    ss = sentences(words)
    chapters = sorted(chapters or [])

    # The opening
    first = first_real_word(words)
    if first is None:
        return [Finding(0.0, "dead_air", "Nobody speaks. Long-form needs a spoken premise in the first seconds.")]
    if first.start > 1.0:
        out.append(Finding(0.0, "dead_air", f"The first meaningful word is at {first.start:.1f}s. "
                           f"Start on \"{first.text}\", or open on a moment from later in the video."))
    if ss:
        slow = [o for o in SLOW_OPENERS if o in _low(ss[0].text)]
        if slow:
            out.append(Finding(ss[0].start, "slow_opener", f"Opens with \"{slow[0]}\". Open on the premise "
                               "(\"For the last 100 days I cut my sets in half\") and greet later, if at all."))
    premise_by = TARGETS["premise_by"]
    opening = _window(words, 0, premise_by)
    if not (_has(opening, QUESTION_CUES) or "?" in opening or re.search(r"\d", opening)):
        out.append(Finding(0.0, "premise", f"The first {premise_by}s ask no question and name no number or stake. "
                           "Every studied opening did one: \"Would I lose muscle?\", \"$13M in 15 months. How?\", "
                           "\"last year 30 minutes, how much faster this year\"."))
    if not _has(_window(words, 0, TARGETS["loop_by"]), LOOP_CUES):
        out.append(Finding(None, "open_loop", f"No open loop in the first {TARGETS['loop_by']}s. Promise something "
                           "the viewer only gets later (\"a doctor blood tests everyone later in the video\").",
                           serious=False))

    # Chapters
    if chapters:
        starts = [t for t, _ in chapters if t > 0]
        if starts and starts[0] > TARGETS["intro_max"]:
            out.append(Finding(starts[0], "intro", f"The opening runs {clock(starts[0])} before the first chapter. "
                               f"Studied median {TARGETS['intro_median']}s; get to the first section sooner."))
        ends = [t for t, _ in chapters[1:]] + [duration]
        for (t, title), end in zip(chapters, ends):
            if t > 0 and end - t > TARGETS["chapter_max"]:
                out.append(Finding(t, "long_chapter", f"\"{title}\" runs {clock(end - t)}. Split it or add a turn "
                                   "inside it; studied chapters run about 2 minutes."))
            if t > 0:
                head = _window(words, t, t + 20)
                if head and not (_has(head, QUESTION_CUES) or "?" in head):
                    out.append(Finding(t, "chapter_open", f"\"{title}\" opens without a question or a turn. Restate "
                                       "what this part answers (\"So after 100 days, did it work?\").", serious=False))
    elif duration >= 480:
        out.append(Finding(None, "chapters", "No chapters. Add them with `stylebrain chapter TIME TITLE`; every "
                           "studied creator except the pure vlogs uses them.", serious=False))

    # Re-hooks through the middle
    qs = sorted({round(t, 1) for t, _ in question_moments(words)} | {round(t, 1) for t, _ in chapters if t > 0})
    edges = [0.0, *qs, duration]
    for a, b in zip(edges, edges[1:]):
        if b - a > TARGETS["dead_stretch"]:
            out.append(Finding(a, "dead_stretch", f"{clock(b - a)} from {clock(a)} with no new question, turn or "
                               "chapter. Add a re-hook: a question, a reveal, a setback or a change of scene."))
    for a, b, n in and_then_stretches(words):
        out.append(Finding(a, "and_then", f"{n} sentences in a row joined by \"and then\". What is at stake, or what "
                           "caused what?", serious=False))

    # Pace and silence
    talk = [w for w in words if w.text.strip()]
    if duration > 0 and len(talk) > 50:
        wpm = len(talk) / (duration / 60)
        lo, hi = TARGETS["words_per_minute"]
        if wpm < lo:
            out.append(Finding(None, "pace", f"{wpm:.0f} words a minute; the studied channels talk at {lo} to {hi}. "
                               "Tighten pauses, or fill quiet stretches with something happening.", serious=False))
    gaps = [(a.end, b.start - a.end) for a, b in zip(talk, talk[1:]) if b.start - a.end >= TARGETS["silence"]]
    for at, g in gaps[:8]:
        out.append(Finding(at, "silence", f"{g:.0f}s with nobody talking. Fine over a lift or a scene that moves; "
                           "otherwise tighten.", serious=False))
    if len(gaps) > 8:
        out.append(Finding(None, "silence", f"{len(gaps) - 8} more quiet stretches of {TARGETS['silence']:.0f}s or more.",
                           serious=False))
    if cuts is not None:
        edges = [0.0, *sorted(c for c in cuts if 0 < c < duration), duration]
        long = [(a, b - a) for a, b in zip(edges, edges[1:]) if b - a > 45]
        for a, g in long[:5]:
            out.append(Finding(a, "long_shot", f"{g:.0f}s with no change of picture. A b-roll cut, a punch-in or a "
                               "graphic would reset attention.", serious=False))

    # Payoff, pitch and ending
    if payoff_at is None:
        out.append(Finding(None, "payoff", "Not checked: when is the main question answered? Pass --payoff.",
                           serious=False))
    else:
        share = payoff_at / duration if duration else 0
        if share < TARGETS["payoff_from"]:
            out.append(Finding(payoff_at, "payoff", f"The main answer lands at {share:.0%} of the video. Viewers leave "
                               "once it is answered; hold it for the last 40%, or open a bigger question right after."))
        if duration - payoff_at > TARGETS["outro_max"]:
            out.append(Finding(payoff_at, "outro", f"{clock(duration - payoff_at)} after the payoff. End within "
                               f"{TARGETS['outro_max']}s of it, with one pitch and the next video."))
    if cta_at is None:
        cta_at = [s.start for s in ss if _has(s.text, CTA_CUES)]
    first_section = next((t for t, _ in chapters if t > 0), min(TARGETS["intro_max"], duration))
    for t in cta_at:
        if t < first_section:
            out.append(Finding(t, "early_pitch", "A pitch before the first section. Studied creators pitch after the "
                               "payoff (Jeff) or at a chapter break mid-video (Noah, Jun), never in the opening."))
    return sorted(out, key=lambda f: (f.at is None, f.at or 0.0))


# ------------------------------------------------------------------ outlines

OUTLINES = {
    "experiment": (
        "Try something for a set time and show the result (Jeff: \"I Cut The Number Of Sets I Do In Half\", "
        "\"How Much Muscle Did I Gain In 365 Days?\")",
        [("cold open", 0.03, "The premise and the question in one breath: what you did, for how long, and the doubt. "
          "Show the before. Promise the result at the end."),
         ("why", 0.20, "Why you tried it: what you always did, what the science or the gym says. End on the stake."),
         ("the plan", 0.17, "Exactly what you did, with numbers. Open with a question the viewer is already asking."),
         ("the hard part", 0.20, "The setback or the doubt mid-way. This is the turn; do not skip it."),
         ("the science", 0.15, "What others found, so the result means something beyond you."),
         ("results", 0.18, "Before and after, numbers on screen. Hold this until here."),
         ("verdict and next", 0.07, "Who should do it, one pitch, the next video.")]),
    "list": (
        "Ranked or numbered items (Jeff: \"7 Things That Helped My Shoulders Grow\"; CBum: \"This Chest Workout Won "
        "Me 6 Olympias\")",
        [("cold open", 0.05, "Why this list is worth 15 minutes: the result it got you, and the one item people get wrong."),
         ("items", 0.85, "One chapter per item, about 2 minutes each. Open each with the claim, prove it, show it, "
          "then tease the next. Save the strongest or most surprising item for last."),
         ("wrap and next", 0.10, "Recap in one line, one pitch, the next video.")]),
    "challenge": (
        "A goal with a date and a way to fail (Noah: \"I trained months for this... and then this happened\"; "
        "a meet, a PR attempt, a race)",
        [("flash-forward", 0.02, "A few seconds from the most tense moment later in the video, then cut away."),
         ("the goal", 0.06, "The number, the deadline, last time's result, why it matters."),
         ("build-up", 0.30, "Preparation, people, places. Every few minutes restate what could go wrong."),
         ("the turn", 0.20, "The setback (Noah's swim was cancelled at 67%). React honestly; this is the story."),
         ("the attempt", 0.30, "The lift, the race, the meet. Slow down here: more cuts, sound up, numbers on screen."),
         ("result and reflection", 0.12, "Did it work, what it meant, what is next.")]),
    "day": (
        "A day or a week in your life with one thread through it (Sam's daily bulk vlogs, Noah's training weeks)",
        [("cold open", 0.05, "Today's one stake: the weight on the scale, the PR attempt, the thing that might go wrong."),
         ("morning", 0.15, "Short. Only what leads to the stake."),
         ("main event", 0.45, "The session or the event, with talk-to-camera between sets about one idea."),
         ("side thread", 0.20, "A Q&A, a meal, a friend. Open it with a question."),
         ("result and tomorrow", 0.15, "Did the stake pay off; tease tomorrow.")]),
    "explainer": (
        "Teach one idea with proof (Jeff: \"Peptides Are Insane\"; Jun: \"How I Brainwashed Myself To Be A High Achiever\")",
        [("cold open", 0.07, "The surprising claim, a proof point and the question (\"$13M in 15 months. How?\")."),
         ("what it is", 0.10, "The plain-language version, so nobody is lost."),
         ("part 1", 0.25, "The first and easiest part, with an example from your own training."),
         ("part 2", 0.25, "Raise the stakes: the part people get wrong."),
         ("part 3", 0.23, "The part that changes how they train tomorrow."),
         ("so what", 0.10, "What to do next, one pitch, the next video.")]),
}


def outline(kind: str, minutes: float) -> list[dict]:
    """A chapter plan for a video of `minutes`: [{"title", "start", "seconds", "job"}]."""
    if kind not in OUTLINES:
        raise ValueError(f"unknown outline {kind!r}; use {', '.join(OUTLINES)}")
    total, t, out = minutes * 60, 0.0, []
    for title, share, job in OUTLINES[kind][1]:
        out.append({"title": title, "start": round(t), "seconds": round(share * total), "job": job})
        t += share * total
    return out


def outline_text(kind: str, minutes: float) -> str:
    lines = [f"{kind}: {OUTLINES[kind][0]}", f"Plan for {minutes:g} minutes:"]
    for s in outline(kind, minutes):
        lines.append(f"  {clock(s['start']):>6}  {s['title']:<22} {clock(s['seconds'])}  {s['job']}")
    lines.append("Each chapter opens with a question or a turn. The main answer lands in the last 40%.")
    return "\n".join(lines)
