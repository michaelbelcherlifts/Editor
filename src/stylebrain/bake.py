"""Effects baked into footage with ffmpeg, for things Resolve scripting cannot keyframe."""

from __future__ import annotations

from pathlib import Path

from .edl import EditError
from .media import has_audio, info, run

_VIDEO_OUT = ["-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p"]


def punch_in(src: str, out: str, start: float, end: float, zoom: float = 1.2, ease: float = 0.25,
             cx: float = 0.5, cy: float = 0.5) -> str:
    """Zoom in to `zoom` between start and end seconds, easing in and out.

    cx, cy (0 to 1) choose the point the zoom centres on. ease=0 gives a hard cut zoom.
    """
    if not (zoom >= 1.0 and end > start and 0 <= cx <= 1 and 0 <= cy <= 1 and ease >= 0):
        raise EditError("punch_in needs zoom >= 1, end after start, and cx, cy between 0 and 1")
    i = info(src)
    w, h = i.width, i.height
    if ease > 0:
        up = f"clip((t-{start})/{ease},0,1)"
        down = f"clip(({end}-t)/{ease},0,1)"
        k = f"min({up},{down})"
        k = f"({k})*({k})*(3-2*({k}))"  # smoothstep
    else:
        k = f"between(t,{start},{end})"
    z = f"(1+{zoom - 1}*{k})"
    vf = (f"scale=w='2*trunc({w}*{z}/2)':h='2*trunc({h}*{z}/2)':eval=frame,"
          f"crop={w}:{h}:'(in_w-{w})*{cx}':'(in_h-{h})*{cy}'")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", vf, *_VIDEO_OUT, "-c:a", "copy", out])
    return out


def change_speed(src: str, out: str, factor: float) -> str:
    """Play the clip `factor` times faster (0.5 is half speed). Audio pitch is kept."""
    if not 0.25 <= factor <= 8:
        raise EditError("speed factor must be between 0.25 and 8")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", f"setpts=PTS/{factor}"]
    if has_audio(src):
        steps, f = [], factor
        while f > 2.0:
            steps.append("atempo=2.0"); f /= 2.0
        while f < 0.5:
            steps.append("atempo=0.5"); f /= 0.5
        steps.append(f"atempo={f}")
        cmd += ["-af", ",".join(steps)]
    run(cmd + _VIDEO_OUT + [out])
    return out
