"""Reframing: where to put the crop when footage has to fill a frame of another shape.

Wide footage in a vertical frame keeps only about a third of its width, so the
crop has to sit on the subject. `track` finds the subject through a clip (faces
when OpenCV is installed, otherwise where the movement is), and `plan` turns
that into one steady framing per shot. A locked crop per shot is the default on
purpose: a crop that drifts after the subject looks like a shaky camera.

The framing is stored on each main-track clip (`x`, `y`, `zoom`), so it follows
the clip through cuts and moves, exports with ffmpeg and builds in Resolve.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .edl import EditError, EditList
from .media import info, read_frames, run

CHUNK = 40.0          # seconds of footage read at a time
SAME_SHOT = 0.06      # subjects closer than this (share of the width) share one framing


def geometry(sw: int, sh: int, tw: int, th: int, x: float = 0.5, y: float = 0.5, zoom: float = 1.0) -> dict:
    """How a source picture sits in a target frame: scale, crop corner, and Resolve's Zoom, Pan and Tilt."""
    fill, fit = max(tw / sw, th / sh), min(tw / sw, th / sh)
    scale = fill * zoom
    w, h = sw * scale, sh * scale
    left = min(max(x * w - tw / 2, 0.0), w - tw)
    top = min(max(y * h - th / 2, 0.0), h - th)
    return {"scale": scale, "left": left, "top": top, "zoom": scale / fit,
            "pan": w / 2 - (left + tw / 2), "tilt": (top + th / 2) - h / 2,
            "window": (tw / w, th / h)}


def crop_filter(tw: int, th: int, x: float = 0.5, y: float = 0.5, zoom: float = 1.0) -> str:
    """The ffmpeg filter for the same framing. Works without knowing the source size."""
    k = f"max({tw}/iw\\,{th}/ih)*{zoom:.4f}"
    return (f"scale=w='ceil(iw*{k}/2)*2':h='ceil(ih*{k}/2)*2',"
            f"crop={tw}:{th}:'clip(iw*{x:.4f}-{tw}/2\\,0\\,iw-{tw})':'clip(ih*{y:.4f}-{th}/2\\,0\\,ih-{th})',setsar=1")


# ------------------------------------------------------------------ tracking

@dataclass(frozen=True)
class Sample:
    t: float
    face: tuple[float, float] | None   # centre of the largest face, 0..1
    cols: object                       # movement in each column since the last sample
    rows: object
    moved: float = 0.0                 # share of the picture that changed since the last sample


_cascade = None


def _faces(gray) -> tuple[float, float] | None:
    """Centre of the largest face in a grey frame, or None. Needs OpenCV; without it, always None."""
    global _cascade
    try:
        import cv2
    except ImportError:
        return None
    if not hasattr(cv2, "CascadeClassifier"):
        return None
    if _cascade is None:
        _cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    h, w = gray.shape
    found = _cascade.detectMultiScale(gray, 1.1, 5, minSize=(max(h // 12, 24), max(h // 12, 24)))
    if len(found) == 0:
        return None
    fx, fy, fw, fh = max(found, key=lambda f: f[2] * f[3])
    return ((fx + fw / 2) / w, (fy + fh / 2) / h)


def track(video: str, start: float, end: float, per_second: float = 3.0, width: int = 480) -> list[Sample]:
    """Sample a stretch of a clip: where the face is and where the picture moves. Needs numpy."""
    import numpy as np

    out: list[Sample] = []
    prev = None
    a = start
    while a < end - 1e-6:
        b = min(a + CHUNK, end)
        try:
            frames = read_frames(video, a, b, fps=per_second, width=width)
        except EditError:
            break
        grey = (frames.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32))
        for n, g in enumerate(grey):
            small = g[::3, ::3]
            share = 0.0
            if prev is None or prev.shape != small.shape:
                cols, rows = np.zeros(small.shape[1]), np.zeros(small.shape[0])
            else:
                moved = np.abs(small - prev) > 14
                cols, rows = moved.sum(axis=0).astype(float), moved.sum(axis=1).astype(float)
                share = float(moved.mean())
            prev = small
            out.append(Sample(round(a + n / per_second, 3), _faces(g.astype(np.uint8)), cols, rows, share))
        a = b
    return out


def _spot(weights) -> tuple[float, float, float]:
    """Weighted middle of a row of weights, and the 10% and 90% points, each 0..1."""
    import numpy as np

    total = weights.sum()
    c = np.cumsum(weights) / total
    at = lambda q: float((np.searchsorted(c, q) + 0.5) / len(weights))  # noqa: E731
    return at(0.5), at(0.1), at(0.9)


@dataclass(frozen=True)
class Subject:
    x: float
    y: float
    lo: float       # the subject's reach across the frame, 0..1
    hi: float
    method: str     # face, motion or centre


def subject(samples: list[Sample]) -> Subject:
    """Where the subject is over a set of samples."""
    import numpy as np

    faces = [s.face for s in samples if s.face]
    if samples and len(faces) >= max(2, 0.4 * len(samples)):
        xs, ys = np.array([f[0] for f in faces]), np.array([f[1] for f in faces])
        return Subject(float(np.median(xs)), float(np.median(ys)), float(np.percentile(xs, 10)),
                       float(np.percentile(xs, 90)), "face")
    calm = [s for s in samples if s.moved < 0.3]      # a sample taken across a cut says nothing about the subject
    if calm:
        cols, rows = sum(s.cols for s in calm), sum(s.rows for s in calm)
        area = len(cols) * len(rows) * max(len(calm) - 1, 1)
        if cols.sum() / area > 0.0005:
            x, lo, hi = _spot(cols)
            return Subject(x, _spot(rows)[0], lo, hi, "motion")
    return Subject(0.5, 0.5, 0.5, 0.5, "centre")


def shot_changes(video: str, samples: list[Sample], fps: float) -> list[int]:
    """Source frames where the picture cuts to a different shot, found from the samples.

    A sample where much of the picture changed is looked at frame by frame. It
    counts as a cut only when one pair of frames holds the change; a zoom or a
    pan spreads it over many frames and is left alone.
    """
    import numpy as np

    out = []
    for before, after in zip(samples, samples[1:]):
        if after.moved < 0.3:
            continue
        # A sample's time is only good to about one sampling step either way (the frame handed
        # back is the nearest one, not the exact one), so look a full step before and after.
        step = max(after.t - before.t, 1 / fps)
        first = max(int((before.t - step) * fps) - 1, 0)
        try:
            frames = read_frames(video, max(first - 0.25, 0) / fps, ((after.t + step) * fps + 2) / fps, width=160)
        except EditError:
            continue
        grey = frames.astype(np.float32).mean(axis=3)
        change = (np.abs(grey[1:] - grey[:-1]) > 14).mean(axis=(1, 2))
        if len(change) < 3:
            continue
        k = int(change.argmax())
        rest = np.delete(change, k)
        if change[k] > 0.3 and change[k] > 3 * float(np.median(rest)) + 0.05:
            out.append(first + k + 1)
    return sorted(set(out))


# ------------------------------------------------------------------ planning

def plan(edit: EditList, width: int = 1080, height: int = 1920, per_second: float = 3.0) -> tuple[EditList, list[str]]:
    """Give every main-track clip a framing that keeps its subject in the frame.

    Returns the new edit and a line per shot. Clips next to each other from the
    same recording share one framing unless the subject has clearly moved, so
    jump cuts do not jitter.
    """
    fps = edit.fps
    sizes = {s: info(s) for s in edit.sources()}
    spans: dict[str, tuple[int, int]] = {}
    for seg in edit.segments:
        lo, hi = spans.get(seg.source, (seg.src_in, seg.src_out))
        spans[seg.source] = (min(lo, seg.src_in), max(hi, seg.src_out))
    tracks = {}
    for src, (lo, hi) in spans.items():
        i = sizes[src]
        if abs(i.width / i.height - width / height) < 0.01:
            continue                                  # already the right shape; nothing to choose
        tracks[src] = track(src, lo / fps, hi / fps, per_second)

    # Where a clip holds more than one shot, split it there (a split changes nothing visible).
    for src, samples in tracks.items():
        for frame in shot_changes(src, samples, fps):
            for a, b in edit.timeline_ranges_for_source(src, frame - 1, frame + 1):
                if b - a == 2:
                    edit = edit.split_at(a + 1)

    # One subject per clip, then group neighbours into shots.
    shots: list[dict] = []
    for start, seg in edit.pieces():
        if seg.source not in tracks:
            shots.append({"start": start, "end": start + seg.duration, "source": seg.source, "sub": None})
            continue
        a, b = seg.src_in / fps, seg.src_out / fps
        inside = [s for s in tracks[seg.source] if a <= s.t < b]
        if not inside:                                # shorter than the sampling step: use the nearest sample
            inside = sorted(tracks[seg.source], key=lambda s: abs(s.t - (a + b) / 2))[:1]
        sub = subject(inside)
        last = shots[-1] if shots else None
        if (last and last["sub"] and last["source"] == seg.source and last["sub"].method == sub.method
                and abs(last["sub"].x - sub.x) < SAME_SHOT and abs(last["sub"].y - sub.y) < SAME_SHOT):
            wa, wb = last["end"] - last["start"], seg.duration
            m = last["sub"]
            last["sub"] = Subject((m.x * wa + sub.x * wb) / (wa + wb), (m.y * wa + sub.y * wb) / (wa + wb),
                                  min(m.lo, sub.lo), max(m.hi, sub.hi), m.method)
            last["end"] = start + seg.duration
        else:
            shots.append({"start": start, "end": start + seg.duration, "source": seg.source, "sub": sub})

    lines = []
    for shot in shots:
        when = f"{shot['start'] / fps:7.2f}s to {shot['end'] / fps:.2f}s"
        sub = shot["sub"]
        if sub is None:
            lines.append(f"{when}  already fits the frame")
            continue
        i = sizes[shot["source"]]
        win_w, win_h = geometry(i.width, i.height, width, height, zoom=1.0)["window"]
        x = min(max(sub.x, win_w / 2), 1 - win_w / 2)
        # y is kept as found, even where the frame cannot move that way yet: a later punch-in
        # then closes in on the face and not on the middle of the picture.
        y = sub.y if sub.method == "face" else min(max(sub.y, win_h / 2), 1 - win_h / 2)
        edit = edit.reframe(shot["start"], shot["end"], x=x, y=y)
        line = f"{when}  x {x:.2f}, y {y:.2f}  ({sub.method})"
        if sub.method == "centre":
            line += "  nothing to follow, kept in the middle"
        elif sub.hi - sub.lo > win_w and win_w < 0.99:
            line += f"  warning: the subject ranges over {100 * (sub.hi - sub.lo):.0f}% of the width; the frame holds {100 * win_w:.0f}%"
        lines.append(line)
    return edit, lines


def preview(edit: EditList, out: str | Path, width: int = 1080, height: int = 1920, limit: int = 12) -> Path:
    """One image with the middle frame of each framing, cropped as it will be, in order."""
    shots: list[tuple[str, int, tuple]] = []
    last = None
    for _, seg in edit.pieces():
        key = (seg.source, seg.framing)
        if key != last:
            shots.append((seg.source, (seg.src_in + seg.src_out) // 2, seg.framing))
            last = key
    shots = shots[:limit]
    tw = 270
    th = round(tw * height / width / 2) * 2
    cmd, chains = ["ffmpeg", "-v", "error", "-y"], []
    for n, (src, frame, (x, y, zoom)) in enumerate(shots):
        cmd += ["-ss", f"{frame / edit.fps:.4f}", "-i", src]
        chains.append(f"[{n}:v]{crop_filter(tw, th, x, y, zoom)},trim=end_frame=1[p{n}]")
    row = "".join(f"[p{n}]" for n in range(len(shots)))
    chains.append(f"{row}hstack=inputs={len(shots)}[o]" if len(shots) > 1 else "[p0]null[o]")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    run(cmd + ["-filter_complex", ";".join(chains), "-map", "[o]", "-frames:v", "1", str(out)])
    return Path(out)
