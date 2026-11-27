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
    A .srt or .vtt subtitle file is also accepted, with approximate timings.
    """
    if str(path).lower().endswith((".srt", ".vtt")):
        return from_subtitles(Path(path).read_text())
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


def find_retakes(words: list[Word], min_words: int = 4, window: float = 30.0) -> list[tuple[float, float]]:
    """Likely false starts: a run of words said again shortly after.

    When the same `min_words` words in a row come up again within `window`
    seconds, the first attempt (from its start to where the repeat starts) is
    returned as a stretch to cut. Deliberate repetition looks the same, so
    these are candidates to review, not certainties.
    """
    norm = [_norm(w.text) for w in words]
    out, i, n = [], 0, len(words)
    while i + min_words <= n:
        key = norm[i:i + min_words]
        hit = None
        if all(key):
            j = i + 1
            while j + min_words <= n and words[j].start - words[i].start <= window:
                if norm[j:j + min_words] == key:
                    hit = j
                    break
                j += 1
        if hit is None:
            i += 1
        else:
            out.append((words[i].start, words[hit].start))
            i = hit
    return out


def on_timeline(words: list[Word], spans) -> list[Word]:
    """Words that survive in the edit, with timeline times.

    `spans(start, end)` maps a source range in seconds to the list of timeline
    ranges in seconds where it now sits (empty when it was cut).
    """
    out = []
    for w in words:
        for lo, hi in spans(w.start, w.end):
            out.append(Word(w.text, lo, hi))
    return sorted(out, key=lambda w: w.start)


def _stamp(t: float, sep: str = ",") -> str:
    ms = round(t * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}{sep}{ms % 1000:03d}"


def caption_lines(words: list[Word], max_chars: int = 32, max_gap: float = 0.7) -> list[list[Word]]:
    """Group words into caption lines by length and pauses."""
    lines: list[list[Word]] = []
    for w in words:
        cur = lines[-1] if lines else None
        if cur and len(" ".join(x.text for x in cur)) + 1 + len(w.text) <= max_chars and w.start - cur[-1].end <= max_gap:
            cur.append(w)
        else:
            lines.append([w])
    return lines


def to_srt(words: list[Word], max_chars: int = 32) -> str:
    """Subtitles (SRT text) from word timings."""
    blocks = []
    for n, line in enumerate(caption_lines(words, max_chars), 1):
        blocks.append(f"{n}\n{_stamp(line[0].start)} --> {_stamp(max(line[-1].end, line[0].start + 0.2))}\n"
                      + " ".join(w.text for w in line) + "\n")
    return "\n".join(blocks)


_CUE = re.compile(r"(\d+):(\d\d):(\d\d)[.,](\d{3})\s*-->\s*(\d+):(\d\d):(\d\d)[.,](\d{3})")


def from_subtitles(text: str) -> list[Word]:
    """Approximate word timings from SRT or VTT subtitles.

    Each cue's words are spread evenly across the cue. YouTube's automatic
    captions repeat the previous line in each cue; repeated lines are dropped.
    Good enough for measuring speech pace, not for frame-accurate cuts.
    """
    words: list[Word] = []
    seen: list[str] = []
    cue = None
    lines: list[str] = []

    def flush():
        if cue is None:
            return
        fresh = []
        for ln in lines:
            ln = re.sub(r"<[^>]+>", "", ln).strip()
            if ln and ln not in seen[-3:]:
                fresh.append(ln)
                seen.append(ln)
        toks = " ".join(fresh).split()
        if toks and cue[1] > cue[0]:
            step = (cue[1] - cue[0]) / len(toks)
            for k, t in enumerate(toks):
                words.append(Word(t, round(cue[0] + k * step, 3), round(cue[0] + (k + 1) * step, 3)))

    for raw in text.splitlines():
        m = _CUE.search(raw)
        if m:
            flush()
            g = [int(x) for x in m.groups()]
            cue = (g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000, g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000)
            lines = []
        elif cue is not None and raw.strip() and not raw.strip().isdigit():
            lines.append(raw)
    flush()
    return sorted(words, key=lambda w: w.start)


_PHANTOMS = {"thanksforwatching", "thankyouforwatching", "thankyou", "thanks", "you", "pleasesubscribe",
             "subscribe", "bye", "music", "thankyouverymuch", "seeyounexttime"}


def drop_phantom_speech(words: list[Word]) -> list[Word]:
    """Remove the stock phrases speech-to-text tools invent over music.

    When the whole transcript is one of a few well-known phantom lines (such
    as "Thanks for watching!"), the clip has no speech: return no words.
    """
    if len(words) <= 6 and _norm("".join(w.text for w in words)) in _PHANTOMS:
        return []
    return words
