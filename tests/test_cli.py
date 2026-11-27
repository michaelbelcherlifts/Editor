import json
import shutil
import subprocess

import pytest

from stylebrain.cli import main
from stylebrain.store import Store


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["new", "demo", "--source", "a.mov", "--fps", "24", "--frames", "240"])
    words = [{"word": "hello", "start": 1.0, "end": 1.5}, {"word": "um", "start": 2.0, "end": 2.2},
             {"word": "world", "start": 6.0, "end": 6.5}]
    (tmp_path / "t.json").write_text(json.dumps(words))
    return Store("demo")


def test_cut_then_undo(proj, capsys):
    main(["cut", "1", "2"])
    assert proj.load().duration == 216
    main(["undo"])
    assert proj.load().duration == 240
    assert "back to v1" in capsys.readouterr().out


def test_edit_after_undo_keeps_every_version(proj):
    main(["cut", "1", "2"])
    main(["undo"])
    main(["cut", "0", "1"])
    assert [r["version"] for r in proj.log()] == [1, 2, 3]
    assert [r["parent"] for r in proj.log()] == [0, 1, 1]
    main(["goto", "2"])
    assert proj.head() == 2


def test_cut_phrase_still_lands_after_earlier_cuts(proj):
    main(["cut", "0", "1"])                      # everything shifts one second earlier
    main(["cut-phrase", "um", "--transcript", "t.json"])
    segs = [(s.src_in, s.src_out) for s in proj.load().segments]
    assert segs == [(24, 48), (53, 240)]


def test_cut_phrase_already_gone(proj, capsys):
    main(["cut", "1.9", "2.3"])
    with pytest.raises(SystemExit) as e:
        main(["cut-phrase", "um", "--transcript", "t.json"])
    assert e.value.code == 2 and "already cut" in capsys.readouterr().err


def test_tighten(proj):
    main(["tighten", "--transcript", "t.json", "--min-gap", "1.0", "--pad", "0.25"])
    segs = [(s.src_in, s.src_out) for s in proj.load().segments]
    # keeps 0.25s before "hello", around the long pause, and after "world"
    assert segs == [(18, 59), (138, 162)]


def test_overlay_and_show(proj, capsys):
    main(["overlay-add", "title", "--source", "t.mov", "--at", "2", "--duration", "1"])
    main(["cut", "0", "1"])
    assert proj.load().overlays[0].at == 24
    main(["show"])
    assert "overlay 'title' on V2" in capsys.readouterr().out


def test_no_project(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        main(["show"])
    assert "no project selected" in capsys.readouterr().err


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_new_reads_a_real_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=64x64:rate=30",
                    "-pix_fmt", "yuv420p", "c.mp4"], check=True)
    main(["new", "real", "--source", "c.mp4"])
    e = Store("real").load()
    assert (e.fps, e.duration) == (30.0, 60)


def test_j_l_and_straight_cut_commands(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["new", "split", "--source", "a.mov", "--fps", "30", "--frames", "300"])
    main(["cut", "2", "4"])                                     # leaves a cut at 2s
    capsys.readouterr()
    main(["jcut", "2.3"])
    out = capsys.readouterr().out
    assert "J-cut at" in out and "8 frames before the picture" in out and "length unchanged" in out
    main(["lcut", "2", "--seconds", "0.5"])
    assert "L-cut at" in capsys.readouterr().out
    main(["straight-cut", "2"])
    assert "straight cut at" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["jcut", "8"])
    assert "no cut within" in capsys.readouterr().err


def test_loop_trim_ends_on_the_last_word(tmp_path, monkeypatch, capsys):
    import json
    monkeypatch.chdir(tmp_path)
    main(["new", "loop", "--source", "a.mov", "--fps", "30", "--frames", "300"])
    (tmp_path / "w.json").write_text(json.dumps([{"word": "one", "start": 1.0, "end": 1.4},
                                                 {"word": "cue", "start": 5.0, "end": 5.5}]))
    capsys.readouterr()
    main(["loop-trim", "--transcript", "w.json"])
    out = capsys.readouterr().out
    assert 'after the last word ("cue")' in out and "0:10.00 -> 0:05.60" in out
    main(["loop-trim", "--transcript", "w.json"])
    assert "nothing changed" in capsys.readouterr().out
    main(["loop-check", "--transcript", "w.json", "--seconds", "9"])
    assert "[tail]" in capsys.readouterr().out
