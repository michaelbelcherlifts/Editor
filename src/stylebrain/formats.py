"""Video formats: the frame, loudness and checks that go with where a video is posted.

A project with no format follows the house rule for frame (`rules.py`), then
1080x1920. Set one with `stylebrain format longform`, and exports, builds,
reframing and the long-form checks use its frame.
"""

from __future__ import annotations

from dataclasses import dataclass

from .edl import EditError, EditList


@dataclass(frozen=True)
class Format:
    name: str
    width: int
    height: int
    lufs: float
    min_seconds: float
    max_seconds: float
    chapters: bool          # YouTube chapters in the description
    burned_captions: bool   # captions drawn on the picture (vertical feeds watch muted); long-form uses an uploaded SRT
    about: str

    @property
    def size(self) -> str:
        return f"{self.width}x{self.height}"


FORMATS = {
    "reel": Format("reel", 1080, 1920, -14.0, 7, 90, False, True,
                   "Instagram Reel, TikTok or YouTube Short: vertical 9:16, hook in the first 3 seconds"),
    "short": Format("short", 1080, 1920, -14.0, 7, 180, False, True,
                    "YouTube Short up to 3 minutes: vertical 9:16"),
    "longform": Format("longform", 1920, 1080, -14.0, 480, 1500, True, False,
                       "YouTube long-form, 10 to 20 minutes: wide 16:9, chapters, a re-hook at every chapter"),
    "longform-4k": Format("longform-4k", 3840, 2160, -14.0, 480, 1500, True, False,
                          "YouTube long-form at 4K: same rules as longform, a sharper upload"),
}


def get(name: str) -> Format:
    try:
        return FORMATS[name]
    except KeyError:
        raise EditError(f"unknown format {name!r}; use {', '.join(FORMATS)}") from None


def of(edit: EditList) -> Format | None:
    return get(edit.format) if edit.format else None


def size_for(edit: EditList | None, asked: str | None = None) -> tuple[int, int]:
    """The frame to render or build at: what was asked, then the edit's format, then the house rule, then 1080x1920."""
    if asked is None and edit is not None and edit.format:
        f = get(edit.format)
        return f.width, f.height
    if asked is None:
        from . import rules
        asked = rules.get("frame") or "1080x1920"
    try:
        w, h = (int(x) for x in asked.lower().split("x"))
    except ValueError:
        raise EditError("size looks like 1080x1920") from None
    return w, h


def is_wide(edit: EditList | None) -> bool:
    w, h = size_for(edit)
    return w > h
