import json
import shutil

import pytest
from fake_resolve import Project, Resolve

np = pytest.importorskip("numpy")
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

from stylebrain import export, media, reframe  # noqa: E402
from stylebrain.cli import main  # noqa: E402
from stylebrain.edl import EditError, EditList, Segment  # noqa: E402
from stylebrain.resolve_builder import build_timeline  # noqa: E402
from stylebrain.store import Store  # noqa: E402


@pytest.fixture(scope="module")
def wide(tmp_path_factory):
    """A wide grey clip with a white box that jiggles on the left for 3s, then on the right for 3s."""
    out = tmp_path_factory.mktemp("reframe") / "wide.mp4"
    graph = ("color=c=0x404040:s=640x360:r=30:d=6[bg];color=c=white:s=40x90:r=30:d=6[b];"
             "[bg][b]overlay=x='if(lt(t,3),120,500)+12*sin(12*t)':y='130+6*sin(9*t)'")
    media.run(["ffmpeg", "-v", "error", "-y", "-filter_complex", graph, "-pix_fmt", "yuv420p", str(out)])
    return str(out)


def test_geometry_for_wide_footage_in_a_vertical_frame():
    g = reframe.geometry(1920, 1080, 1080, 1920)
    assert g["scale"] == pytest.approx(1920 / 1080) and g["zoom"] == pytest.approx(3.1605, abs=1e-3)
    assert g["pan"] == pytest.approx(0) and g["window"][0] == pytest.approx(0.3164, abs=1e-3)
    left = reframe.geometry(1920, 1080, 1080, 1920, x=0.0)
    assert left["left"] == 0 and left["pan"] == pytest.approx((1920 * 1920 / 1080 - 1080) / 2)   # picture slides right
    same = reframe.geometry(1080, 1920, 1080, 1920, x=0.2)
    assert same["zoom"] == pytest.approx(1) and same["pan"] == pytest.approx(0)                   # nothing to choose
    punch = reframe.geometry(1080, 1920, 1080, 1920, y=0.25, zoom=1.5)
    assert punch["zoom"] == pytest.approx(1.5) and punch["tilt"] < 0                              # looks higher up


def test_framing_lives_on_clips_and_follows_them():
    e = EditList.from_clip("/v/a.mov", 300, 30.0)
    assert not e.fill
    r = e.reframe(90, 180, x=0.3, zoom=1.2)
    assert r.fill and [(s.src_in, s.src_out, s.x, s.zoom) for s in r.segments] == [
        (0, 90, 0.5, 1.0), (90, 180, 0.3, 1.2), (180, 300, 0.5, 1.0)]
    assert r.reframe(0, 300, x=0.3, zoom=1.2).segments == (Segment("/v/a.mov", 0, 300, "", 0.3, 0.5, 1.2),)
    moved = r.move_range(90, 180, 0)
    assert moved.segments[0].framing == (0.3, 0.5, 1.2) and moved.duration == 300
    assert r.remove_range(100, 120).segments[1].framing == (0.3, 0.5, 1.2)
    assert EditList.from_dict(json.loads(json.dumps(r.to_dict()))) == r
    old = EditList.from_dict({"fps": 30, "segments": [{"source": "x", "src_in": 0, "src_out": 9}]})
    assert old.segments[0].framing == (0.5, 0.5, 1.0) and not old.fill
    with pytest.raises(EditError, match="framing"):
        e.reframe(0, 10, x=1.4)


def test_subject_is_found_from_movement_and_faces(wide, monkeypatch):
    monkeypatch.setattr(reframe, "_faces", lambda grey: None)
    left = reframe.subject(reframe.track(wide, 0.2, 2.8))
    right = reframe.subject(reframe.track(wide, 3.2, 5.8))
    assert left.method == right.method == "motion"
    assert left.x == pytest.approx(140 / 640, abs=0.05) and right.x == pytest.approx(520 / 640, abs=0.05)
    assert reframe.subject([]).method == "centre"
    monkeypatch.setattr(reframe, "_faces", lambda grey: (0.7, 0.3))
    face = reframe.subject(reframe.track(wide, 0.2, 2.8))
    assert (face.method, face.x, face.y) == ("face", pytest.approx(0.7), pytest.approx(0.3))


def test_plan_keeps_the_subject_in_a_vertical_frame(wide, tmp_path, monkeypatch):
    monkeypatch.setattr(reframe, "_faces", lambda grey: None)
    # Three jump cuts while the box is on the left, then one clip with it on the right.
    edit = EditList(30.0, (Segment(wide, 6, 30), Segment(wide, 36, 60), Segment(wide, 66, 84), Segment(wide, 96, 174)))
    new, lines = reframe.plan(edit, 180, 320)
    xs = [s.x for s in new.segments]
    assert len(set(xs[:3])) == 1 and xs[0] < 0.35 < 0.65 < xs[3]         # jump cuts share one framing
    assert len(lines) == 2 and "(motion)" in lines[0]
    out = export.render(new, tmp_path / "v.mp4", 180, 320)
    for t in (0.5, 1.5, 3.0):
        frame = media.read_frame(str(out), t)
        assert (frame.mean(axis=2) > 200).mean() > 0.01, f"the subject is out of frame at {t}s"
    centre = export.render(edit, tmp_path / "c.mp4", 180, 320)
    assert (media.read_frame(str(centre), 0.5).mean(axis=2) > 200).mean() < 0.001   # a centre crop loses it
    sheet = reframe.preview(new, tmp_path / "sheet.jpg", 180, 320)
    assert media.info(str(sheet)).width == 270 * 2

    whole = EditList.from_clip(wide, 180, 30.0)
    _, lines = reframe.plan(whole, 180, 320)
    assert "warning" in lines[0] and "ranges over" in lines[0]            # one clip, subject on both sides


def test_upright_footage_needs_no_reframing_and_phone_rotation_is_read(tmp_path):
    tall = tmp_path / "tall.mp4"
    media.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=180x320:r=30:d=1", "-pix_fmt", "yuv420p", str(tall)])
    edit, lines = reframe.plan(EditList.from_clip(str(tall), 30, 30.0), 1080, 1920)
    assert "already fits" in lines[0] and not edit.fill
    side = tmp_path / "phone.mp4"
    lying = tmp_path / "lying.mp4"
    media.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=30:d=1", "-pix_fmt", "yuv420p", str(lying)])
    media.run(["ffmpeg", "-v", "error", "-display_rotation", "90", "-i", str(lying), "-c", "copy", str(side)])
    i = media.info(str(side))
    assert (i.width, i.height) == (180, 320)
    assert media.read_frame(str(side), 0.2).shape == (320, 180, 3)


def test_resolve_gets_zoom_and_pan_only_when_reframed():
    edit = EditList.from_clip("/v/a.mov", 240, 24.0)
    plain = Project()
    assert build_timeline(Resolve(plain), edit, "t").ok
    assert plain.timelines[-1].tracks[1][0].props == {}
    framed = Project()
    report = build_timeline(Resolve(framed), edit.reframe(0, 120, x=0.25), "t")
    assert report.ok, report.text()
    a, b = framed.timelines[-1].tracks[1]
    assert a.props["ZoomX"] == a.props["ZoomY"] == pytest.approx(3.1605, abs=1e-3) and a.props["Pan"] > 0
    assert b.props["ZoomX"] == pytest.approx(3.1605, abs=1e-3) and b.props["Pan"] == 0 and b.props["Tilt"] == 0


def test_reframe_command(wide, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(reframe, "_faces", lambda grey: None)
    main(["new", "p", "--source", wide])
    main(["cut", "2.8", "3.2"])
    main(["reframe", "--auto", "--size", "180x320"])
    out = capsys.readouterr().out
    assert "(motion)" in out and "frames to look at" in out
    main(["reframe", "--from", "0", "--to", "1", "--zoom", "1.3", "--no-preview"])
    main(["show"])
    assert "zoom 1.3" in capsys.readouterr().out
    segs = Store("p").load().segments
    assert segs[0].zoom == 1.3 and segs[0].x == segs[1].x < 0.35 and segs[-1].x > 0.65
    with pytest.raises(SystemExit):
        main(["reframe"])


def test_a_punch_in_counts_as_a_zoom_for_sounds(tmp_path, monkeypatch):
    from stylebrain import sfx
    monkeypatch.chdir(tmp_path)
    sfx.make_basics()
    edit = EditList.from_clip("/v/a.mov", 300, 30.0).reframe(90, 180, zoom=1.2)
    _, lines = sfx.auto_place(edit, on=("zooms", "cuts"), min_cut_gap=0.5)
    assert [ln.split()[1:4] for ln in lines] == [["whoosh", "on", "zoom"], ["whoosh", "on", "cut"]]


def test_a_clip_holding_two_shots_is_split_at_the_cut(tmp_path, monkeypatch):
    monkeypatch.setattr(reframe, "_faces", lambda grey: None)
    out = tmp_path / "two.mp4"
    graph = ("color=c=0x303030:s=640x360:r=30:d=3[a];color=c=0x8090c0:s=640x360:r=30:d=3[b];"
             "color=c=white:s=40x90:r=30:d=6,split[w1][w2];"
             "[a][w1]overlay=x='110+12*sin(12*t)':y=130:shortest=1[s1];"
             "[b][w2]overlay=x='500+12*sin(12*t)':y=130:shortest=1[s2];[s1][s2]concat=n=2[o]")
    media.run(["ffmpeg", "-v", "error", "-y", "-filter_complex", graph, "-map", "[o]", "-pix_fmt", "yuv420p", str(out)])
    samples = reframe.track(str(out), 0, 6)
    assert reframe.shot_changes(str(out), samples, 30.0) == [90]
    new, lines = reframe.plan(EditList.from_clip(str(out), 180, 30.0), 180, 320)
    assert [(s.src_in, s.src_out) for s in new.segments] == [(0, 90), (90, 180)]
    assert new.segments[0].x < 0.35 < 0.65 < new.segments[1].x and len(lines) == 2
    assert not any("warning" in ln for ln in lines)


def test_face_height_is_kept_for_later_punch_ins(wide, monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(reframe, "_faces", lambda grey: (0.4, 0.22))
    new, lines = reframe.plan(EditList.from_clip(wide, 80, 30.0), 180, 320)
    assert new.segments[0].y == pytest.approx(0.22) and "(face)" in lines[0]
    g = reframe.geometry(640, 360, 180, 320, *new.reframe(0, 80, zoom=1.2).segments[0].framing)
    assert g["top"] == 0                                    # the punch-in keeps the top of the picture, where his head is
    monkeypatch.chdir(tmp_path)
    main(["new", "q", "--source", "/v/a.mov", "--fps", "30", "--frames", "300"])
    main(["reframe", "--zoom", "1.2", "--no-preview"])
    assert "add --y 0.4" in capsys.readouterr().out
