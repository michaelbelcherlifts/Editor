"""Word-level transcripts: find what was said, and where the pauses are.

Times are seconds in the source clip. Use EditList.timeline_ranges_for_source
to turn a source range into where it currently sits on the timeline.
"""

from __future__ import annotations

import html
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


@dataclass(frozen=True)
class Take:
    """A stretch that looks like a failed attempt, to cut so the good attempt remains."""

    start: float
    end: float
    kind: str        # repeat, restart, said-again, cue or stutter
    sure: bool       # safe to cut without asking; the rest are for a person to judge
    why: str


CUES_SURE = ("start over", "scratch that", "take two", "let me try that again", "let me redo that",
             "let me say that again", "let me do that again", "i messed that up", "let me restart")
CUES_MAYBE = ("one more time", "try that again", "say that again", "sorry", "hold on", "wait")
FILLER_DOUBLES = {"i", "the", "a", "and", "so", "but", "we", "you", "it", "to", "my", "this", "is", "i'm", "it's",
                  "that's", "if", "when", "because", "like", "um", "uh", "that", "in", "of", "for", "with"}


def phrases(words: list[Word], gap: float = 0.45) -> list[tuple[int, int]]:
    """Index ranges [i, j) of words said in one breath: split at pauses and at sentence ends."""
    out, i = [], 0
    for n in range(1, len(words) + 1):
        if n == len(words) or words[n].start - words[n - 1].end >= gap \
                or words[n - 1].text.rstrip("\"')").endswith((".", "!", "?")):
            if n > i:
                out.append((i, n))
            i = n
    return out


def _exact_repeats(words: list[Word], norm: list[str], min_words: int, window: float,
                   ph: list[tuple[int, int]], punctuated: bool) -> list[Take]:
    """The same run of words twice. Sure only when it looks like starting the line again."""
    where = {}
    for i0, i1 in ph:
        for k in range(i0, i1):
            where[k] = (i0, i1)

    def looks_like_a_redo(i: int, hit: int) -> bool:
        a0, a1 = where[i]
        b0, b1 = where[hit]
        if (a0, a1) == (b0, b1):
            return i == a0                    # no pause between: a redo only if the line itself starts twice
        if hit - b0 > 1:
            return False                      # a redo starts the line again; this repeat is mid-line
        a = [x for x in norm[a0:a1] if x]
        b = [x for x in norm[b0:b1] if x]
        last = words[a1 - 1].text.rstrip("\"')")
        finished = last.endswith((".", "!", "?")) if punctuated else len(a) > 5
        same = len(set(a) & set(b)) / max(len(set(a)), 1) >= 0.75
        return not finished or same           # a finished line said in other words is a device, not a slip

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
            sure = looks_like_a_redo(i, hit)
            out.append(Take(words[i].start, words[hit].start, "repeat", sure,
                            f"the same {min_words} words come again"
                            + ("" if sure else ", but mid-line or in a finished sentence, so it may be on purpose")))
            i = hit
    return out


def find_takes(words: list[Word], min_words: int = 4, window: float = 30.0) -> list[Take]:
    """Every stretch that looks like a failed attempt, surest kinds first where they overlap.

    repeat: the same `min_words` words in a row come again within `window` seconds.
    restart: a phrase is dropped unfinished and the next one starts with the same words.
    said-again: a whole phrase is said again in nearly the same words.
    cue: he says so ("let me start over"); the flubbed phrase and the cue both go.
    stutter: a small word doubled ("I I think").
    Deliberate repetition can look the same, so only `sure` ones are safe to cut unasked.
    """
    norm = [_norm(w.text) for w in words]
    ph = phrases(words)
    punctuated = any(w.text.rstrip("\"')").endswith((".", "!", "?", ",")) for w in words)
    found = _exact_repeats(words, norm, min_words, window, ph, punctuated)

    for n, (i0, i1) in enumerate(ph):
        a = [x for x in norm[i0:i1] if x]
        if not a:
            continue
        last = words[i1 - 1].text.rstrip("\"')")
        finished = last.endswith((".", "!", "?")) if punctuated else len(a) > 5
        for j0, j1 in ph[n + 1:n + 4]:
            if words[j0].start - words[i0].start > min(window, 20.0):
                break
            b = [x for x in norm[j0:j1] if x]
            prefix = 0
            while prefix < min(len(a), len(b)) and a[prefix] == b[prefix]:
                prefix += 1
            overlap = len(set(a) & set(b)) / len(set(a))
            if prefix >= 2 and not finished and len(b) >= len(a) - 1:
                found.append(Take(words[i0].start, words[j0].start, "restart", prefix >= 3 or len(a) <= 4,
                                  f"breaks off, then starts again with \"{' '.join(a[:prefix])}\""))
                break
            if len(a) >= 4 and prefix >= 1 and overlap >= 0.75:
                found.append(Take(words[i0].start, words[j0].start, "said-again", overlap >= 0.9 and prefix >= 2,
                                  "nearly the same line comes again"))
                break

    for n, (i0, i1) in enumerate(ph):
        said = " ".join(x for x in norm[i0:i1] if x)
        sure = any(c in said for c in CUES_SURE)
        maybe = (i1 - i0) <= 6 and any(re.search(rf"\b{re.escape(c)}\b", said) for c in CUES_MAYBE)
        if not (sure or maybe):
            continue
        start = words[ph[n - 1][0]].start if n else words[i0].start
        end = words[i1].start if i1 < len(words) else words[i1 - 1].end
        found.append(Take(start, end, "cue", sure, f"he says \"{said[:40]}\""))

    for i in range(len(words) - 1):
        if norm[i] and norm[i] == norm[i + 1] and norm[i] in FILLER_DOUBLES \
                and words[i + 1].start - words[i].end < 0.6:
            found.append(Take(words[i].start, words[i + 1].start, "stutter", False, f"\"{norm[i]}\" twice"))

    # Where two overlap keep the sure one, then the longer one.
    out: list[Take] = []
    for t in sorted(found, key=lambda t: (not t.sure, -(t.end - t.start), t.start)):
        if t.end - t.start > 0.01 and not any(t.start < o.end and o.start < t.end for o in out):
            out.append(t)
    return sorted(out, key=lambda t: t.start)


def find_retakes(words: list[Word], min_words: int = 4, window: float = 30.0) -> list[tuple[float, float]]:
    """The failed attempts that are safe to cut unasked, as (start, end) in seconds. See `find_takes`."""
    return [(t.start, t.end) for t in find_takes(words, min_words, window) if t.sure]


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


def caption_lines(words: list[Word], max_chars: int = 32, max_gap: float = 0.7,
                  breaks: list[float] = ()) -> list[list[Word]]:
    """Group words into caption lines by length and pauses. A line never runs across a time in
    `breaks` (a cut to another part of the recording, such as a cold open)."""
    lines: list[list[Word]] = []
    for w in words:
        cur = lines[-1] if lines else None
        crosses = cur and any(cur[-1].start < b <= w.start + 0.001 for b in breaks)
        if (cur and not crosses and len(" ".join(x.text for x in cur)) + 1 + len(w.text) <= max_chars
                and w.start - cur[-1].end <= max_gap):
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

    YouTube's automatic captions (the ".en-orig.vtt" kind) also carry a time
    for every word; when those are there they are used, which is close enough
    to choose sentences and pauses from.
    """
    if _INLINE.search(text):
        return _from_timed_vtt(text)
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


_INLINE = re.compile(r"<(\d+):(\d\d):(\d\d)\.(\d{3})>")
_WORD_MAX = 1.0  # a word timed only by when the next one starts is held at most this long


def _secs(g) -> float:
    return int(g[0]) * 3600 + int(g[1]) * 60 + int(g[2]) + int(g[3]) / 1000


def _from_timed_vtt(text: str) -> list[Word]:
    """Words from a VTT whose cues carry a time per word: `first<00:00:04.200><c> next</c>...`.

    Each cue repeats the line before and adds one new line, the last one; a new line of one
    word has no inline times and starts with its cue. Cues of a few milliseconds only repeat.
    Sound labels such as [music] are dropped.
    """
    starts: list[tuple[float, str]] = []
    ends: list[float] = []   # the end of the cue each word came from
    cues: list[tuple[float, float, list[str]]] = []
    for raw in text.splitlines():
        m = _CUE.search(raw)
        if m:
            g = m.groups()
            cues.append((_secs(g[:4]), _secs(g[4:]), []))
        elif cues and raw.strip():
            cues[-1][2].append(raw.strip())
    last = None
    for cue_start, cue_end, lines in cues:
        if not lines or cue_end - cue_start < 0.02:
            continue
        line = html.unescape(lines[-1])
        if line == last:
            continue
        last = line
        at = cue_start
        for piece in re.split(r"(<\d+:\d\d:\d\d\.\d{3}>)", line):
            tag = _INLINE.fullmatch(piece)
            if tag:
                at = _secs(tag.groups())
                continue
            for tok in re.sub(r"</?c[^>]*>", "", piece).split():
                if not re.fullmatch(r"\[[^\]]*\]|>>|-", tok):
                    starts.append((at, tok))
                    ends.append(cue_end)
    words = []
    for k, (t, tok) in enumerate(starts):
        nxt = starts[k + 1][0] if k + 1 < len(starts) else ends[k]
        end = min(max(nxt, t + 0.05), t + _WORD_MAX)
        words.append(Word(tok, round(t, 3), round(end, 3)))
    return words


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
