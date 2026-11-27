import shutil
from pathlib import Path

import pytest

from stylebrain import transitions
from stylebrain.edl import EditError, EditList, Overlay, Segment

ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")


def test_strength_peaks_at_the_cut():
    out = transitions.strengths(4, outgoing=True)
    assert out == sorted(out) and out[-1] == 1.0
    assert transitions.strengths(4, outgoing=False) == out[::-1]
    assert transitions.strengths(0, True) == []


def test_blur_smears_a_sharp_edge_and_leaves_zero_alone():
    np = pytest.importorskip("numpy")
    f = np.zeros((20, 40, 3), dtype=np.uint8)
    f[:, 30:] = 255  # off-centre, so the zoom smear moves it too
    assert (transitions.blur_frame(f, 0, "whip") == f).all()
    for kind in transitions.KINDS:
        b = transitions.blur_frame(f, 1.0, kind)
        mids = ((b > 30) & (b < 225)).sum()
        assert b.shape == f.shape and mids > 0, kind
    with pytest.raises(EditError):
        transitions.blur_frame(f, 0.5, "spin")


def _fake(made):
    def bake(src, start, frames, out, fps, kind, outgoing, direction):
        made.append((src, round(start, 3), frames, kind, outgoing))
        Path(out).write_bytes(b"")
    return bake


def test_apply_bakes_both_sides_and_keeps_lengths_and_overlays(tmp_path):
    edit = EditList(30.0, (Segment("a.mp4", 0, 60), Segment("b.mp4", 30, 90)), (Overlay("t", "t.mov", 70, 10),))
    made = []
    new, lines = transitions.apply(edit, 62, "whip", tmp_path, frames=6, baker=_fake(made))
    assert made == [("a.mp4", 54 / 30, 6, "whip", True), ("b.mp4", 1.0, 6, "whip", False)]
    assert new.duration == edit.duration
    assert [s.duration for s in new.segments] == [54, 6, 6, 54]
    assert new.overlays == edit.overlays
    assert "frame 60" in lines[0]
    # a second run reuses the baked files
    transitions.apply(edit, 60, "whip", tmp_path, frames=6, baker=_fake(made))
    assert len(made) == 2


def test_apply_refuses_far_from_a_cut_and_bad_kinds(tmp_path):
    edit = EditList(30.0, (Segment("a.mp4", 0, 60), Segment("b.mp4", 0, 60)))
    with pytest.raises(EditError):
        transitions.apply(edit, 100, "whip", tmp_path, baker=_fake([]))
    with pytest.raises(EditError):
        transitions.apply(edit, 60, "spin", tmp_path, baker=_fake([]))
    with pytest.raises(EditError):
        transitions.apply(EditList(30.0, (Segment("a.mp4", 0, 60),)), 30, "zoom", tmp_path, baker=_fake([]))


@ffmpeg
def test_transition_command_bakes_real_frames(tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    from stylebrain import media
    from stylebrain.cli import main
    from stylebrain.store import Store
    monkeypatch.chdir(tmp_path)
    for name, colour in [("a", "red"), ("b", "blue")]:
        media.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=s=160x90:r=30:d=2",
                   "-pix_fmt", "yuv420p", str(tmp_path / f"{name}.mp4")])
    main(["new", "flex", "--source", str(tmp_path / "a.mp4")])
    main(["add-source", str(tmp_path / "b.mp4")])
    before = Store("flex").load()
    main(["transition", "--at", "2", "--kind", "zoom", "--frames", "4"])
    edit = Store("flex").load()
    assert edit.duration == before.duration
    baked = [s for s in edit.segments if "zoom" in s.source]
    assert len(baked) == 2 and all(Path(s.source).exists() for s in baked)
    assert media.info(baked[0].source).frames == 4
    main(["undo"])
    assert Store("flex").load().segments == before.segments
