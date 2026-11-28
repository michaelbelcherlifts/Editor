import pytest
from fake_resolve import Clip, Folder, Project, Resolve

from stylebrain.edl import EditError, EditList, Overlay
from stylebrain.resolve_builder import build_timeline


def edit():
    e = EditList.from_clip("/v/a.mov", 1000, 24.0).remove_range(100, 300)
    return e.add_overlay(Overlay("title", "/v/t.mov", at=48, duration=24, track=3))


@pytest.mark.parametrize("inclusive", [True, False])
def test_builds_and_verifies_whichever_way_end_frame_works(inclusive):
    project = Project(end_inclusive=inclusive)
    resolve = Resolve(project)
    report = build_timeline(resolve, edit(), "cut v2")
    assert report.ok, report.text()
    assert (report.clips, report.overlays) == (2, 1)
    assert [t.name for t in project.timelines] == ["cut v2"]
    tl = project.timelines[0]
    assert [(i.start - 86400, i.duration) for i in tl.tracks[1]] == [(0, 100), (100, 700)]
    assert [(i.start - 86400, i.duration) for i in tl.tracks[3]] == [(48, 24)]
    assert resolve.saves == 1
    assert project.pool.deleted == ([] if inclusive else ["cut v2"])


def test_reuses_media_already_in_the_pool_even_in_subfolders():
    project = Project()
    project.pool.root = Folder(subs=[Folder(clips=[Clip("/v/a.mov")])])
    build_timeline(Resolve(project), edit(), "x")
    assert project.pool.imported == ["/v/t.mov"]


def test_never_overwrites_an_existing_timeline_name():
    project = Project()
    r = Resolve(project)
    names = [build_timeline(r, edit(), "cut").timeline for _ in range(3)]
    assert names == ["cut", "cut (2)", "cut (3)"]


def test_an_empty_project_is_set_to_the_edits_frame_rate():
    project = Project(fps="29.97")
    report = build_timeline(Resolve(project), edit(), "x")
    assert report.ok and project.fps == f"{edit().fps:g}"
    assert "note: the project had no timelines, so it was set from 29.97 to" in report.text()


def test_a_project_with_timelines_at_another_rate_is_refused_and_nothing_is_built():
    project = Project()
    r = Resolve(project)
    build_timeline(r, edit(), "first")
    project.fps = "29.97"                       # as if the project had been made at another rate
    with pytest.raises(EditError, match="Nothing was built"):
        build_timeline(r, edit(), "second")
    assert project.GetTimelineCount() == 1
    locked = Project(fps="29.97")
    locked.locked = True                        # Resolve refuses the change
    with pytest.raises(EditError, match="29.97 fps"):
        build_timeline(Resolve(locked), edit(), "x")
    assert locked.GetTimelineCount() == 0


def test_missing_media_is_an_error():
    with pytest.raises(EditError, match="could not import"):
        build_timeline(Resolve(Project(missing=["/v/t.mov"])), edit(), "x")


def test_forced_wrong_mode_is_reported_not_hidden():
    report = build_timeline(Resolve(Project(end_inclusive=False)), edit(), "x", end_inclusive=True)
    assert not report.ok and "expected 100" in report.text()


def test_split_edits_place_picture_and_sound_apart():
    project = Project()
    e = EditList.from_clip("/v/a.mov", 1000, 24.0).remove_range(100, 300).split_edit(100, -6)
    report = build_timeline(Resolve(project), e, "j")
    assert report.ok, report.text()
    tl = project.timelines[0]
    assert [(i.start - 86400, i.duration) for i in tl.tracks[1]] == [(0, 100), (100, 700)]
    assert [(i.start - 86400, i.duration) for i in tl.audio[1]] == [(0, 94), (94, 706)]
