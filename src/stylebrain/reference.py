"""Study a reference video: get it, look at it frame by frame, and measure it.

These are the eyes for copying an effect. Claude cannot watch video, so a
moment is turned into things it can use: a contact sheet of frames to look at,
a motion curve that says when things move and for how long, and the colours
on screen. `compare_sheet` then puts a render next to the reference to check
the copy.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from .edl import EditError
from .media import info, read_frame, read_frames, run


def fetch(url: str, dest: str | Path = "references", max_height: int = 1080) -> Path:
    """Download a video for private study with yt-dlp. Returns the file path.

    Not run in automated tests: it needs the network and yt-dlp.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    out = run(["yt-dlp", "--no-playlist", "-f", f"bv*[height<={max_height}]+ba/b[height<={max_height}]/b",
               "--merge-output-format", "mp4", "--write-info-json", "--write-auto-subs", "--sub-langs", "en.*",
               "-o", str(dest / "%(id)s.%(ext)s"), "--print", "after_move:filepath", url], text=True).stdout
    path = Path(out.strip().splitlines()[-1])
    if not path.exists():
        raise EditError(f"yt-dlp reported {path} but it is not there")
    return path


def _times(start: float, end: float, count: int) -> list[float]:
    if count < 1 or end <= start:
        raise EditError("need a positive count and an end after the start")
    step = (end - start) / count
    return [round(start + step * (n + 0.5), 4) for n in range(count)]


def contact_sheet(video: str, start: float, end: float, out: str | Path, count: int = 24, columns: int = 6,
                  width: int = 320, label: bool = True) -> list[float]:
    """Save `count` evenly spaced frames as one image, in reading order.

    Returns the time of each frame. Times are also drawn on the frames when
    ffmpeg can draw text.
    """
    times = _times(start, end, count)
    rows = math.ceil(count / columns)
    pick = f"fps={count / (end - start):.6f}:round=near,scale={width}:-2"
    stamp = (f"drawtext=text='%{{pts\\:hms\\:{start:.3f}}}':fontcolor=white:fontsize=16:"
             "box=1:boxcolor=black@0.6:x=4:y=4,")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    for text in ([stamp, ""] if label else [""]):
        try:
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.4f}", "-t", f"{end - start:.4f}",
                 "-i", str(video), "-vf", f"{pick},{text}tile={columns}x{rows}", "-frames:v", "1", str(out)])
            break
        except EditError:
            if not text:
                raise
    return times


def frames(video: str, start: float, end: float, out_dir: str | Path, count: int = 12,
           width: int = 960) -> list[dict]:
    """Save individual frames for a close look. Returns [{"time", "path"}]."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for n, t in enumerate(_times(start, end, count)):
        path = out_dir / f"frame_{n:03d}_{t:.2f}s.png"
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.4f}", "-i", str(video), "-frames:v", "1",
             "-vf", f"scale={width}:-2", str(path)])
        saved.append({"time": t, "path": str(path)})
    return saved


@dataclass(frozen=True)
class Motion:
    """How much the picture changes over a stretch of video."""

    times: list[float]
    change: list[float]          # mean absolute pixel change from the frame before, 0 to 255
    bursts: list[tuple[float, float]]  # (start, end) of each stretch of movement

    def to_dict(self) -> dict:
        return {"bursts": [{"start": round(a, 3), "end": round(b, 3), "seconds": round(b - a, 3)}
                           for a, b in self.bursts],
                "curve": [{"t": round(t, 3), "change": round(c, 2)} for t, c in zip(self.times, self.change)]}


def motion(video: str, start: float, end: float, threshold: float = 0.6, width: int = 160) -> Motion:
    """Find when things move between start and end, and for how long.

    A burst is a run of frames that each differ from the one before by more
    than `threshold`. For an animation over still footage, the burst length is
    the animation's duration.
    """
    import numpy as np

    fps = info(video).fps
    f = read_frames(video, start, end, width=width).astype(np.int16)
    change = [0.0] + [float(np.abs(f[n] - f[n - 1]).mean()) for n in range(1, len(f))]
    times = [start + n / fps for n in range(len(f))]
    bursts, begin = [], None
    for n, c in enumerate(change):
        if c > threshold and begin is None:
            begin = n
        elif c <= threshold and begin is not None:
            bursts.append((times[begin - 1], times[n - 1])); begin = None
    if begin is not None:
        bursts.append((times[begin - 1], times[-1]))
    return Motion(times, change, bursts)


def palette(video: str, t: float, colours: int = 5, box: list[float] | None = None) -> list[dict]:
    """The main colours of a frame, most common first, as [{"hex", "share"}].

    box = [x, y, w, h] as fractions limits it to part of the frame.
    """
    import numpy as np

    frame = read_frame(video, t, width=320)
    if box:
        h, w = frame.shape[:2]
        x0, y0 = int(box[0] * w), int(box[1] * h)
        frame = frame[y0:max(y0 + 1, int((box[1] + box[3]) * h)), x0:max(x0 + 1, int((box[0] + box[2]) * w))]
    pixels = frame.reshape(-1, 3).astype(np.int32)
    buckets = (pixels // 24)                     # coarse bins so near-identical shades group together
    keys = buckets[:, 0] * 10000 + buckets[:, 1] * 100 + buckets[:, 2]
    uniq, inverse, counts = np.unique(keys, return_inverse=True, return_counts=True)
    order = np.argsort(-counts)[:colours]
    out = []
    for idx in order:
        mean = pixels[inverse == idx].mean(axis=0).round().astype(int)
        out.append({"hex": "#%02x%02x%02x" % tuple(mean), "share": round(float(counts[idx]) / len(pixels), 3)})
    return out


def compare_sheet(reference: str, ref_start: float, mine: str, mine_start: float, seconds: float,
                  out: str | Path, count: int = 8, width: int = 320, background: str | None = None,
                  background_start: float = 0.0) -> list[float]:
    """Reference frames on the top row, your render on the bottom row, at matching moments.

    If `mine` is a transparent overlay, pass `background` (a clip or image) to
    show it over footage; otherwise it is shown over mid grey.
    """
    step = seconds / count
    offsets = [round(step * (n + 0.5), 4) for n in range(count)]
    ri, mi = info(reference), info(mine)
    h = round(ri.height * width / ri.width / 2) * 2
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    scale = f"scale={width}:{h}:force_original_aspect_ratio=decrease,pad={width}:{h}:(ow-iw)/2:(oh-ih)/2"
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{ref_start:.4f}", "-t", f"{seconds:.4f}", "-i", str(reference),
           "-ss", f"{mine_start:.4f}", "-t", f"{seconds:.4f}", "-i", str(mine)]
    if background:
        still = Path(background).suffix.lower() in (".png", ".jpg", ".jpeg")
        cmd += (["-loop", "1", "-t", f"{seconds:.4f}"] if still else
                ["-ss", f"{background_start:.4f}", "-t", f"{seconds:.4f}"]) + ["-i", str(background)]
        under = f"[2:v]scale={mi.width}:{mi.height},fps={mi.fps}[bg];"
    else:
        cmd += ["-f", "lavfi", "-t", f"{seconds:.4f}", "-i", f"color=c=0x777777:s={mi.width}x{mi.height}:r={mi.fps}"]
        under = "[2:v]null[bg];"
    pick = f"fps={count / seconds:.6f}:round=near"
    graph = (f"{under}[bg][1:v]overlay=shortest=1[m];"
             f"[0:v]{pick},{scale},tile={count}x1[top];[m]{pick},{scale},tile={count}x1[bot];[top][bot]vstack")
    run(cmd + ["-filter_complex", graph, "-frames:v", "1", str(out)])
    return offsets


def describe(video: str) -> dict:
    """Basic facts about a reference file, plus yt-dlp's saved details when present."""
    i = info(video)
    facts = {"path": str(video), "fps": i.fps, "seconds": round(i.duration, 2), "width": i.width, "height": i.height}
    meta = Path(video).with_suffix(".info.json")
    if meta.exists():
        data = json.loads(meta.read_text())
        facts |= {k: data.get(k) for k in ("title", "uploader", "webpage_url", "view_count", "upload_date")}
    return facts
