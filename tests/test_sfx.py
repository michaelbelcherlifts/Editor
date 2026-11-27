import json
import shutil

import pytest
from fake_resolve import Project, Resolve

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

from stylebrain import media, sfx  # noqa: E402
from stylebrain.cli import main  # noqa: E402
from stylebrain.edl import EditError, EditList, Overlay, Segment, Sound  # noqa: E402
from stylebrain.resolve_builder import build_timeline  # noqa: E402
from stylebrain.store import Store  # noqa: E402
from stylebrain.transcript import Word  # noqa: E402


@pytest.fixture
def lib(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sfx.make_basics()
    return tmp_path


def test_basics_and_library_rules(lib):
    tags = {t for i in sfx.load() for t in i["tags"]}
    assert {"pop", "whoosh", "thud", "click", "riser"} <= tags
    assert all(i["licence"] == "made-here" and 0 < i["seconds"] < 2 for i in sfx.load())
    wav = lib / "library" / "sfx" / "basic-pop.wav"
    with pytest.raises(EditError, match="on record"):
        sfx.add(wav, ["pop"], " ")
    with pytest.raises(EditError, match="at least one tag"):
        sfx.add(wav, [], "cc0")
    with pytest.raises(EditError, match="no sound tagged"):
        sfx.find("airhorn")
    shutil.copy(wav, lib / "My Plate Drop.wav")
    item = sfx.add(lib / "My Plate Drop.wav", ["Hit", "plates"], "own")
    assert item["file"] == "my-plate-drop.wav" and item["tags"] == ["hit", "plates"]
    assert sfx.find("hit", turn=0)["file"] != sfx.find("hit", turn=1)["file"]
    shutil.copy(wav, lib / "song sting.wav")
    assert sfx.add(lib / "song sting.wav", ["sting"], "Unknown")["licence"] == "unknown"   # recorded, not blocked
    assert sfx.find("sting")["file"] == "song-sting.wav"
    with pytest.raises(EditError, match="no sound tagged"):
        sfx.find("sting", safe_only=True)                                                   # but kept out of ads


def test_sounds_follow_cuts_and_survive_save(lib):
    edit = EditList.from_clip("/v/a.mov", 300, 30.0)
    edit = edit.add_sound(Sound("a", "/s/pop.wav", 30, 3)).add_sound(Sound("b", "/s/pop.wav", 200, 3, -6.0))
    cut = edit.remove_range(20, 80)
    assert [(x.name, x.at) for x in cut.sounds] == [("b", 140)]
    assert EditList.from_dict(json.loads(json.dumps(cut.to_dict()))) == cut
    assert EditList.from_dict({"fps": 30, "segments": [{"source": "x", "src_in": 0, "src_out": 9}]}).sounds == ()
    with pytest.raises(EditError):
        edit.add_sound(Sound("a", "/s/pop.wav", 10, 3))
    assert edit.remove_sounds("a").sounds[0].name == "b" and edit.remove_sounds("").sounds == ()


def test_auto_place_picks_moments_and_ducks_under_speech(lib):
    edit = EditList(30.0, (Segment("/v/a.mov", 0, 90), Segment("/v/a.mov", 100, 110), Segment("/v/a.mov", 120, 300),
                           Segment("/v/a.mov", 400, 500, "zoom 1.2"), Segment("/v/a.mov", 500, 600)))
    edit = edit.add_overlay(Overlay("title", "/v/t.mov", 30, 30)).add_overlay(Overlay("captions 1", "/v/c.mov", 0, 300))
    words = [Word("press", 2.9, 3.4)]
    new, lines = sfx.auto_place(edit, words)
    got = {x.name: x for x in new.sounds}
    # pop on the title; whoosh on the first cut (3.0s) but not the one 0.33s later; whoosh on the zoom; whoosh on the last cut
    assert sorted(got) == ["auto:cut@380", "auto:cut@90", "auto:overlay@30", "auto:zoom@280"]
    assert got["auto:overlay@30"].tag == "pop" and got["auto:overlay@30"].gain_db == -14.0
    assert got["auto:cut@90"].gain_db == -20.0 and "lowered under speech" in "\n".join(lines)
    assert len(lines) == 4
    again, _ = sfx.auto_place(new.add_sound(Sound("mine", got["auto:cut@90"].source, 200, 5)), words, on=("overlays",))
    assert sorted(x.name for x in again.sounds) == ["auto:overlay@30", "mine"]
    with pytest.raises(EditError):
        sfx.auto_place(edit, on=("vibes",))


def test_mix_puts_each_sound_at_its_time(lib, tmp_path):
    np = pytest.importorskip("numpy")
    edit = EditList.from_clip("/v/a.mov", 90, 30.0)
    edit = edit.add_sound(sfx.sound_for(edit, "thud", 30, "one", 0.0)).add_sound(sfx.sound_for(edit, "thud", 60, "two", -20.0))
    out = sfx.mix(edit, tmp_path / "mix.wav")
    raw = media.run(["ffmpeg", "-v", "error", "-i", str(out), "-ac", "1", "-ar", "1000", "-f", "s16le", "-"]).stdout
    level = np.abs(np.frombuffer(raw, np.int16).astype(float))
    assert len(level) == pytest.approx(3000, abs=5)
    assert level[:950].max() < 50 and level[1000:1150].max() > 2000
    assert 0.05 < level[2000:2150].max() / level[1000:1150].max() < 0.2
    assert sfx.mix(EditList.from_clip("/v/a.mov", 90, 30.0), tmp_path / "none.wav") is None


def test_fetch_keeps_only_cc0_and_short_sounds(lib):
    src = str(lib / "library" / "sfx" / "basic-whoosh.wav")
    results = {"results": [
        {"title": "Nice whoosh", "license": "cc0", "url": "http://x/1.wav", "filetype": "wav", "duration": 400, "creator": "ann",
         "foreign_landing_url": "http://x/page1"},
        {"title": "Credit me", "license": "by", "url": "http://x/2.wav", "duration": 400},
        {"title": "Long one", "license": "cc0", "url": "http://x/3.wav", "duration": 9000},
        {"title": "Broken", "license": "cc0", "url": "http://x/4.wav", "duration": 300},
    ]}
    asked = []

    def download(url, dest):
        if url.endswith("4.wav"):
            raise OSError("404")
        shutil.copy(src, dest)

    added, skipped = sfx.fetch("gym whoosh", ["whoosh", "gym"], get_json=lambda u: asked.append(u) or results, download=download)
    assert "license=cc0" in asked[0] and "q=gym+whoosh" in asked[0]
    assert [i["file"] for i in added] == ["gym-whoosh-nice-whoosh.wav"]
    assert added[0]["licence"] == "cc0" and added[0]["credit"] == "ann" and added[0]["source"] == "http://x/page1"
    assert len(skipped) == 3 and "not cc0" in skipped[0] and "longer than" in skipped[1] and "404" in skipped[2]
    assert not (lib / "library" / "sfx" / "_tmp").exists()
    added, skipped = sfx.fetch("gym whoosh", ["x"], licence="any", get_json=lambda u: asked.append(u) or results, download=download)
    assert "license" not in asked[-1] and {i["licence"] for i in added} == {"cc0", "by"}


def test_commands_and_build_put_the_mix_on_an_audio_track(lib, capsys, monkeypatch):
    main(["new", "p", "--source", "/v/a.mov", "--fps", "30", "--frames", "300"])
    main(["cut", "3", "4"])
    main(["sfx-auto"])
    assert "whoosh  on cut" in capsys.readouterr().out
    main(["sfx-place", "pop", "--at", "1", "--name", "hello"])
    main(["show"])
    assert "2 sounds" in capsys.readouterr().out
    edit = Store("p").load()
    mixed = sfx.mix(edit, lib / "m.wav")
    project = Project(fps="30")
    report = build_timeline(Resolve(project), edit, "p v4", sound_mix=str(mixed))
    assert report.ok and "2 sound effects" in report.text()
    tl = project.timelines[0]
    assert len(tl.audio[2]) == 1 and tl.audio[2][0].duration == edit.duration
    main(["sfx-remove", "auto"])
    assert [x.name for x in Store("p").load().sounds] == ["hello"]
    main(["sfx-list"])
    assert "basic-pop.wav" in capsys.readouterr().out
