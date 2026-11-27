import json
import os
import shutil
import stat

import pytest
from fake_resolve import Project, Resolve

from stylebrain import autopilot, review, style
from stylebrain import transcript as tr
from stylebrain.cli import main
from stylebrain.edl import EditError, EditList
from stylebrain.store import Store
from stylebrain.transcript import Word


def say(text, start, each=0.3, gap=0.05):
    out, t = [], start
    for w in text.split():
        out.append(Word(w, round(t, 3), round(t + each, 3)))
        t += each + gap
    return out


# A false start, then the real line, a long pause, then a second line.
WORDS = (say("so today we are going", 1.0) + say("so today we are going to bench press", 3.0)
         + say("keep your shoulders back", 8.0))


def test_retake_is_the_first_attempt():
    assert tr.find_retakes(WORDS) == [(1.0, 3.0)]
    assert tr.find_retakes(say("one two three four five six", 0)) == []
    far = say("so today we are", 0) + say("so today we are", 100)
    assert tr.find_retakes(far) == []


def test_words_follow_the_cut():
    edit = EditList.from_clip("/v/a.mov", 300, 30.0).remove_range(30, 90)   # cut source 1s to 3s
    words = autopilot.timeline_words(edit, "/v/a.mov", WORDS)
    assert words[0].text == "so" and words[0].start == pytest.approx(1.0)   # the second "so", moved up 2s
    assert len(words) == len(WORDS) - 5


def test_subtitles_out_and_back():
    srt = tr.to_srt(say("keep your shoulders back and down the whole time you press", 1.0), max_chars=20)
    assert srt.startswith("1\n00:00:01,000 --> ")
    back = tr.from_subtitles(srt)
    assert [w.text for w in back][:4] == ["keep", "your", "shoulders", "back"]
    assert back[0].start == pytest.approx(1.0)


def test_youtube_style_captions_drop_repeated_lines():
    vtt = ("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nhello<00:00:01.500><c> there</c>\n\n"
           "00:00:03.000 --> 00:00:05.000\nhello there\nwelcome back\n")
    assert [w.text for w in tr.from_subtitles(vtt)] == ["hello", "there", "welcome", "back"]


def test_review_points_at_long_shots_pauses_and_a_late_start():
    target = {"name": "ref", "pacing": style.pacing([2, 4, 6, 8, 10, 12, 14, 16, 18], 20.0),
              "speech": style.speech(say("a b c d e f g h i j k l m n o p q r s t u v w x y z", 0.2, 0.3, 0.05), 20.0)}
    edit = EditList.from_clip("/v/a.mov", 600, 30.0)
    mine = review.profile_of_edit(edit, WORDS)
    found = review.compare(mine, target)
    kinds = [s.kind for s in found]
    assert "long_shot" in kinds and "pause" in kinds and "opening" in kinds
    pause = next(s for s in found if s.kind == "pause")
    assert pause.at == pytest.approx(WORDS[12].end)
    assert found == sorted(found, key=lambda s: (s.at is not None, s.at or 0))
    assert "[long_shot]" in next(s for s in found if s.kind == "long_shot").line(30.0)


def test_review_is_quiet_when_the_cut_matches():
    target = {"name": "ref", "pacing": style.pacing([2, 4, 6, 8], 10.0)}
    mine = {"frame": {"seconds": 10.0}, "cuts": [2, 4, 6, 8], "pacing": style.pacing([2, 4, 6, 8], 10.0)}
    assert review.compare(mine, target) == []


class FakeRender:
    frames = 30

    def __init__(self, path):
        self.path = path


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("stylebrain.media.probe", lambda path: (30.0, 300))
    (tmp_path / "raw.words.json").write_text(json.dumps([{"word": w.text, "start": w.start, "end": w.end} for w in WORDS]))
    return tmp_path


def test_autopilot_cuts_retake_tightens_captions_builds_and_reviews(project):
    style.save("ref", {"source": "x", "pacing": style.pacing([1, 2, 3, 4, 5, 6, 7, 8, 9], 10.0),
                       "speech": style.speech(say("a b c d e f g h i j", 0.1, 0.3, 0.1), 10.0)})
    resolve = Resolve(Project(fps="30"))
    rendered = []

    def render(template, params, out, fps, width, height, label):
        rendered.append(params)
        return FakeRender(str(project / f"{label}.mov"))

    r = autopilot.run("bench", str(project / "raw.mov"), style_name="ref", captions=True,
                      connect=lambda: resolve, render=render)
    text = r.text()
    assert "cut 1 likely retakes" in text and "tighten" in text and "place captions" in text
    assert r.built and "all checked" in text
    assert any("retake cut, source 1.0s to 3.0s" in n for n in r.notes)
    assert rendered and rendered[0]["words"][0]["start"] == 0
    assert (project / ".stylebrain" / "renders" / "bench.srt").read_text().startswith("1\n")
    store = Store("bench")
    assert store.head() == 4 and store.load().duration < 300
    assert resolve.project.timelines[0].name == "bench v4"
    assert {s.kind for s in r.suggestions} == {"pace", "opening"}
    main(["undo"])
    assert not Store("bench").load().overlays


def test_autopilot_without_resolve_keeps_the_edit(project):
    def no_resolve():
        raise EditError("could not reach Resolve")

    r = autopilot.run("bench", str(project / "raw.mov"), connect=no_resolve)
    assert not r.built and any("not built in Resolve" in n for n in r.notes)
    assert Store("bench").head() == 3
    # No sliver of the cut retake is left behind: the edit opens just before the real first line.
    assert Store("bench").load().segments[0].src_in == round((3.0 - 0.12) * 30)
    with pytest.raises(EditError):
        autopilot.run("bench", str(project / "raw.mov"), connect=no_resolve)
    with pytest.raises(EditError, match="too rough"):
        autopilot.run("other", str(project / "raw.mov"), transcript="subs.srt", connect=no_resolve)
    assert not Store("other").exists()


def test_commands_retakes_srt_and_review(project, capsys):
    t = str(project / "raw.words.json")
    main(["new", "p", "--source", str(project / "raw.mov"), "--fps", "30", "--frames", "300"])
    main(["retakes", "--transcript", t])
    assert "so today we are going" in capsys.readouterr().out
    main(["retakes", "--transcript", t, "--cut"])
    assert "0:10.00 -> 0:08.13" in capsys.readouterr().out
    main(["srt", "--transcript", t, "--out", "cut.srt"])
    assert "00:00:01,133 --> " in (project / "cut.srt").read_text()
    style.save("ref", {"source": "x", "pacing": style.pacing([1, 2, 3, 4, 5, 6, 7], 8.0)})
    main(["review", "ref", "--transcript", t])
    assert "[long_shot]" in capsys.readouterr().out


def test_phantom_speech_over_music_is_dropped():
    assert tr.drop_phantom_speech([Word("Thanks", 9, 9.5), Word("for", 9.5, 9.8), Word("watching!", 9.8, 11)]) == []
    real = say("thanks for watching my bench today", 0)
    assert tr.drop_phantom_speech(real) == real


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
@pytest.mark.skipif(os.name == "nt", reason="the stand-in speech tool is a shell script, which Windows cannot run")
def test_transcribe_uses_the_first_tool_found(tmp_path, monkeypatch):
    from stylebrain import media
    from stylebrain.transcribe import transcribe
    clip = tmp_path / "clip.mp4"
    media.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x36:r=10:d=1",
               "-f", "lavfi", "-i", "sine=duration=1", "-shortest", str(clip)])
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tool = bin_dir / "whisper"
    tool.write_text("#!/bin/sh\nwhile [ $# -gt 0 ]; do [ \"$1\" = --output_dir ] && out=$2; shift; done\n"
                    "echo '{\"segments\":[{\"words\":[{\"word\":\" hi\",\"start\":0.1,\"end\":0.4}]}]}' > \"$out/audio.json\"\n")
    tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    real = os.path.dirname(shutil.which("ffmpeg"))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{real}{os.pathsep}/usr/bin{os.pathsep}/bin")
    path, words = transcribe(str(clip))
    assert path.name == "clip.words.json" and words == [Word("hi", 0.1, 0.4)]
    monkeypatch.setenv("PATH", f"{real}{os.pathsep}/usr/bin{os.pathsep}/bin")
    if not shutil.which("mlx_whisper") and not shutil.which("whisper"):
        with pytest.raises(EditError, match="no speech-to-text tool"):
            transcribe(str(clip))
