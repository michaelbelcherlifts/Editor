import json
import shutil

import pytest

np = pytest.importorskip("numpy")
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

from stylebrain import media, style  # noqa: E402
from stylebrain.cli import main  # noqa: E402
from stylebrain.edl import EditError  # noqa: E402
from stylebrain.transcript import Word  # noqa: E402

# Four flat-colour shots of differing brightness: 1s, 2s, 0.5s, 2.5s. Tone for 3s, then silence.
SHOTS = [("0x401010", 1.0), ("0x60e080", 2.0), ("0x102060", 0.5), ("0xf0e060", 2.5)]


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    out = tmp_path_factory.mktemp("style") / "ref.mp4"
    cmd = ["ffmpeg", "-v", "error"]
    for colour, seconds in SHOTS:
        cmd += ["-f", "lavfi", "-i", f"color=c={colour}:s=320x180:r=20:d={seconds}"]
    cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration=3",
            "-filter_complex", f"{''.join(f'[{n}]' for n in range(len(SHOTS)))}concat=n={len(SHOTS)}[v];[{len(SHOTS)}]apad=whole_dur=6[a]",
            "-map", "[v]", "-map", "[a]", "-pix_fmt", "yuv420p", "-t", "6", str(out)]
    media.run(cmd)
    return str(out)


def test_cuts_are_found_where_the_shots_change(video):
    cuts = style.cut_times(video)
    assert len(cuts) == 3
    for got, want in zip(cuts, [1.0, 3.0, 3.5]):
        assert abs(got - want) <= 0.06


def test_pacing_numbers():
    p = style.pacing([1.0, 3.0, 3.5], 6.0)
    assert p["shots"] == 4
    assert p["cuts_per_minute"] == 30.0
    assert p["median_shot"] == 1.5
    assert p["longest_shot"] == 2.5
    assert p["hook"] == {"seconds": 6.0, "cuts": 3, "median_shot": 1.5, "first_cut": 1.0}
    assert sum(p["cuts_per_minute_by_quarter"]) == pytest.approx(120.0)


def test_pacing_with_no_cuts():
    p = style.pacing([], 10.0)
    assert p["shots"] == 1 and p["hook"]["first_cut"] is None and p["hook"]["cuts"] == 0


def test_speech_pace_and_pauses():
    words = [Word("so", 0.5, 0.7), Word("today", 0.75, 1.1), Word("we", 2.1, 2.2), Word("bench", 2.25, 2.7)]
    s = style.speech(words, duration=60.0)
    assert s["words_per_minute"] == 4
    assert s["longest_pause"] == 1.0
    assert s["pauses_over_half_second_per_minute"] == 1.0
    assert s["first_word_at"] == 0.5
    assert s["hook_text"] == "so today we bench"
    with pytest.raises(EditError):
        style.speech([])


def test_colour_reads_warm_and_cool(video, tmp_path):
    warm, cool = tmp_path / "warm.mp4", tmp_path / "cool.mp4"
    for path, c in ((warm, "0xd08030"), (cool, "0x3070d0")):
        media.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c={c}:s=160x90:r=10:d=2",
                   "-pix_fmt", "yuv420p", str(path)])
    a, b = style.colour(str(warm)), style.colour(str(cool))
    assert a["warmth"] > 0.3 and b["warmth"] < -0.3
    assert a["saturation"] > 0.5


def test_audio_sees_the_quiet_half(video):
    a = style.audio(video)
    assert a["loudness_lufs"] is not None and a["loudness_lufs"] < 0
    assert 0.35 <= a["quiet_share"] <= 0.6


def test_learn_show_and_list_from_the_command_line(video, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    words = tmp_path / "w.json"
    words.write_text(json.dumps([{"word": "hello", "start": 0.2, "end": 0.5}, {"word": "there", "start": 0.6, "end": 0.9}]))
    main(["style-learn", video, "--name", "ref", "--transcript", str(words), "--about", "test clip"])
    out = capsys.readouterr().out
    assert "30 a minute" in out and "Opening words: \"hello there\"" in out
    saved = json.loads((tmp_path / "library" / "styles" / "ref.json").read_text())
    assert saved["pacing"]["shots"] == 4 and saved["frame"]["shape"] == "wide"
    main(["style-list"])
    assert "ref: test clip" in capsys.readouterr().out
    main(["style-show", "ref"])
    assert "Cuts: 30 a minute" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["style-show", "missing"])


def test_cuts_inside_a_film_strip_are_found(tmp_path):
    # Three shots inside a strip across the middle of a vertical frame, black above and below: the
    # whole-frame measure changes too little to count them; the middle-band pass finds both cuts.
    out = tmp_path / "strip.mp4"
    cmd = ["ffmpeg", "-v", "error"]
    for c in ["red", "blue", "green"]:
        cmd += ["-f", "lavfi", "-i", f"color=c={c}:s=180x96:r=20:d=2"]
    cmd += ["-filter_complex", "[0][1][2]concat=n=3,pad=180:320:0:104:black[v]", "-map", "[v]",
            "-pix_fmt", "yuv420p", str(out)]
    media.run(cmd)
    cuts = style.cut_times(str(out))
    assert len(cuts) == 2 and abs(cuts[0] - 2.0) <= 0.06 and abs(cuts[1] - 4.0) <= 0.06


def test_merge_cuts_drops_near_duplicates():
    assert style.merge_cuts([1.0, 3.0], [1.05, 5.0, 0.1]) == [1.0, 3.0, 5.0]


def test_edit_cuts_come_from_clip_and_broll_boundaries():
    from stylebrain.edl import EditList, Overlay, Segment
    edit = EditList(fps=25.0, segments=(Segment("a.mov", 0, 100), Segment("a.mov", 200, 300)),
                    overlays=(Overlay("broll x", "x.mp4", at=0, duration=101, track=2),   # ends 1 frame after the cut
                              Overlay("broll y", "y.mp4", at=150, duration=25, track=2),
                              Overlay("cap", "cap.mov", at=10, duration=20, track=5)))  # captions are not cuts
    assert style.edit_cuts(edit) == [4.0, 6.0, 7.0]
