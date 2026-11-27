import math
import shutil
from pathlib import Path

import pytest

from stylebrain import speed
from stylebrain.edl import EditError, EditList, Overlay, Segment

ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")


def test_out_seconds_constant_and_ramped():
    assert speed.out_seconds(2.0, 0.5) == pytest.approx(4.0)
    assert speed.out_seconds(2.0, 2.0) == pytest.approx(1.0)
    ramped = speed.out_seconds(3.0, 0.5, ramp=0.5)
    # slower than playing it straight, faster than all of it at half speed
    assert 3.0 < ramped < 6.0
    # each ramp takes r/(s-1)*ln(s) seconds: 0.5/-0.5*ln(0.5) = ln 2
    assert ramped == pytest.approx(2 * math.log(2) + 2.0 / 0.5)


def test_bad_speeds_and_ramps_are_refused():
    with pytest.raises(EditError):
        speed.out_seconds(2.0, 0.0)
    with pytest.raises(EditError):
        speed.out_seconds(2.0, 0.5, ramp=1.5)


def test_pts_expression_is_continuous_at_the_joins():
    length, s, r = 3.0, 0.4, 0.6
    expr = speed.pts_expr(length, s, r)
    assert expr.startswith("(if(lt(T,0.6)")
    k = r / (s - 1)
    ease_in = lambda T: k * math.log(1 + (s - 1) * T / r)  # noqa: E731
    t_in = ease_in(r)
    hold = lambda T: t_in + (T - r) / s  # noqa: E731
    t_hold = hold(length - r)
    ease_out = lambda T: t_hold + k * (math.log(s) - math.log(s - (s - 1) * (T - (length - r)) / r))  # noqa: E731
    assert hold(r) == pytest.approx(t_in)
    assert ease_out(length - r) == pytest.approx(t_hold)
    assert ease_out(length) == pytest.approx(speed.out_seconds(length, s, r))


def _fake_baker(made):
    def bake(src, start, end, out, fps, s, ramp, smooth, sound):
        made.append((src, round(start, 3), round(end, 3), s, ramp))
        return Path(out)
    return bake


def test_apply_bakes_each_clip_in_the_range_and_keeps_the_rest(tmp_path):
    edit = EditList(30.0, (Segment("a.mp4", 0, 60), Segment("b.mp4", 30, 90)), (Overlay("t", "t.mov", 70, 10),))
    made = []
    new, lines = speed.apply(edit, 30, 90, 0.5, tmp_path, baker=_fake_baker(made))
    # a.mp4 0..30 kept, a.mp4 30..60 and b.mp4 30..60 each slowed, b.mp4 60..90 kept
    assert [(s.source.endswith(".mp4") and "0.5x" in s.source) for s in new.segments] == [False, True, True, False]
    assert made == [("a.mp4", 1.0, 2.0, 0.5, 0.0), ("b.mp4", 1.0, 2.0, 0.5, 0.0)]
    assert new.duration == 30 + 60 + 60 + 30
    # the overlay 10 frames into b's slowed part stays on the same moment: 20 frames in at half speed
    assert new.overlays[0].at == 30 + 60 + 20
    assert any("silent" in line for line in lines)


def test_apply_reuses_a_bake_it_already_made(tmp_path):
    edit = EditList(30.0, (Segment("a.mp4", 0, 90),))
    made = []

    def touch(src, start, end, out, *rest):
        made.append(src)
        Path(out).write_bytes(b"")

    speed.apply(edit, 0, 30, 0.5, tmp_path, baker=touch)
    speed.apply(edit, 0, 30, 0.5, tmp_path, baker=touch)
    assert made == ["a.mp4"]


@ffmpeg
def test_bake_writes_the_right_length_at_the_edit_rate(tmp_path):
    from stylebrain import media
    src = tmp_path / "src.mp4"
    media.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=160x90:r=60:d=3",
               "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-pix_fmt", "yuv420p", "-shortest", str(src)])
    out = speed.bake(str(src), 1.0, 2.0, tmp_path / "slow.mp4", 30.0, 0.5, sound=True)
    i = media.info(str(out))
    assert i.fps == pytest.approx(30.0)
    assert abs(i.frames - 60) <= 2
    assert media.has_audio(str(out))
    ramped = speed.bake(str(src), 0.0, 2.0, tmp_path / "ramp.mp4", 30.0, 0.5, ramp=0.4)
    want = speed.out_seconds(2.0, 0.5, 0.4) * 30
    assert abs(media.info(str(ramped)).frames - want) <= 3
    assert not media.has_audio(str(ramped))


@ffmpeg
def test_speed_command_slows_part_of_the_edit(tmp_path, monkeypatch):
    from stylebrain import media
    from stylebrain.cli import main
    from stylebrain.store import Store
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "lift.mp4"
    media.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=160x90:r=30:d=4",
               "-pix_fmt", "yuv420p", str(src)])
    main(["new", "flex", "--source", str(src)])
    main(["speed", "--from", "1", "--to", "2", "--speed", "0.5", "--ramp", "0.2"])
    edit = Store("flex").load()
    assert len(edit.segments) == 3
    assert edit.duration > 4 * 30
    assert Path(edit.segments[1].source).exists()
    main(["undo"])
    assert Store("flex").load().duration == 120
