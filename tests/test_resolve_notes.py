import json

import pytest
from fake_resolve import Item, Project, Resolve

from stylebrain import resolve_builder
from stylebrain import resolve_notes as notes
from stylebrain.cli import main
from stylebrain.edl import EditError, EditList
from stylebrain.resolve_builder import build_timeline
from stylebrain.store import Store


@pytest.fixture
def studio(tmp_path, monkeypatch):
    """A project with one built timeline, and Resolve reachable from the commands."""
    monkeypatch.chdir(tmp_path)
    project = Project(fps="30")
    monkeypatch.setattr(resolve_builder, "connect", lambda: Resolve(project))
    main(["new", "p", "--source", "/v/a.mov", "--fps", "30", "--frames", "300"])
    main(["cut", "2", "3"])
    main(["build"])
    return project


def test_his_markers_and_playhead_are_read_as_edit_times(studio, capsys):
    t = studio.current
    t.AddMarker(45, "Blue", "Marker 1", "cut from here", 1)
    t.AddMarker(120, "Blue", "Marker 2", "", 30)
    t.timecode = "00:48:02:15"                              # the stand-in starts at frame 86400, which is 00:48:00:00 at 30 fps
    assert notes.playhead(t, 30.0) == 75
    capsys.readouterr()
    main(["markers"])
    out = capsys.readouterr().out
    assert "playhead: 0:02.50" in out and "0:01.50  Blue     cut from here" in out
    assert "0:04.00 for 0:01.00  Blue" in out and "note:" not in out
    main(["markers", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert [m["frame"] for m in data["markers"]] == [45, 120] and data["playhead"] == 75


def test_stale_timeline_is_called_out(studio, capsys):
    main(["cut", "0", "1"])                                 # the edit moves on; the open timeline is now old
    capsys.readouterr()
    main(["markers"])
    assert "not a build of version 3" in capsys.readouterr().out


def test_review_notes_go_on_as_markers_and_come_off_without_touching_his(studio, capsys):
    t = studio.current
    t.AddMarker(0, "Blue", "Marker 1", "mine", 1)
    placed, failed = notes.add_notes(t, [(None, "pace", "slower than the style"), (0.0, "opening", "starts on dead air"),
                                         (4.0, "long_shot", "an 8s shot")], 30.0)
    assert (placed, failed) == (3, 0)
    ours = [m for m in notes.read_markers(t, 30.0) if m["ours"]]
    assert [m["frame"] for m in ours] == [1, 2, 120]        # frame 0 was his, so ours step aside
    assert ours[1]["colour"] == "Red" and ours[2]["name"] == "long shot"
    capsys.readouterr()
    main(["markers"])
    assert "slower than the style" not in capsys.readouterr().out     # his view shows his markers only
    main(["markers", "--clear"])
    assert "removed 3 review marker(s)" in capsys.readouterr().out
    assert [m["note"] for m in notes.read_markers(t, 30.0)] == ["mine"]


def test_rebuild_warns_about_hand_changes_and_leaves_his_timeline(studio, capsys):
    first = studio.current
    assert json.loads((Store("p").dir / "built.json").read_text())["name"] == "p v2"
    capsys.readouterr()
    main(["build", "--name", "again"])
    assert "changed by hand" not in capsys.readouterr().out            # nothing was touched

    # He trims a clip, adds a title on V2, resizes a clip and drops a marker on the latest build.
    latest = studio.current
    latest.tracks[1][0].duration -= 12
    latest.tracks[1][1].props["ZoomX"] = 1.2
    latest.AddTrack("video")
    latest.tracks[2].append(Item(latest.GetStartFrame() + 30, 60))
    latest.AddMarker(50, "Blue", "Marker 1", "", 1)
    notes.add_notes(latest, [(1.0, "pace", "ours do not count")], 30.0)
    main(["cut", "0", "0.5"])
    main(["build"])
    out = capsys.readouterr().out
    assert "warning: 'again' was changed by hand" in out
    for line in ("V1 clip 1 is 12 frame(s) shorter", "V1 clip 2 was resized, moved in the frame or cropped",
                 "V2 is a new track with 1 clip(s)", "1 marker(s) were added", "will NOT have these changes"):
        assert line in out, line
    assert latest in studio.timelines and first in studio.timelines   # nothing of his was removed
    assert studio.current.GetName() == "p v3"


def test_differences_in_plain_words():
    a = {"video": {"1": [[0, 100], [100, 50]]}, "audio": {"1": [[0, 150]], "2": [[0, 150]]}, "markers": []}
    b = {"video": {"1": [[0, 100], [110, 50]]}, "audio": {"1": [[0, 150]]}, "markers": []}
    assert notes.differences(a, b) == ["V1 clip 2 was moved by +10 frame(s)", "A2 was removed"]
    assert notes.differences(a, a) == []
    assert notes.differences(a, {**a, "video": {"1": [[0, 100]]}}) == ["V1 has 1 clip(s), it was built with 2"]


def test_no_open_timeline_is_an_error_not_a_crash():
    project = Project()
    with pytest.raises(EditError, match="no timeline is open"):
        notes.current(Resolve(project))
    assert build_timeline(Resolve(project), EditList.from_clip("/v/a.mov", 48, 24.0), "t").ok
    assert notes.playhead(type("T", (), {})(), 24.0) is None
