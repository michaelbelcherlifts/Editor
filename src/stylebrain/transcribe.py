"""Make a word-timing transcript with a free speech-to-text tool on this computer.

Nothing is sent anywhere. The first tool found is used:

- `mlx_whisper` (fast on Apple Silicon; `uv tool install mlx-whisper`)
- `whisper` (OpenAI's open-source one; `uv tool install openai-whisper`)

Resolve Studio can also transcribe a clip itself; a transcript from there, or
any .srt/.vtt file, works with `load_words` too.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .edl import EditError
from .media import run
from .transcript import Word, load_words

ENGINES = {
    "mlx_whisper": lambda audio, out, model: [
        "mlx_whisper", audio, "--model", model or "mlx-community/whisper-small.en-mlx",
        "--word-timestamps", "True", "--output-format", "json", "--output-dir", out],
    "whisper": lambda audio, out, model: [
        "whisper", audio, "--model", model or "small.en",
        "--word_timestamps", "True", "--output_format", "json", "--output_dir", out],
}


def available() -> list[str]:
    return [name for name in ENGINES if shutil.which(name)]


def transcribe(video: str, out: str | Path | None = None, engine: str | None = None,
               model: str | None = None) -> tuple[Path, list[Word]]:
    """Transcribe `video` to `<video>.words.json` (or `out`). Returns the path and the words."""
    found = available()
    if engine and engine not in ENGINES:
        raise EditError(f"unknown engine {engine!r}; choose from {', '.join(ENGINES)}")
    if engine and engine not in found:
        raise EditError(f"{engine} is not installed")
    if not found:
        raise EditError("no speech-to-text tool found; install one with `uv tool install mlx-whisper` "
                        "(Apple Silicon) or `uv tool install openai-whisper`, or pass a transcript file")
    engine = engine or found[0]
    out = Path(out) if out else Path(str(video)).with_suffix(".words.json")
    with tempfile.TemporaryDirectory() as tmp:
        audio = str(Path(tmp) / "audio.wav")
        run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", audio])
        run(ENGINES[engine](audio, tmp, model))
        result = Path(tmp) / "audio.json"
        if not result.exists():
            raise EditError(f"{engine} finished but wrote no transcript")
        words = load_words(result)
        if not words:
            raise EditError(f"{engine} returned no word timings")
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(result, out)
    return out, words
