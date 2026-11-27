import shutil

import pytest
from fake_resolve import Item, Project, Resolve

np = pytest.importorskip("numpy")
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

from stylebrain import look, media, style  # noqa: E402
from stylebrain.cli import main  # noqa: E402
from stylebrain.edl import EditError, EditList  # noqa: E402
from stylebrain.resolve_builder import build_timeline  # noqa: E402


@pytest.fixture(scope="module")
def clips(tmp_path_factory):
    d = tmp_path_factory.mktemp("look")
    mine, ref = d / "mine.mp4", d / "ref.mp4"
    src = "testsrc2=s=320x180:r=10:d=2"
    media.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", src, "-pix_fmt", "yuv420p", str(mine)])
    # The reference: the same picture graded warm, darker and lower in contrast.
    media.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", src, "-vf",
               "colorchannelmixer=rr=0.95:bb=0.6,eq=contrast=0.8:brightness=-0.05",
               "-pix_fmt", "yuv420p", str(ref)])
    return str(mine), str(ref)


def test_identity_curves_when_matching_a_clip_to_itself(clips):
    px = look._pixels(clips[0], 8)
    c = look.curves(px, px)
    assert np.abs(c - np.arange(256) / 255.0).max() < 0.03


def test_cube_file_shape(tmp_path):
    ident = np.tile(np.arange(256) / 255.0, (3, 1))
    path = look.write_cube(tmp_path / "id.cube", ident, size=5)
    lines = [ln for ln in path.read_text().splitlines() if ln and ln[0].isdigit()]
    assert len(lines) == 125
    assert lines[1] == "0.250000 0.000000 0.000000"  # red changes fastest
    assert lines[-1] == "1.000000 1.000000 1.000000"


def test_look_moves_footage_toward_the_reference(clips, tmp_path):
    mine, ref = clips
    lut = look.make("warm", ref, mine, base=tmp_path)
    graded = look.apply_to_file(mine, lut, tmp_path / "graded.mp4")
    before, after, want = style.colour(mine), style.colour(str(graded)), style.colour(ref)
    for key in ("warmth", "brightness", "contrast"):
        assert abs(after[key] - want[key]) < abs(before[key] - want[key]) * 0.35, key


def test_strength_scales_the_change(clips, tmp_path):
    mine, ref = clips
    half = look.apply_to_file(mine, look.make("half", ref, mine, strength=0.5, base=tmp_path), tmp_path / "h.mp4")
    before, mid, want = style.colour(mine)["warmth"], style.colour(str(half))["warmth"], style.colour(ref)["warmth"]
    assert before < mid < want
    with pytest.raises(EditError):
        look.make("bad", ref, mine, strength=2, base=tmp_path)


def test_preview_image_has_three_panels(clips, tmp_path):
    mine, ref = clips
    lut = look.make("warm", ref, mine, base=tmp_path)
    out = look.preview(mine, lut, 0.5, tmp_path / "p.png", reference=ref, ref_t=0.5, width=160)
    assert media.info(str(out)).width == 480


def test_commands_and_edit_list_carry_the_look(clips, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    mine, ref = clips
    main(["new", "p", "--source", mine])
    main(["look-make", "warm", "--reference", ref, "--footage", mine])
    main(["look-list"])
    assert "warm" in capsys.readouterr().out
    main(["look-use", "warm"])
    main(["cut", "0.5", "1"])
    main(["show"])
    assert "look warm" in capsys.readouterr().out
    main(["look-use", "none"])
    main(["show"])
    assert ", look" not in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["look-use", "missing"])


def test_builder_puts_the_look_on_every_main_clip():
    project = Project()
    e = EditList.from_clip("/v/a.mov", 1000, 24.0).remove_range(100, 300).set_look("/l/warm.cube")
    report = build_timeline(Resolve(project), e, "graded")
    assert report.ok and "look warm.cube" in report.text()
    assert [i.lut for i in project.timelines[0].tracks[1]] == ["/l/warm.cube"] * 2


def test_builder_reports_a_look_that_did_not_take(monkeypatch):
    monkeypatch.setattr(Item, "lut_works", False)
    e = EditList.from_clip("/v/a.mov", 1000, 24.0).set_look("/l/warm.cube")
    report = build_timeline(Resolve(Project()), e, "graded")
    assert not report.ok and "could not be put on 1 of 1 clips" in report.text()
