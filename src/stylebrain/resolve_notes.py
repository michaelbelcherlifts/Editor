"""Notes between Michael and the edit, kept on the Resolve timeline.

Three things, all read-only for his timelines except adding and removing our
own markers:

- his markers and playhead, as times on the edit ("here" means where he put a marker)
- review notes written back as markers he can step through in Resolve
- a snapshot of a timeline when it is built, so the next build can say what he
  changed by hand since, before those changes are left behind

Resolve cannot report colour grades, effects or keyframes to a script, so the
hand-change check sees clips, tracks, clip transforms and markers only.
"""

from __future__ import annotations

import json
from pathlib import Path

from .edl import EditError

OURS = "stylebrain"
COLOURS = {"opening": "Red", "hook": "Red", "dead_air": "Red", "slow_opener": "Red", "pace": "Yellow",
           "long_shot": "Yellow", "pause": "Blue", "picture": "Purple", "sound": "Green", "payoff": "Pink"}
TRANSFORMS = ("ZoomX", "ZoomY", "Pan", "Tilt", "RotationAngle", "CropLeft", "CropRight", "CropTop", "CropBottom",
              "FlipX", "FlipY")


def current(resolve):
    """The open project and its current timeline."""
    project = resolve.GetProjectManager().GetCurrentProject()
    if project is None:
        raise EditError("no project is open in Resolve")
    timeline = project.GetCurrentTimeline()
    if timeline is None:
        raise EditError("no timeline is open in Resolve")
    return project, timeline


def find_timeline(project, name: str):
    for i in range(1, project.GetTimelineCount() + 1):
        t = project.GetTimelineByIndex(i)
        if t.GetName() == name:
            return t
    return None


# -------------------------------------------------------------------- markers

def read_markers(timeline, fps: float) -> list[dict]:
    """Every marker on the timeline, in order: frame from the start, seconds, colour, name, note, length."""
    out = []
    for frame, m in sorted((timeline.GetMarkers() or {}).items(), key=lambda kv: float(kv[0])):
        frame = int(round(float(frame)))
        out.append({"frame": frame, "seconds": round(frame / fps, 3), "colour": m.get("color", ""),
                    "name": m.get("name", ""), "note": m.get("note", ""),
                    "frames": int(m.get("duration", 1) or 1), "ours": str(m.get("customData", "")).startswith(OURS)})
    return out


def playhead(timeline, fps: float) -> int | None:
    """Where the playhead is, in frames from the start of the timeline. None when it cannot be read."""
    try:
        text = timeline.GetCurrentTimecode()
        h, m, s, f = (int(p) for p in text.replace(";", ":").split(":"))
    except (AttributeError, TypeError, ValueError):
        return None
    frame = (h * 3600 + m * 60 + s) * round(fps) + f - timeline.GetStartFrame()
    return frame if frame >= 0 else None


def add_notes(timeline, notes: list[tuple[float | None, str, str]], fps: float) -> tuple[int, int]:
    """Write notes onto the timeline as markers: (seconds or None for overall, kind, text). Returns (placed, failed)."""
    placed = failed = 0
    used = {int(round(float(f))) for f in (timeline.GetMarkers() or {})}
    for at, kind, text in notes:
        frame = 0 if at is None else max(0, round(at * fps))
        while frame in used:                      # one marker per frame in Resolve
            frame += 1
        ok = timeline.AddMarker(frame, COLOURS.get(kind, "Cyan"), kind.replace("_", " "), text, 1, OURS)
        if ok:
            used.add(frame)
            placed += 1
        else:
            failed += 1
    return placed, failed


def clear_notes(timeline) -> int:
    """Remove the markers we wrote. His own markers are never touched."""
    n = 0
    for frame, m in list((timeline.GetMarkers() or {}).items()):
        if m.get("customData", "") == OURS and timeline.DeleteMarkerAtFrame(frame):
            n += 1
    return n


# ------------------------------------------------------- hand-change tracking

def snapshot(timeline) -> dict:
    """What a script can see of a timeline: clips on each track, clip transforms on video, his markers."""
    origin = timeline.GetStartFrame()
    out: dict = {"name": timeline.GetName(), "video": {}, "audio": {}}
    for kind in ("video", "audio"):
        for index in range(1, timeline.GetTrackCount(kind) + 1):
            items = sorted(timeline.GetItemListInTrack(kind, index) or [], key=lambda i: i.GetStart())
            rows = []
            for item in items:
                row = [item.GetStart() - origin, item.GetDuration()]
                if kind == "video" and hasattr(item, "GetProperty"):
                    row.append({k: item.GetProperty(k) for k in TRANSFORMS if item.GetProperty(k) not in (None, "")})
                rows.append(row)
            out[kind][str(index)] = rows
    marks = timeline.GetMarkers() or {}
    out["markers"] = sorted(int(round(float(f))) for f, m in marks.items() if not str(m.get("customData", "")).startswith(OURS))
    return out


def differences(built: dict, now: dict) -> list[str]:
    """What changed on a timeline between two snapshots, in plain lines."""
    lines = []
    for kind, letter in (("video", "V"), ("audio", "A")):
        was, got = built.get(kind, {}), now.get(kind, {})
        for index in sorted(set(was) | set(got), key=int):
            a, b = was.get(index), got.get(index)
            track = f"{letter}{index}"
            if a is None:
                if b:
                    lines.append(f"{track} is a new track with {len(b)} clip(s)")
                continue
            if b is None:
                lines.append(f"{track} was removed")
                continue
            if len(a) != len(b):
                lines.append(f"{track} has {len(b)} clip(s), it was built with {len(a)}")
                continue
            for n, (x, y) in enumerate(zip(a, b), 1):
                if x[1] != y[1]:
                    d = y[1] - x[1]
                    lines.append(f"{track} clip {n} is {abs(d)} frame(s) {'longer' if d > 0 else 'shorter'}")
                elif x[0] != y[0]:
                    lines.append(f"{track} clip {n} was moved by {y[0] - x[0]:+d} frame(s)")
                elif len(x) > 2 and len(y) > 2 and x[2] != y[2]:
                    lines.append(f"{track} clip {n} was resized, moved in the frame or cropped")
    added = len(set(now.get("markers", [])) - set(built.get("markers", [])))
    if added:
        lines.append(f"{added} marker(s) were added")
    return lines


def _record(store) -> Path:
    return Path(store.dir) / "built.json"


def remember_build(store, timeline, version: int) -> None:
    """Save what the freshly built timeline looks like, to compare against later."""
    _record(store).write_text(json.dumps({"version": version, **snapshot(timeline)}))


def hand_changes(project, store) -> tuple[str, list[str]]:
    """What he changed by hand on the last built timeline. Returns (its name, lines); ("", []) when unknown."""
    path = _record(store)
    if not path.exists():
        return "", []
    built = json.loads(path.read_text())
    timeline = find_timeline(project, built["name"])
    if timeline is None:
        return built["name"], []
    return built["name"], differences(built, snapshot(timeline))
