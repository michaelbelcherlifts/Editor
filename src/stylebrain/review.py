"""Compare a cut with a saved style and say, with times, what differs.

Suggestions are observations against one reference, not rules. They are
ordered by where they fall in the video so they can be walked through.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .edl import EditList, format_time
from .style import pacing, speech
from .transcript import Word


@dataclass(frozen=True)
class Suggestion:
    at: float | None  # seconds on the timeline; None for whole-video notes
    kind: str         # opening, pace, long_shot, pause, picture, sound
    text: str

    def line(self, fps: float = 30.0) -> str:
        where = "overall" if self.at is None else format_time(round(self.at * fps), fps)
        return f"{where:>10}  [{self.kind}] {self.text}"


def profile_of_edit(edit: EditList, words: list[Word] | None = None) -> dict:
    """The measurable parts of the current edit, without rendering it.

    `words` are timeline words (see transcript.on_timeline).
    """
    duration = edit.duration / edit.fps
    cuts = [round(start / edit.fps, 3) for start, _ in edit.pieces()][1:]
    out = {"frame": {"seconds": round(duration, 2)}, "cuts": cuts, "pacing": pacing(cuts, duration)}
    if words:
        out["speech"] = speech(words, duration)
        out["words"] = [[w.text, w.start, w.end] for w in words]
    return out


def compare(mine: dict, target: dict, limit: int = 8) -> list[Suggestion]:
    """Suggestions for `mine` measured against the style `target`."""
    out: list[Suggestion] = []
    name = target.get("name", "the reference")
    mp, tp = mine["pacing"], target["pacing"]
    duration = mine["frame"]["seconds"]

    # Opening
    ms, ts = mine.get("speech"), target.get("speech")
    if ms and ts and ms["first_word_at"] > ts["first_word_at"] + 0.3:
        out.append(Suggestion(0.0, "opening",
                              f"You start talking at {ms['first_word_at']:g}s; {name} starts at "
                              f"{ts['first_word_at']:g}s. Trim {ms['first_word_at'] - ts['first_word_at']:.1f}s off the top."))
    mh, th = mp["hook"], tp["hook"]
    if th["cuts"] >= 2 and mh["cuts"] / max(mh["seconds"], 0.1) < th["cuts"] / max(th["seconds"], 0.1) * 0.6:
        out.append(Suggestion(0.0, "opening",
                              f"Your first {mh['seconds']:g}s has {mh['cuts']} cuts; {name} has {th['cuts']} "
                              f"in its first {th['seconds']:g}s. The opening could change picture more often."))
    if th["first_cut"] is not None and (mh["first_cut"] is None or mh["first_cut"] > th["first_cut"] * 2 + 1):
        mine_first = "never" if mh["first_cut"] is None else f"at {mh['first_cut']:g}s"
        out.append(Suggestion(0.0, "opening",
                              f"Your first change of picture is {mine_first}; {name}'s is at {th['first_cut']:g}s."))

    # Pace
    if tp["cuts_per_minute"] > 0:
        ratio = mp["cuts_per_minute"] / tp["cuts_per_minute"]
        if ratio < 0.7 or ratio > 1.4:
            word = "slower" if ratio < 1 else "faster"
            out.append(Suggestion(None, "pace",
                                  f"You cut {mp['cuts_per_minute']:g} times a minute; {name} cuts "
                                  f"{tp['cuts_per_minute']:g}. Yours is {word} overall."))

    # Long shots
    limit_len = max(tp["long_shot"] * 1.5, tp["median_shot"] * 3, 2.0)
    edges = [0.0, *mine["cuts"], duration]
    long = sorted(((b - a, a, b) for a, b in zip(edges, edges[1:]) if b - a > limit_len), reverse=True)[:limit]
    for length, a, b in long:
        out.append(Suggestion(a, "long_shot",
                              f"This shot runs {length:.1f}s. {name} rarely holds past {tp['long_shot']:g}s. "
                              "A punch-in, graphic or b-roll would break it up."))

    # Pauses
    if ms and ts:
        if ms["words_per_minute"] < ts["words_per_minute"] * 0.85:
            out.append(Suggestion(None, "pace",
                                  f"You speak {ms['words_per_minute']} words a minute across the cut; {name} runs "
                                  f"{ts['words_per_minute']}. Tightening pauses would close the gap."))
        gap_limit = max(ts["long_gap"] * 2, 0.5)
        ws = mine.get("words", [])
        gaps = sorted(((b[1] - a[2], a[2]) for a, b in zip(ws, ws[1:]) if b[1] - a[2] > gap_limit), reverse=True)
        for gap, at in gaps[:limit]:
            out.append(Suggestion(at, "pause", f"A {gap:.1f}s pause. {name}'s long pauses are about {ts['long_gap']:g}s."))

    # Picture and sound, when both were measured from video files
    mc, tc = mine.get("colour"), target.get("colour")
    if mc and tc:
        notes = []
        for key, word, tol in (("brightness", ("darker", "brighter"), 0.07), ("contrast", ("flatter", "more contrasty"), 0.1),
                               ("saturation", ("less colourful", "more colourful"), 0.08), ("warmth", ("cooler", "warmer"), 0.04)):
            d = mc[key] - tc[key]
            if abs(d) > tol:
                notes.append(word[d > 0])
        if notes:
            out.append(Suggestion(None, "picture", f"Against {name} your picture is {', '.join(notes)}. "
                                  "A look made with look-make would bring it closer."))
    ma, ta = mine.get("audio"), target.get("audio")
    if ma and ta and ma.get("loudness_lufs") is not None and ta.get("loudness_lufs") is not None:
        d = ma["loudness_lufs"] - ta["loudness_lufs"]
        if abs(d) > 2:
            out.append(Suggestion(None, "sound", f"Your sound is {abs(d):.0f} LU {'quieter' if d < 0 else 'louder'} "
                                  f"than {name} ({ma['loudness_lufs']:g} against {ta['loudness_lufs']:g} LUFS)."))
        if ma["quiet_share"] > ta["quiet_share"] + 0.1:
            out.append(Suggestion(None, "sound", f"{ma['quiet_share'] * 100:.0f}% of your cut is near-silent; "
                                  f"{name} is {ta['quiet_share'] * 100:.0f}%. Music or tighter pauses would fill it."))

    return sorted(out, key=lambda s: (s.at is not None, s.at or 0.0))


def to_json(suggestions: list[Suggestion]) -> list[dict]:
    return [asdict(s) for s in suggestions]


