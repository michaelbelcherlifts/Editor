"""Read facts and frames from video files with ffprobe and ffmpeg."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from fractions import Fraction

from .edl import EditError


@dataclass(frozen=True)
class Info:
    fps: float
    frames: int
    width: int
    height: int
    pix_fmt: str

    @property
    def duration(self) -> float:
        return self.frames / self.fps

    @property
    def has_alpha(self) -> bool:
        return "a" in self.pix_fmt.replace("gray", "") and self.pix_fmt.startswith(("yuva", "rgba", "bgra", "argb", "abgr", "gbrap", "ya"))


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    """Run a command, turning failure into an EditError with the tool's own message."""
    try:
        return subprocess.run(cmd, capture_output=True, check=True, **kw)
    except FileNotFoundError:
        raise EditError(f"{cmd[0]} is not installed") from None
    except subprocess.CalledProcessError as e:
        err = e.stderr if isinstance(e.stderr, str) else (e.stderr or b"").decode(errors="replace")
        raise EditError(f"{cmd[0]} failed: {err.strip()[-600:]}") from None


def info(path: str) -> Info:
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
               "-show_entries", "stream=r_frame_rate,nb_read_packets,nb_frames,duration,width,height,pix_fmt",
               "-of", "json", str(path)], text=True).stdout
    streams = json.loads(out).get("streams") or []
    if not streams:
        raise EditError(f"{path} has no video stream")
    s = streams[0]
    fps = float(Fraction(s["r_frame_rate"]))
    frames = s.get("nb_read_packets") or s.get("nb_frames")
    if frames in (None, "N/A"):
        frames = round(float(s["duration"]) * fps)
    return Info(fps, int(frames), int(s["width"]), int(s["height"]), s.get("pix_fmt", ""))


def probe(path: str) -> tuple[float, int]:
    """Return (fps, frame count) of the first video stream."""
    i = info(path)
    return i.fps, i.frames


def has_audio(path: str) -> bool:
    out = run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
               "-of", "csv=p=0", str(path)], text=True).stdout
    return bool(out.strip())


def read_frame(path: str, t: float, width: int | None = None):
    """One frame at time t (seconds) as a height x width x 3 uint8 array. Needs numpy."""
    import numpy as np

    i = info(path)
    w = width or i.width
    h = round(i.height * w / i.width / 2) * 2 if width else i.height
    raw = run(["ffmpeg", "-v", "error", "-ss", f"{t:.4f}", "-i", str(path), "-frames:v", "1",
               "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]).stdout
    if len(raw) != w * h * 3:
        raise EditError(f"no frame at {t:.2f}s in {path}")
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3)
