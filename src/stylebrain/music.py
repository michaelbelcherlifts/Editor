"""Music under an edit: find the beats of a track, move cuts onto them, and make the bed.

Beat finding is done here with numpy (no extra tools): how the sound's energy
jumps from moment to moment gives a pulse, the pulse gives a tempo, and the
beats are the evenly spaced moments that best line up with the jumps. It is
good on music with a clear pulse and unreliable on ambient or rubato tracks;
`analyse` reports how clear the pulse was so that can be said out loud.

The bed is the track cut to the edit's length, set to its level, faded at the
end and lowered while someone is speaking.
"""

from __future__ import annotations

import json
from pathlib import Path

from .edl import EditError, EditList
from .media import run
from .transcript import Word

RATE, HOP, WINDOW = 22050, 512, 1024
STEP = HOP / RATE                         # seconds between envelope points


def envelope(file: str | Path, limit: float = 600.0):
    """How strongly the sound jumps at each moment (one value every STEP seconds). Needs numpy."""
    import numpy as np

    raw = run(["ffmpeg", "-v", "error", "-t", f"{limit}", "-i", str(file), "-vn", "-ac", "1", "-ar", str(RATE),
               "-f", "f32le", "-"]).stdout
    x = np.frombuffer(raw, np.float32)
    if len(x) < WINDOW * 4:
        raise EditError(f"{Path(file).name} is too short to find a beat in")
    n = 1 + (len(x) - WINDOW) // HOP
    idx = np.arange(WINDOW)[None, :] + HOP * np.arange(n)[:, None]
    mag = np.abs(np.fft.rfft(x[idx] * np.hanning(WINDOW), axis=1))
    flux = np.maximum(np.diff(np.log1p(100 * mag), axis=0), 0)
    low = int(250 / (RATE / WINDOW))                                  # the kick and bass carry the beat
    env = flux.sum(axis=1) / flux.shape[1] + 3 * flux[:, :low].sum(axis=1) / low
    env = env - np.convolve(env, np.ones(43) / 43, mode="same")      # take out the slow swell
    return np.maximum(env, 0)


def tempo(env) -> tuple[float, float]:
    """Beats a minute, and how clear the pulse is (0 to 1)."""
    import numpy as np

    e = env - env.mean()
    lo, hi = int(round(60 / 200 / STEP)), int(round(60 / 55 / STEP))
    if len(e) < hi * 2:
        raise EditError("the track is too short to find a tempo")
    ac = np.array([float(np.dot(e[:-lag], e[lag:])) for lag in range(lo, hi + 1)])
    ac /= float(np.dot(e, e)) or 1.0
    bpm = 60 / (np.arange(lo, hi + 1) * STEP)
    prior = np.exp(-0.5 * (np.log2(bpm / 120) / 0.9) ** 2)            # most music sits near 120; breaks octave ties
    k = int(np.argmax(ac * prior))
    lag = lo + k
    if 0 < k < len(ac) - 1:                                           # finer than one envelope step
        a, b, c = ac[k - 1], ac[k], ac[k + 1]
        if a - 2 * b + c != 0:
            lag += 0.5 * (a - c) / (a - 2 * b + c)
    return float(60 / (lag * STEP)), float(max(0.0, min(1.0, ac[k])))


def beat_times(env, bpm: float) -> list[float]:
    """Evenly paced beats that line up best with the jumps in the sound, in seconds."""
    import numpy as np

    period = 60 / bpm / STEP
    n = len(env)
    norm = env / (env.std() or 1.0)
    score = norm.copy()
    back = np.full(n, -1)
    lo, hi = int(round(period / 2)), int(round(period * 2))
    gaps = np.arange(lo, hi + 1)
    penalty = -100.0 * np.log(gaps / period) ** 2                     # stray far from the tempo and it costs
    for t in range(lo, n):
        prev = t - gaps
        ok = prev >= 0
        if not ok.any():
            continue
        cand = score[prev[ok]] + penalty[ok]
        best = int(np.argmax(cand))
        if cand[best] > 0:
            score[t] = norm[t] + cand[best]
            back[t] = prev[ok][best]
    t = int(np.argmax(score[-int(period * 2):]) + n - int(period * 2)) if n > period * 2 else int(np.argmax(score))
    beats = []
    while t >= 0:
        beats.append(t)
        t = int(back[t])
    times = np.array([(b + 1) * STEP + WINDOW / 2 / RATE for b in reversed(beats)])
    # The envelope only has a point every 23 ms. A straight line through each beat's neighbours
    # takes that jitter out while still following a tempo that drifts.
    k = np.arange(len(times))
    smooth = times.copy()
    for i in range(len(times)):
        lo, hi = max(0, i - 4), min(len(times), i + 5)
        if hi - lo >= 4:
            slope, start = np.polyfit(k[lo:hi], times[lo:hi], 1)
            smooth[i] = slope * i + start
    return [round(float(t), 3) for t in smooth]


def analyse(file: str | Path, cache: str | Path | None = ".stylebrain/beats") -> dict:
    """Tempo and beat times of a track: {"bpm", "clear", "beats"}. Saved so a track is only read once."""
    file = Path(file)
    if not file.exists():
        raise EditError(f"cannot find {file}")
    saved = Path(cache) / f"{file.stem}.{file.stat().st_size}.json" if cache else None
    if saved and saved.exists():
        return json.loads(saved.read_text())
    env = envelope(file)
    bpm, clear = tempo(env)
    beats = beat_times(env, bpm)
    if len(beats) > 8:                    # the beats themselves give a finer tempo than the first estimate
        bpm = 60 * (len(beats) - 1) / (beats[-1] - beats[0])
    out = {"file": str(file), "bpm": round(bpm, 1), "clear": round(clear, 2), "beats": beats}
    if saved:
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_text(json.dumps(out))
    return out


def timeline_beats(edit: EditList, beats: list[float] | None = None) -> list[float]:
    """The beats as seconds on the timeline, given where in the song the edit starts."""
    if edit.music is None:
        raise EditError("there is no music on this edit; add it with `music-add FILE`")
    beats = analyse(edit.music.source)["beats"] if beats is None else beats
    total = edit.duration / edit.fps
    return [round(b - edit.music.start, 3) for b in beats if 0 <= b - edit.music.start < total]


def snap_cuts(edit: EditList, beats: list[float], max_trim: float = 0.3, words: list[Word] | None = None,
              every: int = 1) -> tuple[EditList, list[str]]:
    """Move cuts back onto the beat by trimming the end of the clip before each cut.

    A cut is moved only when a beat falls up to `max_trim` seconds before it,
    and never into a spoken word (`words` are timeline times). Later material
    moves earlier by what was trimmed, so each cut is judged where it lands.
    `every`: use every Nth beat (2 for half-time, 4 for the bar).
    """
    fps = edit.fps
    grid = beats[::max(every, 1)]
    if not grid:
        raise EditError("no beats fall inside the edit")
    lines, shift, n = [], 0.0, 0
    words = sorted(words or [], key=lambda w: w.start)
    starts = [start for start, _ in edit.pieces()][1:]
    for original in starts:
        cut = original / fps - shift                                 # where this cut sits now
        frame = round(cut * fps)
        before = [b for b in grid if b <= cut + 0.5 / fps]
        if not before:
            lines.append(f"{cut:7.2f}s  left alone: no beat before it")
            continue
        beat = before[-1]
        target = round(beat * fps)
        trim = frame - target
        if trim <= 0:
            lines.append(f"{cut:7.2f}s  already on the beat")
            continue
        if trim / fps > max_trim:
            lines.append(f"{cut:7.2f}s  left alone: the beat is {trim / fps:.2f}s away")
            continue
        prev_start = max(s for s, _ in edit.pieces() if s < frame)
        if target <= prev_start:
            lines.append(f"{cut:7.2f}s  left alone: the clip before it is shorter than the move")
            continue
        # Words are in the original timeline's times; this stretch of the original is what would go.
        lo, hi = target / fps + shift, frame / fps + shift
        if any(w.start < hi - 0.02 and w.end > lo + 0.02 for w in words):
            lines.append(f"{cut:7.2f}s  left alone: moving it would clip a word")
            continue
        edit = edit.remove_range(target, frame)
        shift += trim / fps
        n += 1
        lines.append(f"{cut:7.2f}s  moved to the beat at {beat:.2f}s (trimmed {trim / fps:.2f}s)")
    lines.append(f"{n} of {len(starts)} cuts now land on the beat")
    return edit, lines


def bed(edit: EditList, out: str | Path, voice: str | Path | None = None, fade: float = 1.0) -> Path:
    """The music cut to the edit: from its start point, at its level, faded out, lowered under the voice."""
    m = edit.music
    if m is None:
        raise EditError("there is no music on this edit")
    if not Path(m.source).exists():
        raise EditError(f"cannot find {m.source}")
    total = edit.duration / edit.fps
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{m.start:.3f}", "-t", f"{total + 0.5:.3f}", "-i", m.source]
    chain = (f"[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume={m.gain_db:.1f}dB,"
             f"afade=t=out:st={max(total - fade, 0):.3f}:d={min(fade, total):.3f},apad=whole_dur={total:.4f}")
    if voice and m.duck:
        cmd += ["-i", str(voice)]
        # The voice is padded without end and the result padded again: whichever input runs out
        # first, the bed still comes out at the full length of the edit.
        chain += ("[bed];[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,apad[key];"
                  f"[bed][key]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=400,apad=whole_dur={total:.4f}")
    run(cmd + ["-filter_complex", chain + "[o]", "-map", "[o]", "-t", f"{total:.4f}", "-ar", "48000", str(out)])
    return out
