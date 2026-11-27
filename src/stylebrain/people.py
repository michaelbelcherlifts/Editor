"""Shots built around the person and the bar, as vertical clips to lay over the main track (`broll`).

- wide_clip: a landscape lift shown wide enough to see the bar and plates in a 9:16 frame, filled above and
  below with the same shot blurred ("blur") or with black film bars ("film", the cinematic strip)
- behind: big text placed behind the person: background, then the text layer, then the person cut back
  out on top (MediaPipe's multiclass selfie segmenter; `uv sync --extra people`)
- speech_only: a copy of a clip with its sound kept only where words are spoken, so a vlog's own music
  drops out between lines and a new song can sit under the edit

Michael asked for all three after round 1 of the practice reels: "put text behind people", "zoom out and
include the weights", and better music.
"""

from __future__ import annotations

import json
import subprocess
import urllib.request
from pathlib import Path

from .edl import EditError
from .media import run

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/image_segmenter/"
             "selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite")
MODEL = Path("library") / "models" / "selfie_multiclass_256x256.tflite"
W, H = 1080, 1920


def wide_filter(x: float = 0.5, share: float = 0.62, fill: str = "blur", width: int = W, height: int = H,
                fps: float | None = None) -> str:
    """The ffmpeg filter for `wide_clip`. `share` is how much of the source width stays in the picture."""
    if not 0.2 <= share <= 1 or not 0 <= x <= 1:
        raise EditError("share is between 0.2 and 1 of the source width, x between 0 and 1")
    crop_x = f"max(0\\,min(iw-iw*{share}\\,iw*{x}-iw*{share}/2))"
    rate = f"fps={fps:g}," if fps else ""
    if fill == "blur":
        return (f"[0:v]{rate}split[a][b];"
                f"[a]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
                "boxblur=24:2,eq=brightness=-0.22:saturation=0.8[bg];"
                f"[b]crop=iw*{share}:ih:{crop_x}:0,scale={width}:-2[fg];"
                "[bg][fg]overlay=0:(H-h)/2-60,setsar=1[v]")
    if fill == "film":
        # The full height of the shot is always kept: a lift's plates sit at the bottom of the frame, and a
        # 2:1 strip that cropped top and bottom cut them off (Michael, round 4: "weights were cut out").
        return (f"[0:v]{rate}crop=iw*{share}:ih:{crop_x}:0,scale={width}:-2,"
                "eq=contrast=1.18:saturation=0.78:brightness=-0.035:gamma=0.95,"
                f"pad={width}:{height}:0:(oh-ih)/2-80:black,setsar=1[v]")
    raise EditError("fill is 'blur' (the shot blurred above and below) or 'film' (black bars, a graded strip)")


def wide_clip(src: str, start: float, end: float, out: str, x: float = 0.5, share: float = 0.62,
              fill: str = "blur", fps: float | None = None) -> Path:
    """Render a vertical clip of src[start:end] that keeps the bar and plates in view."""
    if end <= start:
        raise EditError("end must come after start")
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start}", "-to", f"{end}", "-i", src, "-an",
         "-filter_complex", wide_filter(x, share, fill, fps=fps), "-map", "[v]",
         "-c:v", "libx264", "-crf", "15", "-preset", "veryfast", "-pix_fmt", "yuv420p", out])
    return Path(out)


def speech_spans(words: list[dict], pad: float = 0.12, join: float = 0.35) -> list[tuple[float, float]]:
    """Stretches where someone is talking: each word padded, words closer than `join` merged."""
    spans: list[list[float]] = []
    for w in sorted(words, key=lambda w: float(w["start"])):
        a, b = float(w["start"]) - pad, float(w["end"]) + pad
        if spans and a <= spans[-1][1] + join:
            spans[-1][1] = max(spans[-1][1], b)
        else:
            spans.append([max(a, 0.0), b])
    return [(a, b) for a, b in spans]


def speech_only(src: str, words_file: str, out: str, pad: float = 0.12) -> tuple[Path, int]:
    """Copy src with its sound muted wherever nobody is speaking (picture untouched)."""
    words = json.loads(Path(words_file).read_text(encoding="utf-8"))
    spans = speech_spans(words, pad)
    if not spans:
        raise EditError("the transcript has no words, so everything would be muted")
    expr = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in spans)
    script = Path(out).with_suffix(".mute.txt")
    script.write_text(f"volume='if({expr},1,0)':eval=frame", encoding="utf-8")
    try:
        run(["ffmpeg", "-v", "error", "-y", "-i", src, "-c:v", "copy", "-/filter:a", str(script),
             "-c:a", "aac", "-b:a", "192k", out])
    finally:
        script.unlink(missing_ok=True)
    return Path(out), len(spans)


def composite(bg, text, mask):
    """One frame: text (RGBA) over the background, then the person (where mask is 1) back on top."""
    import numpy as np
    out = bg.astype(np.float32)
    if text is not None:
        alpha = text[..., 3:4].astype(np.float32) / 255
        out = out * (1 - alpha) + text[..., :3].astype(np.float32) * alpha
    m = mask[..., None] if mask.ndim == 2 else mask
    out = out * (1 - m) + bg.astype(np.float32) * m
    return out.clip(0, 255).astype(np.uint8)


def _model() -> Path:
    if not MODEL.exists():
        MODEL.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MODEL_URL, MODEL)
    return MODEL


def _frames(path: str, pix: str, channels: int):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", pix, "-s", f"{W}x{H}", "-"],
                         stdout=subprocess.PIPE)
    import numpy as np
    n = W * H * channels
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            return
        yield np.frombuffer(b, np.uint8).reshape(H, W, channels)


def behind(base: str, text: str, out: str, fps: float = 30.0, feather: float = 7.0) -> Path:
    """Put a transparent text layer (a .mov from `render`, e.g. big_title) behind the person in `base`.
    Both are 1080x1920 and start together. The mask is smoothed over time so its edge does not flicker."""
    try:
        import cv2
        import mediapipe as mp
        import numpy as np
        from mediapipe.tasks.python import BaseOptions, vision
    except ImportError:
        raise EditError("text behind a person needs MediaPipe; run `uv sync --extra people`") from None
    seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
        base_options=BaseOptions(model_asset_path=str(_model())), output_confidence_masks=True,
        running_mode=vision.RunningMode.VIDEO))
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", f"{fps}", "-i", "-", "-c:v", "libx264", "-crf", "15", "-preset", "veryfast",
                            "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    layer, prev = _frames(text, "rgba", 4), None
    for i, bg in enumerate(_frames(base, "rgb24", 3)):
        small = np.ascontiguousarray(cv2.resize(bg, (W // 2, H // 2)))
        r = seg.segment_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=small), int(i * 1000 / fps))
        m = cv2.resize(1 - np.squeeze(r.confidence_masks[0].numpy_view()), (W, H))   # 1 = person
        if prev is not None:
            m = 0.6 * m + 0.4 * prev
        prev = m
        m = cv2.GaussianBlur(np.clip((m - 0.35) / 0.3, 0, 1).astype(np.float32), (0, 0), feather)
        enc.stdin.write(composite(bg, next(layer, None), m).tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        raise EditError(f"ffmpeg could not write {out}")
    return Path(out)
