"""Word-level transcripts: find what was said, and where the pauses are.

Times are seconds in the source clip. Use EditList.timeline_ranges_for_source
to turn a source range into where it currently sits on the timeline.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float


def load_words(path: str | Path) -> list[Word]:
    """Read word timings from JSON.

    Accepts a flat list of {"word"|"text", "start", "end"}, or the Whisper
    shape {"segments": [{"words": [...]}]}. Words without timings are skipped.
    """
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict):
        if "words" in data:
            raw = data["words"]
        else:
            raw = [w for seg in data.get("segments", []) for w in seg.get("words", [])]
    else:
        raw = data
    words = []
    for w in raw:
        text = w.get("word", w.get("text", "")).strip()
        if text and w.get("start") is not None and w.get("end") is not None:
            words.append(Word(text, float(w["start"]), float(w["end"])))
    return sorted(words, key=lambda w: w.start)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9']+", "", text.lower())


def find_phrase(words: list[Word], phrase: str) -> list[tuple[float, float]]:
    """Every place the phrase is spoken, as (start, end) seconds.

    Matching ignores case and punctuation.
    """
    target = [t for t in (_norm(p) for p in phrase.split()) if t]
    spoken = [(i, _norm(w.text)) for i, w in enumerate(words)]
    spoken = [(i, t) for i, t in spoken if t]
    hits = []
    if not target:
        return hits
    for k in range(len(spoken) - len(target) + 1):
        if [t for _, t in spoken[k : k + len(target)]] == target:
            first, last = spoken[k][0], spoken[k + len(target) - 1][0]
            hits.append((words[first].start, words[last].end))
    return hits


def find_silences(
    words: list[Word], min_gap: float = 0.6, clip_length: float | None = None
) -> list[tuple[float, float]]:
    """Stretches with no speech at least min_gap seconds long.

    Includes the lead-in before the first word, and the tail after the last
    word when clip_length is given.
    """
    edges = [0.0]
    for w in words:
        edges += [w.start, w.end]
    if clip_length is not None:
        edges.append(clip_length)
    else:
        edges.append(edges[-1])
    gaps = []
    for lo, hi in zip(edges[0::2], edges[1::2]):
        if hi - lo >= min_gap:
            gaps.append((lo, hi))
    return gaps


def tighten_ranges(
    words: list[Word], min_gap: float = 0.6, pad: float = 0.12, clip_length: float | None = None
) -> list[tuple[float, float]]:
    """The parts of each silence to cut, leaving `pad` seconds of air around speech."""
    cuts = []
    for lo, hi in find_silences(words, min_gap, clip_length):
        lo2 = lo + pad if lo > 0 else lo
        hi2 = hi - pad if clip_length is None or hi < clip_length else hi
        if hi2 - lo2 > 0.001:
            cuts.append((lo2, hi2))
    return cuts
