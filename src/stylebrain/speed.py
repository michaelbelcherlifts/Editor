"""Slow motion and speed ramps on part of the timeline.

Resolve's scripting API cannot set a clip's speed, so a slowed stretch is baked:
ffmpeg writes that part of the source as a new file at the edit's frame rate,
and the edit list points at the new file instead. Everything else (cutting,
moving, export, the Resolve build, undo) then treats it as an ordinary clip.

A ramp eases from normal speed into the slow speed and back out again, the
way flex and pose edits slow into a pose and speed back up for the next cut.
The speed changes smoothly through the ramp, not in steps.

Real slow motion needs footage filmed at a higher frame rate. At half speed,
60 fps footage gives a full 30 frames a second of real pictures; 30 fps footage
has to repeat or blend frames. `smooth=True` makes the in-between frames by
motion interpolation, which is slower to render and can smear fast movement.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import replace
from pathlib import Path

from .edl import EditError, EditList, Segment, _join
from .media import has_audio, info, probe, run

_VIDEO_OUT = ["-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p"]


def out_seconds(length: float, speed: float, ramp: float = 0.0) -> float:
    """How long `length` seconds of source play for at `speed`, with `ramp` seconds easing in and out."""
    _check(length, speed, ramp)
    if ramp <= 0 or speed == 1:
        return length / speed
    hold = length - 2 * ramp
    return 2 * _ramp_time(ramp, ramp, speed) + hold / speed


def _ramp_time(u: float, r: float, s: float) -> float:
    """Output seconds after u source seconds of a ramp whose speed goes linearly from 1 to s over r seconds."""
    return r / (s - 1) * math.log(1 + (s - 1) * u / r)


def _check(length: float, speed: float, ramp: float) -> None:
    if not 0.1 <= speed <= 4:
        raise EditError("speed runs from 0.1 (ten times slower) to 4 (four times faster); 0.5 is half speed")
    if ramp < 0 or 2 * ramp > length:
        raise EditError("the ramp in and out together must fit inside the stretch being slowed")


def pts_expr(length: float, speed: float, ramp: float) -> str:
    """An ffmpeg setpts expression that maps source time T to output time with the ramp."""
    s, r = speed, ramp
    if r <= 0 or s == 1:
        return f"PTS/{s}"
    k = r / (s - 1)
    a = f"{k}*log(1+{s - 1}*T/{r})"                                   # easing in
    t_in = _ramp_time(r, r, s)
    b = f"{t_in}+(T-{r})/{s}"                                          # holding slow
    t_hold = t_in + (length - 2 * r) / s
    # easing out: speed goes from s back to 1, the mirror of easing in
    u = f"(T-{length - r})"
    c = f"{t_hold}+{k}*(log({s})-log({s}-{s - 1}*{u}/{r}))"
    return f"(if(lt(T,{r}),{a},if(lt(T,{length - r}),{b},{c})))/TB"


def bake(src: str, start: float, end: float, out: str | Path, fps: float, speed: float, ramp: float = 0.0,
         smooth: bool = False, sound: bool = False) -> Path:
    """Write source seconds [start, end) played at `speed` (with an optional ramp) as a new clip."""
    length = end - start
    _check(length, speed, ramp)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    total = out_seconds(length, speed, ramp)
    rate = f"minterpolate=fps={fps:g}:mi_mode=mci:mc_mode=aobmc:vsbmc=1" if smooth else f"fps={fps:g}"
    vf = f"trim=duration={length:.6f},setpts=PTS-STARTPTS,setpts='{pts_expr(length, speed, ramp)}',{rate}"
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.6f}", "-t", f"{length + 0.5:.6f}", "-i", src, "-vf", vf]
    if sound and ramp == 0 and has_audio(src):
        cmd += ["-af", f"atrim=duration={length:.6f},asetpts=PTS-STARTPTS,{_atempo(speed)}", "-c:a", "aac"]
    else:
        cmd += ["-an"]
    run(cmd + ["-t", f"{total:.6f}", *_VIDEO_OUT, str(out)])
    return out


def _atempo(factor: float) -> str:
    steps, f = [], factor
    while f > 2.0:
        steps.append("atempo=2.0"); f /= 2.0
    while f < 0.5:
        steps.append("atempo=0.5"); f /= 0.5
    steps.append(f"atempo={f:.6f}")
    return ",".join(steps)


def apply(edit: EditList, t0: int, t1: int, speed: float, folder: str | Path, ramp: float = 0.0,
          smooth: bool = False, sound: bool = False, baker=bake) -> tuple[EditList, list[str]]:
    """Play timeline frames [t0, t1) at `speed`. Returns the new edit and lines to report.

    Each main-track clip inside the range is baked on its own, so a range that
    spans a cut keeps the cut. `ramp` is in source seconds and applies to each
    baked clip. Overlays and sounds that start inside a slowed clip stay on the
    same moment of it.
    """
    t0, t1 = edit._check_range(t0, t1)
    cut = edit.split_at(t0).split_at(t1)
    fps = edit.fps
    lines, order = [], []
    for start, seg in cut.pieces():
        if not t0 <= start < t1:
            order.append((start, seg, seg.duration))
            continue
        a, b = seg.src_in / fps, seg.src_out / fps
        r = min(ramp, (b - a) / 2)
        key = hashlib.sha1(f"{Path(seg.source).resolve()}|{a:.4f}|{b:.4f}|{speed}|{r:.4f}|{smooth}|{sound}|{fps}"
                           .encode()).hexdigest()[:12]
        path = Path(folder) / f"{Path(seg.source).stem}-{speed:g}x-{key}.mp4"
        if not path.exists():
            baker(seg.source, a, b, path, fps, speed, r, smooth, sound)
        frames = round(out_seconds(b - a, speed, r) * fps)
        try:
            frames = min(frames, max(1, probe(str(path))[1]))
        except EditError:
            pass  # not readable (a test stand-in): keep the computed length
        note = f"{speed:g}x of {Path(seg.source).name} {a:.2f}-{b:.2f}s" + (f", {r:g}s ramps" if r else "")
        order.append((start, replace(seg, source=str(path), src_in=0, src_out=frames, note=note), seg.duration))
        source_fps = _source_fps(seg.source)
        lines.append(f"  {note}: {(b - a):.2f}s now plays {frames / fps:.2f}s")
        if speed < 1 and source_fps and source_fps * speed < fps * 0.99 and not smooth:
            lines.append(f"  note: the source is {source_fps:g} fps, so at {speed:g}x some frames repeat;"
                         f" film at {math.ceil(fps / speed)} fps for clean slow motion, or add --smooth")
    if not sound:
        lines.append("  the slowed part is silent; music or the voice from other clips plays over it")
    return _rebuild(cut, order), lines


def _rebuild(cut: EditList, order: list[tuple[int, Segment, int]]) -> EditList:
    """The edit with some pieces replaced by longer or shorter ones. Overlays and sounds
    that start inside a piece stay on the same moment of it (their offset is scaled)."""
    spans, t = [], 0
    for old_start, seg, old_len in order:
        spans.append((old_start, old_len, t, seg.duration))
        t += seg.duration

    def move(at: int) -> int | None:
        for old_start, old_len, new_start, new_len in spans:
            if old_start <= at < old_start + old_len:
                return new_start + min(new_len - 1, round((at - old_start) * new_len / old_len))
        return None

    overlays = tuple(replace(o, at=move(o.at)) for o in cut.overlays if move(o.at) is not None)
    sounds = tuple(replace(x, at=move(x.at)) for x in cut.sounds if move(x.at) is not None)
    return replace(cut, segments=_join([seg for _, seg, _ in order]), overlays=overlays, sounds=sounds)


def _source_fps(path: str) -> float | None:
    try:
        return info(path).fps
    except Exception:  # noqa: BLE001  (a missing or odd file just skips the advice)
        return None
