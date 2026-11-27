"""Blur transitions on a cut: a whip pan or a zoom blur, baked into the footage.

Resolve's scripting API cannot add a transition with a changing blur, so the
frames around the cut are baked: ffmpeg decodes the last few frames of the
outgoing clip and the first few of the incoming one, each frame is blurred
with numpy (strongest right at the cut, easing off on both sides), and the
two short pieces are written as new clips. The edit list then points at the
baked pieces. Lengths do not change, so overlays, sounds and the cut itself
stay where they were.

whip: a sideways smear, as if the camera was flicked from one shot to the next.
zoom: a radial smear out from the centre, as if rushing into the frame.
Both are the transitions in cinematic military and gym edits that hide a
cut on a beat or a hit.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import replace
from pathlib import Path

from .edl import EditError, EditList, _join
from .media import info

KINDS = ("whip", "zoom")
_VIDEO_OUT = ["-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p"]


def strengths(n: int, outgoing: bool) -> list[float]:
    """Blur strength 0 to 1 for each of n frames: rising to the cut on the outgoing side, falling after it."""
    if n <= 0:
        return []
    up = [((i + 1) / n) ** 2 for i in range(n)]  # eases in, strongest on the frame before the cut
    return up if outgoing else up[::-1]


def blur_frame(frame, amount: float, kind: str, direction: int = 1, samples: int | None = None):
    """Blur one frame (an H x W x 3 uint8 array). amount 0 to 1; whip slides by up to a third of the width."""
    import numpy as np
    if amount <= 0:
        return frame
    h, w = frame.shape[:2]
    acc = np.zeros(frame.shape, dtype=np.float32)
    # enough copies that neighbours sit a few pixels apart, so the smear reads as motion, not ghosts
    reach = amount * w / 3 if kind == "whip" else amount * w * 0.125
    samples = samples or int(min(48, max(9, reach / 4)))
    if kind == "whip":
        for k in range(samples):
            dx = int(round(direction * reach * (k / (samples - 1) - 0.5 + 0.5 * amount)))
            xs = np.clip(np.arange(w) - dx, 0, w - 1)
            acc += frame[:, xs]
    elif kind == "zoom":
        top = 1 + 0.25 * amount
        ys0, xs0 = np.arange(h) - h / 2, np.arange(w) - w / 2
        for k in range(samples):
            s = 1 + (top - 1) * k / (samples - 1)
            ys = np.clip((ys0 / s + h / 2).astype(int), 0, h - 1)
            xs = np.clip((xs0 / s + w / 2).astype(int), 0, w - 1)
            acc += frame[ys][:, xs]
    else:
        raise EditError(f"transition kind is one of: {', '.join(KINDS)}")
    return (acc / samples).astype(np.uint8)


def bake(src: str, start: float, frames: int, out: str | Path, fps: float, kind: str, outgoing: bool,
         direction: int = 1, max_width: int = 1920) -> Path:
    """Write `frames` frames of `src` from `start` seconds, blurred for one side of a transition."""
    import numpy as np
    i = info(src)
    w, h = i.width, i.height
    if w > max_width:  # keep the blur quick on 4K; the export scales to the frame anyway
        h, w = int(round(h * max_width / w / 2) * 2), max_width
    dec = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{start:.6f}", "-i", src, "-vf", f"fps={fps:g},scale={w}:{h}",
                          "-frames:v", str(frames), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    got = len(dec) // (w * h * 3)
    if got == 0:
        raise EditError(f"could not read frames from {Path(src).name} at {start:.2f}s")
    pics = np.frombuffer(dec[:got * w * h * 3], dtype=np.uint8).reshape(got, h, w, 3)
    while len(pics) < frames:  # a short read at the end of a file: hold the last frame
        pics = np.concatenate([pics, pics[-1:]])
    amt = strengths(frames, outgoing)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    body = b"".join(blur_frame(p, a, kind, direction).tobytes() for p, a in zip(pics, amt))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                    "-r", f"{fps:g}", "-i", "-", *_VIDEO_OUT, str(out)], input=body, capture_output=True, check=True)
    return out


def apply(edit: EditList, at: int, kind: str, folder: str | Path, frames: int = 6, direction: int = 1,
          baker=bake) -> tuple[EditList, list[str]]:
    """Put a `kind` blur transition on the cut at timeline frame `at` (or the nearest cut within half a second).

    `frames` is how many frames on each side are blurred. Returns the new edit and lines to report.
    """
    if kind not in KINDS:
        raise EditError(f"transition kind is one of: {', '.join(KINDS)}")
    if frames < 1:
        raise EditError("frames must be at least 1")
    cuts = [s for s, _ in edit.pieces()][1:]
    if not cuts:
        raise EditError("the edit has no cuts to put a transition on")
    cut = min(cuts, key=lambda c: abs(c - at))
    if abs(cut - at) > edit.fps / 2:
        raise EditError(f"no cut within half a second of that time; the nearest is at frame {cut}")
    starts = [s for s, _ in edit.pieces()]
    i = starts.index(cut)
    before, after = edit.segments[i - 1], edit.segments[i]
    n = min(frames, before.duration, after.duration)
    split = edit.split_at(cut - n).split_at(cut + n)
    fps = edit.fps
    new_segs, lines = [], []
    for start, seg in split.pieces():
        side = "out" if cut - n <= start < cut else "in" if cut <= start < cut + n else None
        if side is None:
            new_segs.append(seg)
            continue
        a = seg.src_in / fps
        key = hashlib.sha1(f"{Path(seg.source).resolve()}|{seg.src_in}|{seg.duration}|{kind}|{side}|{direction}|{fps}"
                           .encode()).hexdigest()[:12]
        path = Path(folder) / f"{Path(seg.source).stem}-{kind}-{side}-{key}.mp4"
        if not path.exists():
            baker(seg.source, a, seg.duration, path, fps, kind, side == "out", direction)
        note = f"{kind} transition ({side}) from {Path(seg.source).name} {a:.2f}s"
        new_segs.append(replace(seg, source=str(path), src_in=0, src_out=seg.duration, note=note))
    lines.append(f"  {kind} blur over {n} frames each side of the cut at frame {cut}")
    return replace(split, segments=_join(new_segs)), lines
