import shutil

import pytest

pytest.importorskip("playwright")
np = pytest.importorskip("numpy")
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

from stylebrain import media, reference  # noqa: E402
from stylebrain.cli import main  # noqa: E402
from stylebrain.edl import EditError  # noqa: E402
from stylebrain.render import render_html  # noqa: E402

W, H = 320, 180
# A white square that sits still for 1s, slides right for 0.5s, then sits still.
HTML = ("<style>html,body{margin:0;background:transparent}div{position:absolute;top:60px;left:20px;"
        "width:60px;height:60px;background:#fff;animation:m .5s linear 1s both}"
        "@keyframes m{to{left:240px}}</style><div></div>")


@pytest.fixture(scope="module")
def ref(tmp_path_factory):
    d = tmp_path_factory.mktemp("ref")
    overlay = render_html(HTML, d / "o.mov", 2.5, fps=20, width=W, height=H)
    out = d / "reference.mp4"
    media.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c=0x2040c0:s={W}x{H}:r=20:d=2.5",
               "-i", overlay.path, "-filter_complex", "[0][1]overlay", "-pix_fmt", "yuv420p", str(out)])
    return str(out), overlay.path


def test_motion_finds_when_and_how_long(ref):
    m = reference.motion(ref[0], 0.0, 2.5)
    assert len(m.bursts) == 1
    start, end = m.bursts[0]
    assert abs(start - 1.0) <= 0.11 and abs(end - 1.5) <= 0.11
    assert m.to_dict()["bursts"][0]["seconds"] == pytest.approx(0.5, abs=0.11)


def test_motion_on_still_footage_is_empty(ref):
    assert reference.motion(ref[0], 0.0, 0.9).bursts == []


def test_palette_reports_background_then_square(ref):
    colours = reference.palette(ref[0], 0.5)
    r, g, b = (int(colours[0]["hex"][i:i + 2], 16) for i in (1, 3, 5))
    assert b > 150 and r < 80 and colours[0]["share"] > 0.8
    assert any(all(int(c["hex"][i:i + 2], 16) > 220 for i in (1, 3, 5)) for c in colours)
    boxed = reference.palette(ref[0], 0.5, box=[20 / W + 0.03, 60 / H + 0.05, 0.1, 0.2])
    assert boxed[0]["share"] > 0.9 and boxed[0]["hex"].startswith("#f")


def test_contact_sheet_and_frames(ref, tmp_path):
    times = reference.contact_sheet(ref[0], 0.5, 2.0, tmp_path / "s.png", count=6, columns=3, width=160)
    assert times == [0.625, 0.875, 1.125, 1.375, 1.625, 1.875]
    i = media.info(str(tmp_path / "s.png"))
    assert (i.width, i.height) == (480, 180)
    saved = reference.frames(ref[0], 1.0, 1.5, tmp_path / "f", count=2, width=160)
    assert [round(s["time"], 3) for s in saved] == [1.125, 1.375]
    # the square has moved between the two saved frames
    a, b = (media.read_frame(s["path"], 0) for s in saved)
    assert np.abs(a.astype(int) - b.astype(int)).mean() > 3


def test_compare_sheet_stacks_reference_over_mine(ref, tmp_path):
    out = tmp_path / "cmp.png"
    reference.compare_sheet(ref[0], 0.0, ref[1], 0.0, 2.4, out, count=4, width=160)
    i = media.info(str(out))
    assert (i.width, i.height) == (640, 180)
    sheet = media.read_frame(str(out), 0)
    top, bottom = sheet[:90], sheet[90:]
    assert top[:, :, 2].mean() > 150            # reference row shows its blue background
    assert abs(int(bottom[5, 5, 0]) - 0x77) < 12  # my overlay is shown over grey
    # the square is on the left early and on the right late, in both rows
    for row in (top, bottom):
        assert row[45, 25].min() > 200 and row[45, 3 * 160 + 135].min() > 200


def test_fetch_asks_yt_dlp_and_returns_the_file(monkeypatch, tmp_path):
    made = tmp_path / "abc.mp4"
    made.write_bytes(b"x")
    seen = {}

    class Done:
        stdout = f"noise\n{made}\n"

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return Done()

    monkeypatch.setattr(reference, "run", fake_run)
    assert reference.fetch("https://example.com/v", tmp_path) == made
    assert seen["cmd"][0] == "yt-dlp" and "https://example.com/v" in seen["cmd"]
    Done.stdout = str(tmp_path / "gone.mp4")
    with pytest.raises(EditError):
        reference.fetch("https://example.com/v", tmp_path)


def test_cli_ref_commands(ref, tmp_path, capsys):
    main(["ref-motion", ref[0], "--start", "0", "--end", "2.5"])
    assert '"seconds": 0.5' in capsys.readouterr().out
    main(["ref-palette", ref[0], "--at", "0.5", "--colours", "2"])
    assert capsys.readouterr().out.count("#") == 2
    main(["ref-sheet", ref[0], "--start", "0", "--end", "2", "--out", str(tmp_path / "x.png"), "--count", "4"])
    assert "reading order" in capsys.readouterr().out


def test_motion_in_a_box_ignores_movement_elsewhere(ref):
    # The square slides along the top half; the bottom half never changes.
    assert reference.motion(ref[0], 0.0, 2.5, box=[0, 0.75, 1, 0.25]).bursts == []
    assert len(reference.motion(ref[0], 0.0, 2.5, box=[0, 0.3, 1, 0.4]).bursts) == 1
