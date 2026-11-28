"""The edit list: an edit kept as data, so any change can be rebuilt as a new timeline.

Resolve's scripting API cannot blade, trim or move a clip that is already on a
timeline. So the edit lives here instead, as an ordered list of source ranges
(the main track) plus overlays placed at timeline positions (graphics, effects,
b-roll). Every operation returns a new EditList; nothing is changed in place.

All positions are whole frames at the edit's frame rate. Ranges are half open:
[start, end).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace


class EditError(ValueError):
    """An edit request that cannot be applied as asked."""


@dataclass(frozen=True)
class Segment:
    """A range of one source clip on the main track."""

    source: str
    src_in: int
    src_out: int
    note: str = ""
    # Framing, used when the clip has to fill a frame of another shape: the point of the
    # source picture kept in the middle (0..1 across, 0..1 down) and a punch-in.
    x: float = 0.5
    y: float = 0.5
    zoom: float = 1.0
    # A split edit at the cut into this piece: how many frames the sound changes away from
    # the picture. Negative is a J-cut (this piece's sound comes in early, under the piece
    # before); positive is an L-cut (the sound of the piece before carries on under this one).
    audio_shift: int = 0

    def __post_init__(self) -> None:
        if self.src_in < 0 or self.src_out <= self.src_in:
            raise EditError(f"bad source range {self.src_in}..{self.src_out} for {self.source}")
        if not (0 <= self.x <= 1 and 0 <= self.y <= 1 and 1 <= self.zoom <= 4):
            raise EditError("framing: x and y run from 0 to 1, zoom from 1 to 4")

    @property
    def framing(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.zoom)

    @property
    def duration(self) -> int:
        return self.src_out - self.src_in


@dataclass(frozen=True)
class Overlay:
    """A clip placed above the main track at a timeline position."""

    name: str
    source: str
    at: int
    duration: int
    track: int = 2
    src_in: int = 0

    def __post_init__(self) -> None:
        if self.at < 0 or self.duration <= 0 or self.track < 2 or self.src_in < 0:
            raise EditError(f"bad overlay {self.name!r}")


@dataclass(frozen=True)
class Sound:
    """A sound effect placed at a timeline position, on its own audio layer."""

    name: str
    source: str
    at: int
    duration: int
    gain_db: float = 0.0
    tag: str = ""

    def __post_init__(self) -> None:
        if self.at < 0 or self.duration <= 0:
            raise EditError(f"bad sound {self.name!r}")


@dataclass(frozen=True)
class Chapter:
    """A YouTube chapter, pinned to a frame of a source clip so it follows that moment through cuts and moves."""

    title: str
    source: str
    src_at: int

    def __post_init__(self) -> None:
        if not self.title.strip() or self.src_at < 0:
            raise EditError("a chapter needs a title and a time")


@dataclass(frozen=True)
class Music:
    """One music track under the whole edit. It plays through cuts; it does not move with them."""

    source: str
    start: float = 0.0      # seconds into the song where the edit begins
    gain_db: float = -21.0
    duck: bool = True       # lower it while someone is speaking

    def __post_init__(self) -> None:
        if self.start < 0 or not -60 <= self.gain_db <= 6:
            raise EditError("music: start is 0 or more seconds, gain runs from -60 to 6 dB")


@dataclass(frozen=True)
class EditList:
    fps: float
    segments: tuple[Segment, ...] = ()
    overlays: tuple[Overlay, ...] = field(default=())
    look: str = ""  # path of a .cube LUT applied to every main-track clip
    sounds: tuple[Sound, ...] = field(default=())
    fill: bool = False  # main-track clips are scaled to cover the frame, placed by each clip's framing
    music: Music | None = None
    format: str = ""  # a name from formats.py ("reel", "longform"); "" follows the house rule for frame
    chapters: tuple[Chapter, ...] = field(default=())

    # ---- construction -------------------------------------------------

    @classmethod
    def from_clip(cls, source: str, frames: int, fps: float) -> "EditList":
        """Start an edit from one whole source clip."""
        return cls(fps=fps, segments=(Segment(source, 0, frames),))

    @classmethod
    def from_dict(cls, data: dict) -> "EditList":
        return cls(
            fps=float(data["fps"]),
            segments=tuple(Segment(**s) for s in data.get("segments", [])),
            overlays=tuple(Overlay(**o) for o in data.get("overlays", [])),
            look=data.get("look", ""),
            sounds=tuple(Sound(**x) for x in data.get("sounds", [])),
            fill=bool(data.get("fill", False)),
            music=Music(**data["music"]) if data.get("music") else None,
            format=data.get("format", ""),
            chapters=tuple(Chapter(**c) for c in data.get("chapters", [])),
        )

    def to_dict(self) -> dict:
        return {
            "fps": self.fps,
            "segments": [asdict(s) for s in self.segments],
            "overlays": [asdict(o) for o in self.overlays],
            "look": self.look,
            "sounds": [asdict(x) for x in self.sounds],
            "fill": self.fill,
            "music": asdict(self.music) if self.music else None,
            "format": self.format,
            "chapters": [asdict(c) for c in self.chapters],
        }

    # ---- reading ------------------------------------------------------

    @property
    def duration(self) -> int:
        return sum(s.duration for s in self.segments)

    def pieces(self) -> list[tuple[int, Segment]]:
        """Each main-track segment with its timeline start frame."""
        out, t = [], 0
        for seg in self.segments:
            out.append((t, seg))
            t += seg.duration
        return out

    def timeline_ranges_for_source(self, source: str, src_in: int, src_out: int) -> list[tuple[int, int]]:
        """Where a range of a source clip currently sits on the timeline.

        A source range can appear zero times (already cut), once, or several
        times (split up or reordered), so this returns a list.
        """
        out = []
        for start, seg in self.pieces():
            if seg.source != source:
                continue
            lo, hi = max(src_in, seg.src_in), min(src_out, seg.src_out)
            if lo < hi:
                out.append((start + lo - seg.src_in, start + hi - seg.src_in))
        return out

    # ---- operations ---------------------------------------------------

    def split_at(self, t: int) -> "EditList":
        """Make sure a cut point exists at timeline frame t. Changes nothing visible."""
        if t <= 0 or t >= self.duration:
            return self
        new = []
        for start, seg in self.pieces():
            if start < t < start + seg.duration:
                mid = seg.src_in + (t - start)
                new += [replace(seg, src_out=mid), replace(seg, src_in=mid)]
            else:
                new.append(seg)
        return replace(self, segments=tuple(new))

    def remove_range(self, t0: int, t1: int) -> "EditList":
        """Cut timeline frames [t0, t1) and close the gap."""
        t0, t1 = self._check_range(t0, t1)
        cut = self.split_at(t0).split_at(t1)
        keep = [(s, seg) for s, seg in cut.pieces() if not (s >= t0 and s + seg.duration <= t1)]
        if not keep:
            raise EditError("that would remove the whole edit")
        return cut._reassemble(keep)

    def remove_ranges(self, ranges: list[tuple[int, int]]) -> "EditList":
        """Cut several timeline ranges at once (given in current timeline frames)."""
        edit = self
        for t0, t1 in sorted(_merge(ranges), reverse=True):
            edit = edit.remove_range(t0, t1)
        return edit

    def move_range(self, t0: int, t1: int, to: int) -> "EditList":
        """Move timeline frames [t0, t1) so they start at the point that is now frame `to`."""
        t0, t1 = self._check_range(t0, t1)
        if t0 < to < t1:
            raise EditError("cannot move a section into the middle of itself")
        to = max(0, min(to, self.duration))
        cut = self.split_at(t0).split_at(t1).split_at(to)
        moved = [p for p in cut.pieces() if t0 <= p[0] < t1]
        rest = [p for p in cut.pieces() if not (t0 <= p[0] < t1)]
        idx = next((i for i, p in enumerate(rest) if p[0] >= to), len(rest))
        return cut._reassemble(rest[:idx] + moved + rest[idx:])

    def swap_ranges(self, a0: int, a1: int, b0: int, b1: int) -> "EditList":
        """Swap two sections of the timeline that do not overlap."""
        (a0, a1), (b0, b1) = sorted([self._check_range(a0, a1), self._check_range(b0, b1)])
        if a1 > b0:
            raise EditError("the two sections overlap")
        cut = self
        for t in (a0, a1, b0, b1):
            cut = cut.split_at(t)
        ps = cut.pieces()
        pick = lambda lo, hi: [p for p in ps if lo <= p[0] < hi]  # noqa: E731
        order = pick(0, a0) + pick(b0, b1) + pick(a1, b0) + pick(a0, a1) + pick(b1, cut.duration)
        return cut._reassemble(order)

    def insert_segment(self, segment: Segment, at: int | None = None) -> "EditList":
        """Put another stretch of footage on the main track at timeline frame `at` (default: the end).

        Everything after it moves later, along with its overlays and sounds.
        """
        at = self.duration if at is None else at
        if not 0 <= at <= self.duration:
            raise EditError("that position is outside the edit")
        cut = self.split_at(at)
        ps = cut.pieces()
        new_piece = (-10 ** 12, segment)  # a start no overlay can sit on
        order = [p for p in ps if p[0] < at] + [new_piece] + [p for p in ps if p[0] >= at]
        return cut._reassemble(order)

    def cut_near(self, t: int, within: int | None = None) -> int:
        """The index of the piece that starts at the cut nearest timeline frame `t`."""
        cuts = [(start, n) for n, (start, _) in enumerate(self.pieces()) if n > 0]
        if not cuts:
            raise EditError("there is no cut in this edit yet")
        start, n = min(cuts, key=lambda c: abs(c[0] - t))
        within = round(self.fps) if within is None else within
        if abs(start - t) > within:
            raise EditError(f"no cut within {within} frames of there; the nearest is at frame {start}")
        return n

    def split_edit(self, t: int, shift: int) -> "EditList":
        """Make the cut nearest `t` a J-cut (shift < 0), an L-cut (shift > 0) or a straight cut (0)."""
        n = self.cut_near(t)
        prev, seg = self.segments[n - 1], self.segments[n]
        room = min(prev.duration, seg.duration) - 1
        if abs(shift) > room:
            raise EditError(f"the pieces either side of that cut only allow {room} frames")
        if shift < 0 and seg.src_in + shift < 0:
            raise EditError(f"the clip has only {seg.src_in} frames before that point to lead in with")
        segments = list(self.segments)
        segments[n] = replace(seg, audio_shift=shift)
        return replace(self, segments=tuple(segments))

    def audio_ranges(self) -> list[tuple[str, int, int]]:
        """For each piece, the source frames its sound comes from. The lengths add up to the edit's length."""
        shifts = self.audio_shifts()
        return [(seg.source, seg.src_in + shifts[n], seg.src_out + shifts[n + 1])
                for n, seg in enumerate(self.segments)]

    def audio_shifts(self) -> list[int]:
        """The shift in force at each cut, one more entry than pieces (0 at both ends), kept within what fits."""
        out = [0]
        for n in range(1, len(self.segments)):
            prev, seg = self.segments[n - 1], self.segments[n]
            room = min(prev.duration, seg.duration) - 1
            shift = max(-room, min(room, seg.audio_shift))
            out.append(max(shift, -seg.src_in))
        return out + [0]

    @property
    def has_split_edits(self) -> bool:
        return any(self.audio_shifts())

    def sources(self) -> list[str]:
        """Every source file on the main track, in order of first use."""
        return list(dict.fromkeys(s.source for s in self.segments))

    def add_overlay(self, overlay: Overlay) -> "EditList":
        if any(o.name == overlay.name for o in self.overlays):
            raise EditError(f"an overlay named {overlay.name!r} already exists")
        if overlay.at >= self.duration:
            raise EditError("that position is past the end of the edit")
        return replace(self, overlays=self.overlays + (overlay,))

    def add_sound(self, sound: Sound) -> "EditList":
        if any(x.name == sound.name for x in self.sounds):
            raise EditError(f"a sound named {sound.name!r} already exists")
        if sound.at >= self.duration:
            raise EditError("that position is past the end of the edit")
        return replace(self, sounds=self.sounds + (sound,))

    def remove_sounds(self, prefix: str = "") -> "EditList":
        """Remove the sound with this name, or every sound whose name starts with it ("" for all)."""
        keep = tuple(x for x in self.sounds if not x.name.startswith(prefix))
        if len(keep) == len(self.sounds):
            raise EditError(f"no sound named {prefix!r}" if prefix else "there are no sounds")
        return replace(self, sounds=keep)

    def reframe(self, t0: int, t1: int, x: float | None = None, y: float | None = None,
                zoom: float | None = None) -> "EditList":
        """Set the framing of timeline frames [t0, t1). Values left as None are kept. Nothing moves."""
        t0, t1 = self._check_range(t0, t1)
        cut = self.split_at(t0).split_at(t1)
        new = []
        for start, seg in cut.pieces():
            if t0 <= start < t1:
                seg = replace(seg, x=seg.x if x is None else round(x, 4), y=seg.y if y is None else round(y, 4),
                              zoom=seg.zoom if zoom is None else round(zoom, 4))
            new.append(seg)
        return replace(cut, segments=_join(new), fill=True)

    def set_music(self, music: Music | None) -> "EditList":
        """Put a music track under the edit, or None to take it off."""
        return replace(self, music=music)

    def set_look(self, path: str) -> "EditList":
        """Use a LUT file on the main track, or "" for none."""
        return replace(self, look=path)

    def remove_overlay(self, name: str) -> "EditList":
        if not any(o.name == name for o in self.overlays):
            raise EditError(f"no overlay named {name!r}")
        return replace(self, overlays=tuple(o for o in self.overlays if o.name != name))

    # ---- internals ----------------------------------------------------

    def _check_range(self, t0: int, t1: int) -> tuple[int, int]:
        t0, t1 = max(0, t0), min(t1, self.duration)
        if t0 >= t1:
            raise EditError("empty range: the start must be before the end, inside the edit")
        return t0, t1

    # ---- chapters -----------------------------------------------------

    def source_at(self, t: int) -> tuple[str, int]:
        """The source clip and source frame shown at timeline frame t."""
        for start, seg in self.pieces():
            if start <= t < start + seg.duration:
                return seg.source, seg.src_in + (t - start)
        raise EditError(f"frame {t} is past the end of the edit")

    def chapter_times(self) -> list[tuple[int | None, Chapter]]:
        """Each chapter with its timeline frame now (None if its moment was cut), in timeline order."""
        out = []
        for c in self.chapters:
            hits = self.timeline_ranges_for_source(c.source, c.src_at, c.src_at + 1)
            out.append((hits[0][0] if hits else None, c))
        return sorted(out, key=lambda p: (p[0] is None, p[0] or 0))

    def add_chapter(self, title: str, t: int) -> "EditList":
        """Start a chapter at timeline frame t. A chapter already at that moment is renamed."""
        source, at = self.source_at(t)
        keep = tuple(c for c in self.chapters if (c.source, c.src_at) != (source, at)
                     and c.title.strip().lower() != title.strip().lower())
        return replace(self, chapters=keep + (Chapter(title.strip(), source, at),))

    def remove_chapter(self, title: str) -> "EditList":
        keep = tuple(c for c in self.chapters if c.title.strip().lower() != title.strip().lower())
        if len(keep) == len(self.chapters):
            raise EditError(f"no chapter called {title!r}")
        return replace(self, chapters=keep)

    def set_format(self, name: str) -> "EditList":
        return replace(self, format=name)

    def _reassemble(self, order: list[tuple[int, Segment]]) -> "EditList":
        """Build a new edit from this edit's pieces in a new order.

        Overlays and sounds follow the piece they started on, keeping their
        offset into it. One whose piece was removed is removed with it.
        """
        new_start, t = {}, 0
        for old_start, seg in order:
            new_start[old_start] = t
            t += seg.duration
        durations = {old: seg.duration for old, seg in order}
        overlays = []
        for o in self.overlays:
            for old, new in new_start.items():
                if old <= o.at < old + durations[old]:
                    overlays.append(replace(o, at=new + (o.at - old)))
                    break
        sounds = []
        for x in self.sounds:
            for old, new in new_start.items():
                if old <= x.at < old + durations[old]:
                    sounds.append(replace(x, at=new + (x.at - old)))
                    break
        return replace(self, segments=_join([seg for _, seg in order]), overlays=tuple(overlays),
                       sounds=tuple(sounds))


def _join(segments: list[Segment]) -> tuple[Segment, ...]:
    """Merge neighbours that are one continuous run of the same source."""
    out: list[Segment] = []
    for seg in segments:
        prev = out[-1] if out else None
        if prev and prev.source == seg.source and prev.src_out == seg.src_in and prev.note == seg.note \
                and prev.framing == seg.framing:
            out[-1] = replace(prev, src_out=seg.src_out)      # one continuous run: a split edit here means nothing
        else:
            out.append(seg)
    if out and out[0].audio_shift:
        out[0] = replace(out[0], audio_shift=0)               # nothing comes before the first piece
    return tuple(out)


def _merge(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for lo, hi in sorted(ranges):
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out


# ---- time helpers -----------------------------------------------------


def parse_time(text: str | int | float, fps: float) -> int:
    """Turn a spoken-style time into a frame number.

    Accepts seconds ("83.5"), minutes and seconds ("1:23.5"), hours
    ("1:02:03.5"), a frame count ("120f"), or timecode with frames
    ("00:01:23:12").
    """
    if isinstance(text, (int, float)):
        return round(float(text) * fps)
    text = text.strip()
    try:
        if text.lower().endswith("f"):
            return int(text[:-1])
        parts = text.split(":")
        if len(parts) == 4:
            h, m, s, f = (int(p) for p in parts)
            return round((h * 3600 + m * 60 + s) * fps) + f
        if len(parts) > 4:
            raise ValueError
        seconds = 0.0
        for p in parts:
            seconds = seconds * 60 + float(p)
    except ValueError:
        raise EditError(f"cannot read {text!r} as a time") from None
    return round(seconds * fps)


def format_time(frame: int, fps: float) -> str:
    seconds = frame / fps
    m, s = divmod(seconds, 60)
    h, m = divmod(int(m), 60)
    return f"{h}:{m:02d}:{s:05.2f}" if h else f"{m}:{s:05.2f}"
