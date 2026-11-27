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

    def __post_init__(self) -> None:
        if self.src_in < 0 or self.src_out <= self.src_in:
            raise EditError(f"bad source range {self.src_in}..{self.src_out} for {self.source}")

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
class EditList:
    fps: float
    segments: tuple[Segment, ...] = ()
    overlays: tuple[Overlay, ...] = field(default=())
    look: str = ""  # path of a .cube LUT applied to every main-track clip

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
        )

    def to_dict(self) -> dict:
        return {
            "fps": self.fps,
            "segments": [asdict(s) for s in self.segments],
            "overlays": [asdict(o) for o in self.overlays],
            "look": self.look,
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

    def add_overlay(self, overlay: Overlay) -> "EditList":
        if any(o.name == overlay.name for o in self.overlays):
            raise EditError(f"an overlay named {overlay.name!r} already exists")
        if overlay.at >= self.duration:
            raise EditError("that position is past the end of the edit")
        return replace(self, overlays=self.overlays + (overlay,))

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

    def _reassemble(self, order: list[tuple[int, Segment]]) -> "EditList":
        """Build a new edit from this edit's pieces in a new order.

        Overlays follow the piece they started on, keeping their offset into
        it. An overlay whose piece was removed is removed with it.
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
        return replace(self, segments=_join([seg for _, seg in order]), overlays=tuple(overlays))


def _join(segments: list[Segment]) -> tuple[Segment, ...]:
    """Merge neighbours that are one continuous run of the same source."""
    out: list[Segment] = []
    for seg in segments:
        prev = out[-1] if out else None
        if prev and prev.source == seg.source and prev.src_out == seg.src_in and prev.note == seg.note:
            out[-1] = replace(prev, src_out=seg.src_out)
        else:
            out.append(seg)
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
