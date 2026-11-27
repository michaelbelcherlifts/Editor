import shutil

import pytest

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

from stylebrain import export, media, sfx  # noqa: E402
from stylebrain.cli import main  # noqa: E402
from stylebrain.edl import EditError, EditList, Overlay, Segment  # noqa: E402


def _clip(path, colour, seconds=3, size="320x180", tone=440, volume=0.05, sound=True):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={colour}:s={size}:r=30:d={seconds}"]
    if sound:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency={tone}:duration={seconds}", "-af", f"volume={volume}"]
    media.run(cmd + ["-pix_fmt", "yuv420p", "-shortest", str(path)])
    return str(path)


@pytest.fixture(scope="module")
def clips(tmp_path_factory):
    d = tmp_path_factory.mktemp("export")
    return {"red": _clip(d / "red.mp4", "red"), "blue": _clip(d / "blue.mp4", "blue", sound=False),
            "green": _clip(d / "green.mp4", "green", size="180x320"), "dir": d}


def _colour(file, t):
    r, g, b = media.read_frame(file, t, width=32).reshape(-1, 3).mean(axis=0)
    return "red" if r > 150 and g < 90 else "blue" if b > 150 and g < 90 else "green" if g > 90 and r < 90 else "other"


def test_render_follows_the_edit_and_lands_on_target(clips, tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    monkeypatch.chdir(tmp_path)
    sfx.make_basics()
    edit = EditList(30.0, (Segment(clips["red"], 0, 30), Segment(clips["blue"], 30, 60), Segment(clips["red"], 60, 90)),
                    (Overlay("b", clips["green"], 70, 15),))
    edit = sfx.auto_place(edit, on=("cuts",), min_cut_gap=0.5)[0]
    out = export.render(edit, tmp_path / "out" / "cut.mp4", 180, 320)
    i = media.info(str(out))
    assert (i.width, i.height, i.frames) == (180, 320, 90) and media.has_audio(str(out))
    assert [_colour(str(out), t) for t in (0.5, 1.5, 2.2, 2.5, 2.95)] == ["red", "blue", "red", "green", "red"]
    c = export.check(out, 3.0, 180, 320, sheet=tmp_path / "sheet.jpg")
    assert c.ok, c.text()
    assert abs(c.facts["lufs"] + 14) < 1.5 and c.facts["peak"] <= -0.5
    assert (tmp_path / "sheet.jpg").stat().st_size > 0 and "ready to post" in c.text()


def test_fit_keeps_the_whole_picture(clips, tmp_path):
    pytest.importorskip("numpy")
    edit = EditList(30.0, (Segment(clips["red"], 0, 15),))
    out = export.render(edit, tmp_path / "fit.mp4", 180, 320, fit="fit")
    frame = media.read_frame(str(out), 0.2)
    assert frame[10].mean() < 40 and frame[160, :, 0].mean() > 150      # bars above, picture in the middle
    with pytest.raises(EditError, match="fit is"):
        export.render(edit, tmp_path / "x.mp4", fit="stretch")
    with pytest.raises(EditError, match="cannot find"):
        export.render(EditList(30.0, (Segment("/nope.mov", 0, 15),)), tmp_path / "x.mp4")


def test_check_names_what_is_wrong(clips, tmp_path):
    d = clips["dir"]
    black = _clip(d / "black.mp4", "black", seconds=1, size="180x320")
    bad = d / "bad.mp4"
    media.run(["ffmpeg", "-v", "error", "-y", "-i", black, "-i", clips["green"], "-filter_complex",
               "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]", str(bad)])
    c = export.check(bad, expect_seconds=10, width=180, height=320)
    text = c.text()
    assert not c.ok
    assert "opens on black" in text and "too quiet" in text and "but the edit is 10.00s" in text
    assert "thing(s) to fix" in text
    wide = export.check(clips["blue"])
    assert any("no sound" in p for p in wide.problems) and any("320x180" in p for p in wide.problems)


def test_export_commands(clips, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["new", "p", "--source", clips["red"]])
    main(["cut", "1", "2"])
    main(["export", "--size", "180x320"])
    out = capsys.readouterr().out
    assert "exported" in out and "ready to post" in out
    assert (tmp_path / "exports" / "p-v2.mp4").exists() and (tmp_path / "exports" / "p-v2.frames.jpg").exists()
    with pytest.raises(SystemExit):
        main(["export-check", clips["blue"], "--no-sheet"])
    assert "no sound" in capsys.readouterr().out
