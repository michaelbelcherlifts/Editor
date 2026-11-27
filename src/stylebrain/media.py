"""Read a clip's frame rate and length with ffprobe."""

from __future__ import annotations

import json
import subprocess
from fractions import Fraction

from .edl import EditError


def probe(path: str) -> tuple[float, int]:
    """Return (fps, frame count) of the first video stream."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
             "-show_entries", "stream=r_frame_rate,nb_read_packets,nb_frames,duration",
             "-of", "json", path],
            capture_output=True, text=True, check=True,
        ).stdout
    except FileNotFoundError:
        raise EditError("ffprobe is not installed; install ffmpeg or pass --fps and --frames") from None
    except subprocess.CalledProcessError as e:
        raise EditError(f"could not read {path}: {e.stderr.strip()}") from None
    streams = json.loads(out).get("streams") or []
    if not streams:
        raise EditError(f"{path} has no video stream")
    s = streams[0]
    fps = float(Fraction(s["r_frame_rate"]))
    frames = s.get("nb_read_packets") or s.get("nb_frames")
    if frames in (None, "N/A"):
        frames = round(float(s["duration"]) * fps)
    return fps, int(frames)
