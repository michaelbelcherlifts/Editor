import pytest
from fake_resolve import Project, Resolve

from stylebrain.cli import main
from stylebrain.edl import EditError, EditList, Overlay, Segment, Sound
from stylebrain.resolve_builder import build_timeline
from stylebrain.store import Store


def test_insert_in_the_middle_moves_later_things_along():
    e = EditList.from_clip("/v/a.mov", 300, 30.0)
    e = e.add_overlay(Overlay("early", "/v/t.mov", 30, 10)).add_overlay(Overlay("late", "/v/t.mov", 200, 10))
    e = e.add_sound(Sound("s", "/s/pop.wav", 0, 3))
    new = e.insert_segment(Segment("/v/b.mov", 60, 120), at=100)
    assert [(s.source[-5:], s.src_in, s.src_out) for s in new.segments] == [("a.mov", 0, 100), ("b.mov", 60, 120), ("a.mov", 100, 300)]
    assert new.duration == 360
    assert {o.name: o.at for o in new.overlays} == {"early": 30, "late": 260}
    assert new.sounds[0].at == 0
    assert new.sources() == ["/v/a.mov", "/v/b.mov"]


def test_insert_at_the_end_and_bad_positions():
    e = EditList.from_clip("/v/a.mov", 90, 30.0)
    assert e.insert_segment(Segment("/v/b.mov", 0, 30)).segments[-1].source == "/v/b.mov"
    assert e.insert_segment(Segment("/v/b.mov", 0, 30), at=0).segments[0].source == "/v/b.mov"
    with pytest.raises(EditError):
        e.insert_segment(Segment("/v/b.mov", 0, 30), at=91)


def test_commands_build_a_two_camera_edit_with_broll(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["new", "p", "--source", "/v/a.mov", "--fps", "30", "--frames", "300"])
    main(["add-source", "/v/b.mov", "--fps", "30", "--frames", "600", "--from", "2", "--to", "4"])
    main(["add-source", "/v/c.mov", "--fps", "30", "--frames", "90", "--at", "5"])
    main(["broll", "/v/plates.mov", "--fps", "30", "--frames", "300", "--at", "1", "--from", "3", "--duration", "2"])
    edit = Store("p").load()
    assert edit.duration == 300 + 60 + 90
    assert [s.source[-5:] for s in edit.segments] == ["a.mov", "c.mov", "a.mov", "b.mov"]
    o = edit.overlays[0]
    assert (o.at, o.duration, o.src_in, o.track) == (30, 60, 90, 2)
    main(["sources"])
    out = capsys.readouterr().out
    assert "1. a.mov" in out and "above: plates.mov" in out
    main(["cut", "0", "2"])                      # a cut still works across sources and takes the b-roll piece with it
    assert Store("p").load().overlays == ()
    main(["undo"])
    with pytest.raises(SystemExit):
        main(["add-source", "/v/d.mov", "--fps", "24", "--frames", "100"])
    assert "24 fps but this edit is 30 fps" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(["add-source", "/v/b.mov", "--fps", "30", "--frames", "60", "--to", "9"])

    project = Project(fps="30")
    report = build_timeline(Resolve(project), Store("p").load(), "p")
    assert report.ok and (report.clips, report.overlays) == (4, 1)
    assert sorted(project.pool.imported) == ["/v/a.mov", "/v/b.mov", "/v/c.mov", "/v/plates.mov"]
