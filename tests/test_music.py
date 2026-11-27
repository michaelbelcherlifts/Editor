import json
import shutil

import pytest
from fake_resolve import Project, Resolve

np = pytest.importorskip("numpy")
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

from stylebrain import export, media, music  # noqa: E402
from stylebrain.cli import main  # noqa: E402
from stylebrain.edl import EditError, EditList, Music, Segment  # noqa: E402
from stylebrain.store import Store  # noqa: E402
from stylebrain.transcript import Word  # noqa: E402


def _track(path, bpm, seconds=20, first=0.2):
    """A kick on every beat and a lighter click between beats."""
    per = 60 / bpm
    expr = (f"0.6*sin(2*PI*90*t)*exp(-18*mod(t+{per}-{first}\\,{per}))"
            f"+0.2*sin(2*PI*2000*t)*exp(-60*mod(t+{per}-{first}+{per / 2}\\,{per}))+0.02*random(0)")
    media.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"aevalsrc='{expr}':d={seconds}:s=44100", str(path)])
    return str(path)


@pytest.fixture(scope="module")
def song(tmp_path_factory):
    return _track(tmp_path_factory.mktemp("music") / "song120.wav", 120)


@pytest.mark.parametrize("bpm", [87, 100, 128])
def test_tempo_and_beats_of_a_steady_track(tmp_path, bpm):
    info = music.analyse(_track(tmp_path / "t.wav", bpm), cache=None)
    assert info["bpm"] == pytest.approx(bpm, abs=1.5) and info["clear"] > 0.5
    beats, per = np.array(info["beats"]), 60 / bpm
    on_grid = 0.2 + per * np.round((beats - 0.2) / per)
    assert np.abs(beats - on_grid).max() < 0.03                  # on the kick, not the click between
    assert len(beats) >= 20 / per - 3


def test_analysis_is_saved_and_short_files_are_refused(song, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = music.analyse(song)
    assert list((tmp_path / ".stylebrain" / "beats").glob("song120.*.json"))
    monkeypatch.setattr(music, "envelope", lambda *a, **k: (_ for _ in ()).throw(AssertionError("read twice")))
    assert music.analyse(song) == first
    blip = tmp_path / "blip.wav"
    media.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.1", str(blip)])
    monkeypatch.undo()
    with pytest.raises(EditError, match="too short"):
        music.analyse(blip, cache=None)
    with pytest.raises(EditError, match="cannot find"):
        music.analyse(tmp_path / "nope.mp3")


def test_cuts_move_back_onto_the_beat():
    beats = [0.5 * n for n in range(1, 40)]                       # 120 beats a minute
    # Cuts at 1.10s (0.10 after a beat), 2.30s (0.30 after the beat at 2.0) and 4.90s (0.40 after 4.5).
    edit = EditList(30.0, (Segment("/v/a.mov", 0, 33), Segment("/v/a.mov", 100, 136),
                           Segment("/v/a.mov", 200, 278), Segment("/v/a.mov", 300, 400)))
    new, lines = music.snap_cuts(edit, beats, max_trim=0.3)
    starts = [s / 30 for s, _ in new.pieces()]
    # The first trim moves everything 0.10 earlier, so the second cut (now 2.20) is 0.20 from 2.0 and moves too.
    assert starts[1] == pytest.approx(1.0) and starts[2] == pytest.approx(2.0)
    assert "trimmed 0.10s" in lines[0] and "moved to the beat at 2.00s" in lines[1]
    assert starts[3] == pytest.approx(4.5) or "left alone" in lines[2]
    assert lines[-1].endswith("cuts now land on the beat")
    assert new.segments[0] == Segment("/v/a.mov", 0, 30)          # the end of the clip before the cut is what goes

    # A word across the trimmed stretch stops the move.
    words = [Word("hey", 0.95, 1.08)]
    kept, lines = music.snap_cuts(edit, beats, max_trim=0.3, words=words)
    assert "would clip a word" in lines[0] and kept.segments[0].src_out == 33
    bars, _ = music.snap_cuts(edit, beats, max_trim=0.3, every=4)
    assert [s / 30 for s, _ in bars.pieces()][1] == pytest.approx(1.1)   # no bar line near enough
    with pytest.raises(EditError, match="no beats"):
        music.snap_cuts(edit, [])


def test_music_is_part_of_the_edit_and_the_export(song, tmp_path):
    clip = tmp_path / "talk.mp4"
    # Speech stands in as a tone for the first two seconds, then silence.
    media.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=180x320:r=30:d=6", "-f", "lavfi", "-i",
               "sine=frequency=300:duration=6", "-af", "volume='if(lt(t,2),0.5,0)':eval=frame",
               "-pix_fmt", "yuv420p", "-shortest", str(clip)])
    edit = EditList.from_clip(str(clip), 180, 30.0).set_music(Music(song, start=2.0, gain_db=-12.0))
    assert EditList.from_dict(json.loads(json.dumps(edit.to_dict()))) == edit
    assert EditList.from_dict({"fps": 30, "segments": []}).music is None
    assert music.timeline_beats(edit, [1.9, 2.2, 7.9, 8.5]) == [0.2, 5.9]          # song time 2.0 is timeline 0
    with pytest.raises(EditError, match="gain"):
        Music(song, gain_db=20)

    voice = export.voice(edit, tmp_path / "voice.wav")
    ducked = music.bed(edit, tmp_path / "bed.wav", voice=voice)
    length = media.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ducked)],
                       text=True).stdout
    assert abs(float(length) - 6.0) < 0.05

    def level(path, a, b):
        err = media.run(["ffmpeg", "-v", "info", "-nostats", "-ss", str(a), "-t", str(b - a), "-i", str(path),
                         "-af", "volumedetect", "-f", "null", "-"], text=True).stderr
        return float(err.split("mean_volume:")[1].split()[0])
    assert level(ducked, 0.3, 1.8) < level(ducked, 3.0, 4.5) - 4          # lower while he speaks
    assert level(ducked, 5.6, 6.0) < level(ducked, 3.0, 4.5) - 3          # and faded at the end

    out = export.render(edit, tmp_path / "out.mp4", 180, 320)
    quiet = export.render(edit, tmp_path / "plain.mp4", 180, 320, music=False)
    assert export.check(out, 6.0, 180, 320).ok
    # With the music left out the back half is silent, and loudness normalising cannot hide that.
    assert level(out, 3.0, 5.0) > level(quiet, 3.0, 5.0) + 20


def test_music_commands_and_build(song, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["new", "p", "--source", "/v/a.mov", "--fps", "30", "--frames", "400"])
    main(["cut", "1.1", "2"])
    main(["music-add", song, "--start", "0.2", "--gain", "-20"])
    out = capsys.readouterr().out
    import re
    assert abs(float(re.search(r"([0-9.]+) beats a minute", out).group(1)) - 120) < 1 and "a clear pulse" in out
    main(["show"])
    assert "music song120.wav from 0.2s at -20 dB" in capsys.readouterr().out
    main(["music-beats"])
    off = float(re.search(r"cut at +1\.10s +\+([0-9.]+)s from the beat", capsys.readouterr().out).group(1))
    assert off == pytest.approx(0.10, abs=0.03)
    main(["music-snap"])
    assert "1 of 1 cuts now land on the beat" in capsys.readouterr().out
    assert Store("p").load().segments[0].src_out in (29, 30, 31)

    from stylebrain import cli, resolve_builder
    project = Project(fps="30")
    monkeypatch.setattr(resolve_builder, "connect", lambda: Resolve(project))
    main(["build"])
    out = capsys.readouterr().out
    assert "not lowered under the voice" in out and "music on A2: 1" in out      # /v/a.mov is not a real file here
    assert len(project.timelines[-1].audio[2]) == 1
    main(["music-remove"])
    assert Store("p").load().music is None
    with pytest.raises(SystemExit):
        main(["music-beats"])
