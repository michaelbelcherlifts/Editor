"""Ready-made first-cut styles: a caption treatment and a pause length under one name.

A preset is a starting point picked by sight (`preset-preview`), not a rule.
His house rules still win where he has set them, and a learned style
(`--style`) still sets the pause length when one is given.
"""

from __future__ import annotations

from pathlib import Path

from .edl import EditError

PRESETS: dict[str, dict] = {
    "one-word": {
        "about": "one word at a time in the middle of the frame, capitals; fastest feel",
        "template": "mid_captions", "params": {"max_words": 1, "size": 128, "uppercase": True, "y": 0.52},
        "pause_min_gap": 0.35},
    "punchy": {
        "about": "two or three words popping in mid-frame; talking to camera with energy",
        "template": "mid_captions", "params": {"max_words": 3, "size": 104, "y": 0.60},
        "pause_min_gap": 0.4},
    "slam": {
        "about": "huge tilted stacked words that slam in, one in colour; hooks and jokes",
        "template": "kinetic_type", "params": {"per_group": 2},
        "pause_min_gap": 0.35},
    "talking-head": {
        "about": "running captions low in the frame, the spoken word highlighted; explainers",
        "template": "captions", "params": {},
        "pause_min_gap": 0.6},
    "clean": {
        "about": "no captions on screen (a subtitle file is still written); lifts and music-led reels",
        "template": None, "params": {},
        "pause_min_gap": 0.6},
}

SAMPLE = ["This", "one", "cue", "fixed", "my", "bench", "in", "a", "week"]


def get(name: str) -> dict:
    if name not in PRESETS:
        raise EditError(f"no preset named {name!r}; choose from {', '.join(PRESETS)}")
    return PRESETS[name]


def listing() -> str:
    return "\n".join(f"  {name:<14}{p['about']}" for name, p in PRESETS.items())


def sample_words(words: list[str] | None = None, each: float = 0.32) -> list[dict]:
    return [{"word": w, "start": round(i * each, 3), "end": round((i + 1) * each - 0.04, 3)}
            for i, w in enumerate(words or SAMPLE)]


def preview(name: str, out: str | Path | None = None, width: int = 1080, height: int = 1920, fps: float = 30.0,
            render=None, font: str | None = None) -> Path | None:
    """Render a few seconds of the preset's captions on a plain backdrop, to pick by sight. None for no captions."""
    p = get(name)
    if not p["template"]:
        return None
    if render is None:
        from .effects import render_template as render
    tag = f"preset-{name}" + (f"-{font.strip().lower().replace(' ', '-')}" if font else "")
    params = {**p["params"], "words": sample_words(), **({"font": font} if font else {})}
    r = render(p["template"], params, None, fps, width, height, tag)
    out = Path(out) if out else Path(".stylebrain") / "renders" / f"{tag}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    from .media import run
    run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x30343a:s={width}x{height}:r={fps:g}",
         "-i", str(r.path), "-filter_complex", "[0:v][1:v]overlay=shortest=1[v]", "-map", "[v]",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(out)])
    return out
