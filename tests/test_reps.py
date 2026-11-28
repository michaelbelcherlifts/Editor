import shutil

import pytest

np = pytest.importorskip("numpy")

from stylebrain import media, reps  # noqa: E402
from stylebrain.edl import EditList, Segment  # noqa: E402
from stylebrain.reps import Rep  # noqa: E402


def lift(per_second=10.0, lead=4.0, count=4, down=1.0, pause=0.3, up=1.0, top=0.6, tail=3.0, rest=1.0):
    """A trace at `rest`, then `count` reps away from it and back, then at rest again."""
    t, v, marks = 0.0, [], []
    step = 1 / per_second

    def hold(seconds, level):
        nonlocal t
        for _ in range(round(seconds * per_second)):
            v.append(level)
            t += step
    hold(lead, rest)
    for _ in range(count):
        start = t
        for k in range(round(down * per_second)):
            v.append(rest + (1 - 2 * rest) * (k + 1) / round(down * per_second))
            t += step
        hold(pause, 1 - rest)
        for k in range(round(up * per_second)):
            v.append((1 - rest) + (2 * rest - 1) * (k + 1) / round(up * per_second))
            t += step
        marks.append((start, t))
        hold(top, rest)
    hold(tail, rest)
    return np.arange(len(v)) / per_second, np.array(v), marks


def test_reps_are_found_whole_whichever_way_the_trace_points():
    for rest in (1.0, 0.0):                       # the trace may come out either way up
        t, v, marks = lift(rest=rest)
        found = reps.find_reps(t, v + np.random.default_rng(1).normal(0, 0.02, len(v)))
        assert len(found) == 4
        for r, (a, b) in zip(found, marks):
            assert a - 0.45 <= r.start <= a + 0.3 and b - 0.3 <= r.end <= b + 0.45
            assert r.start < r.turn < r.end and r.depth > 0.8


def test_a_rep_that_never_comes_back_up_is_not_counted():
    t, v, _ = lift(count=2)
    cut = int(len(v) * 0.55)                     # the clip stops on the way down into rep two
    found = reps.find_reps(t[:cut], v[:cut])
    assert len(found) == 1


def test_a_single_rep_is_found_and_a_flat_trace_has_none():
    t, v, marks = lift(count=1, down=1.5, pause=1.0, up=2.0)
    found = reps.find_reps(t, v)
    assert len(found) == 1 and abs(found[0].start - marks[0][0]) < 0.45
    assert reps.find_reps(t, np.ones(len(t))) == []


def test_whole_and_broken_say_what_a_cut_loses():
    r = [Rep(10.0, 11.5, 13.0), Rep(13.4, 15.0, 16.5)]
    assert reps.whole(r, 11.0, 14.0) == (10.0, 16.5)
    assert reps.whole(r, 20.0, 22.0) == (20.0, 22.0)
    lost = reps.broken(r, 12.0, 16.5)             # starts after the far point of rep one
    assert [(n, what) for n, _, what in lost] == [(1, "the way down and the press")]
    assert reps.broken(r, 10.0, 16.5) == [] and reps.broken(r, 9.9, 13.05) == []
    assert reps.broken(r, 10.0, 14.0)[0][2] == "everything after it starts"


def test_the_edit_is_checked_against_saved_reps(tmp_path):
    reps.save({"video": "bench.mp4", "reps": [{"start": 10.0, "turn": 11.5, "end": 13.0, "depth": 1.0}]}, tmp_path)
    edit = EditList(fps=30.0, segments=(Segment("bench.mp4", 345, 420), Segment("other.mp4", 0, 60)))
    problems, unmeasured = reps.check(edit, tmp_path)
    assert unmeasured == ["other.mp4"]
    assert len(problems) == 1 and "cuts rep 1" in problems[0] and "whole reps need 10.00-14.00s" in problems[0]
    good = EditList(fps=30.0, segments=(Segment("bench.mp4", 295, 395),))
    assert reps.check(good, tmp_path) == ([], [])


def moving_box(tmp_path, per_second=10, lead=4.0, count=4, tail=3.0, wander=True):
    """A small clip: a bar that goes down and up `count` times, with someone drifting across behind it."""
    t, v, marks = lift(per_second, lead=lead, count=count, tail=tail)
    h, w = 96, 54
    frames = np.full((len(v), h, w, 3), 40, np.uint8)
    rng = np.random.default_rng(3)
    for i, level in enumerate(v):
        y = int(20 + (1 - level) * 40)
        frames[i, y: y + 6, 8: 46] = 220
        if wander:
            x = int(i / len(v) * (w - 6))
            frames[i, 70: 90, x: x + 5] = 120
    frames = np.clip(frames + rng.normal(0, 3, frames.shape), 0, 255).astype(np.uint8)
    raw = tmp_path / "raw.rgb"
    raw.write_bytes(frames.tobytes())
    out = tmp_path / "set.mp4"
    media.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r",
               str(per_second), "-i", str(raw), "-pix_fmt", "yuv420p", "-r", "30", str(out)])
    return out, marks


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_a_set_is_found_in_a_clip_by_its_rhythm(tmp_path):
    clip, marks = moving_box(tmp_path)
    result = reps.measure(str(clip))
    found = [Rep(**r) for r in result["reps"]]
    assert len(found) == 4 and result["how"] == "found by its rhythm"
    for r, (a, b) in zip(found, marks):
        assert abs(r.start - a) < 0.6 and abs(r.end - b) < 0.6
    assert "4 reps between" in reps.text(result)
    saved = reps.save(result, tmp_path)
    assert saved.exists() and len(reps.saved(str(clip), tmp_path)) == 4
    sheet = reps.sheet(str(clip), found, tmp_path / "sheet.jpg")
    assert sheet.exists() and media.info(str(sheet)).width == 600


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_a_single_needs_to_be_told_where_to_look(tmp_path):
    clip, marks = moving_box(tmp_path, count=1, wander=False)
    assert reps.measure(str(clip))["reps"] == [] and "--between" in reps.measure(str(clip))["note"]
    result = reps.measure(str(clip), between=(marks[0][0] - 1.0, marks[0][1] + 1.0))
    assert len(result["reps"]) == 1 and abs(result["reps"][0]["start"] - marks[0][0]) < 0.6


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_reps_and_rep_check_from_the_command_line(tmp_path, monkeypatch, capsys):
    from stylebrain.cli import main
    clip, marks = moving_box(tmp_path)
    monkeypatch.chdir(tmp_path)
    main(["reps", str(clip), "--sheet", "sheet.jpg"])
    out = capsys.readouterr().out
    assert "4 reps between" in out and "check sheet" in out
    main(["new", "bench", "--source", str(clip)])
    main(["rep-check"])
    assert "No measured rep is cut into." in capsys.readouterr().out
    a = marks[0][0] + 1.2                         # a cut that starts after the far point of rep one
    main(["cut", "0", f"{a:.2f}"])
    with pytest.raises(SystemExit):
        main(["rep-check"])
    assert "cuts rep 1" in capsys.readouterr().out
