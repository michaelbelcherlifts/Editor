"""Build an EditList in DaVinci Resolve as a brand new timeline.

Nothing existing is touched: each build makes a new timeline, so the previous
one is still there to go back to. After building, every clip is read back and
compared with what was asked for, because many Resolve scripting calls fail
without raising an error.

NOT YET RUN AGAINST A REAL RESOLVE. Written from the scripting README and
tested against a stand-in. One detail the README does not state is whether
`endFrame` in a clipInfo is inclusive; `build_timeline` works that out on the
first build by reading the result back, and retries the other way if needed.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

from .edl import EditError, EditList

MAC_API = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
MAC_LIB = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"


def connect():
    """Connect to the running Resolve Studio (needs External scripting set to Local)."""
    os.environ.setdefault("RESOLVE_SCRIPT_API", MAC_API)
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", MAC_LIB)
    modules = os.path.join(os.environ["RESOLVE_SCRIPT_API"], "Modules")
    if modules not in sys.path:
        sys.path.append(modules)
    try:
        import DaVinciResolveScript as dvr  # type: ignore
    except ImportError:
        raise EditError("Resolve's scripting module was not found; is DaVinci Resolve Studio installed?") from None
    resolve = dvr.scriptapp("Resolve")
    if resolve is None:
        raise EditError("could not reach Resolve; open it, open a project, and set "
                        "Preferences > System > General > External scripting to Local")
    return resolve


@dataclass
class BuildReport:
    timeline: str
    clips: int = 0
    overlays: int = 0
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def text(self) -> str:
        head = f"timeline {self.timeline!r}: {self.clips} clips, {self.overlays} overlays"
        if self.ok:
            return head + ", all checked"
        return head + "\n" + "\n".join(f"  problem: {p}" for p in self.problems)


def _walk(folder):
    for clip in folder.GetClipList() or []:
        yield clip
    for sub in folder.GetSubFolderList() or []:
        yield from _walk(sub)


def _media_items(media_pool, paths: set[str]) -> dict:
    """Find each file in the media pool, importing any that are missing."""
    found = {}
    for clip in _walk(media_pool.GetRootFolder()):
        path = clip.GetClipProperty("File Path")
        if path in paths:
            found.setdefault(path, clip)
    missing = sorted(paths - set(found))
    if missing:
        for clip in media_pool.ImportMedia(missing) or []:
            found.setdefault(clip.GetClipProperty("File Path"), clip)
    still = sorted(paths - set(found))
    if still:
        raise EditError("Resolve could not import: " + ", ".join(still))
    return found


def _unique_name(project, name: str) -> str:
    taken = {project.GetTimelineByIndex(i).GetName() for i in range(1, project.GetTimelineCount() + 1)}
    if name not in taken:
        return name
    n = 2
    while f"{name} ({n})" in taken:
        n += 1
    return f"{name} ({n})"


def _build_once(project, media_pool, edit: EditList, name: str, end_inclusive: bool):
    items = _media_items(media_pool, {s.source for s in edit.segments} | {o.source for o in edit.overlays})
    timeline = media_pool.CreateEmptyTimeline(name)
    if timeline is None:
        raise EditError(f"Resolve would not create a timeline named {name!r}")
    project.SetCurrentTimeline(timeline)
    origin = timeline.GetStartFrame()
    adj = 1 if end_inclusive else 0

    main = [{"mediaPoolItem": items[seg.source], "startFrame": seg.src_in, "endFrame": seg.src_out - adj,
             "trackIndex": 1, "recordFrame": origin + start}
            for start, seg in edit.pieces()]
    placed_main = media_pool.AppendToTimeline(main) or []

    placed_over = []
    for o in sorted(edit.overlays, key=lambda o: (o.track, o.at)):
        while timeline.GetTrackCount("video") < o.track:
            if not timeline.AddTrack("video"):
                raise EditError(f"Resolve would not add video track {o.track}")
        info = {"mediaPoolItem": items[o.source], "startFrame": o.src_in,
                "endFrame": o.src_in + o.duration - adj, "trackIndex": o.track,
                "recordFrame": origin + o.at, "mediaType": 1}
        placed_over += media_pool.AppendToTimeline([info]) or []
    return timeline, origin, placed_main, placed_over


def _check(timeline, origin: int, edit: EditList) -> tuple[list[str], set[int]]:
    """Compare what is on the timeline with the edit. Returns problems and the set of duration errors."""
    problems, deltas = [], set()
    got = sorted(timeline.GetItemListInTrack("video", 1) or [], key=lambda i: i.GetStart())
    want = edit.pieces()
    if len(got) != len(want):
        problems.append(f"main track has {len(got)} clips, expected {len(want)}")
    for n, (item, (start, seg)) in enumerate(zip(got, want), 1):
        d = item.GetDuration() - seg.duration
        if d:
            deltas.add(d)
            problems.append(f"clip {n} is {item.GetDuration()} frames, expected {seg.duration}")
        elif item.GetStart() != origin + start:
            problems.append(f"clip {n} starts at {item.GetStart() - origin}, expected {start}")
    by_track: dict[int, list] = {}
    for o in edit.overlays:
        by_track.setdefault(o.track, []).append(o)
    for track, wanted in by_track.items():
        starts = {i.GetStart() - origin for i in timeline.GetItemListInTrack("video", track) or []}
        for o in wanted:
            if o.at not in starts:
                problems.append(f"overlay {o.name!r} is missing from V{track}")
    return problems, deltas


def build_timeline(resolve, edit: EditList, name: str, end_inclusive: bool | None = None) -> BuildReport:
    """Create a new timeline from the edit and verify it.

    end_inclusive: whether a clipInfo's endFrame is the last frame used (True)
    or one past it (False). Leave as None to detect it automatically.
    """
    if not edit.segments:
        raise EditError("the edit is empty")
    project = resolve.GetProjectManager().GetCurrentProject()
    if project is None:
        raise EditError("no project is open in Resolve")
    resolve.GetProjectManager().SaveProject()
    media_pool = project.GetMediaPool()
    fps = float(project.GetSetting("timelineFrameRate"))
    warn = []
    if abs(fps - edit.fps) > 0.01:
        warn.append(f"project is {fps:g} fps but the edit is {edit.fps:g} fps; timings will drift")

    modes = [True, False] if end_inclusive is None else [end_inclusive]
    for attempt, mode in enumerate(modes):
        final = _unique_name(project, name)
        timeline, origin, main, over = _build_once(project, media_pool, edit, final, mode)
        problems, deltas = _check(timeline, origin, edit)
        off_by_one = deltas in ({1}, {-1})
        if off_by_one and attempt + 1 < len(modes):
            media_pool.DeleteTimelines([timeline])  # wrong guess about endFrame; try the other way
            continue
        return BuildReport(final, len(main), len(over), warn + problems)
    raise AssertionError("unreachable")
