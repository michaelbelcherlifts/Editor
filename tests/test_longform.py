import json

import pytest
from fake_resolve import Project, Resolve

from stylebrain import formats, longform
from stylebrain.cli import main
from stylebrain.edl import EditError, EditList
from stylebrain.resolve_builder import build_timeline
from stylebrain.store import Store
from stylebrain.transcript import Word


def talk(text: str, start: float = 0.0, rate: float = 3.0) -> list[Word]:
    out, t = [], start
    for w in text.split():
        out.append(Word(w, round(t, 2), round(t + 0.8 / rate, 2)))
        t += 1 / rate
    return out


# ---- chapters in the edit list

def test_chapter_follows_its_moment_through_a_cut():
    e = EditList.from_clip("/v/a.mov", 24 * 600, 24.0).add_chapter("Results", 24 * 300)
    e = e.remove_range(0, 24 * 60)
    [(at, c)] = e.chapter_times()
    assert at == 24 * 240 and c.title == "Results"


def test_chapter_on_a_cut_moment_is_reported_lost():
    e = EditList.from_clip("/v/a.mov", 24 * 600, 24.0).add_chapter("Gone", 24 * 100).remove_range(24 * 90, 24 * 110)
    assert e.chapter_times()[0][0] is None


def test_chapter_same_title_moves_and_round_trips():
    e = EditList.from_clip("/v/a.mov", 2400, 24.0).add_chapter("Intro", 0).add_chapter("Why", 240)
    e = e.add_chapter("Why", 480).set_format("longform")
    back = EditList.from_dict(json.loads(json.dumps(e.to_dict())))
    assert back.format == "longform"
    assert [(at, c.title) for at, c in back.chapter_times()] == [(0, "Intro"), (480, "Why")]
    with pytest.raises(EditError):
        back.remove_chapter("nope")


def test_old_edit_lists_load_without_format_or_chapters():
    d = EditList.from_clip("/v/a.mov", 240, 24.0).to_dict()
    del d["format"], d["chapters"]
    e = EditList.from_dict(d)
    assert e.format == "" and e.chapters == ()


# ---- formats

def test_format_sets_the_frame_and_an_asked_size_wins():
    e = EditList.from_clip("/v/a.mov", 240, 24.0).set_format("longform")
    assert formats.size_for(e) == (1920, 1080)
    assert formats.size_for(e, "1280x720") == (1280, 720)
    assert formats.is_wide(e)
    with pytest.raises(EditError):
        formats.get("tiktok-but-wide")


# ---- YouTube chapter rules

def test_chapters_follow_youtube_rules():
    ok = longform.check_chapters([(0, "Intro"), (60, "Why"), (200, "Results")], 600)
    assert ok.lines == ["0:00 Intro", "1:00 Why", "3:20 Results"] and not ok.problems
    few = longform.check_chapters([(0, "Intro"), (5, "Why")], 600)
    assert any("at least 3" in p for p in few.problems)
    assert any("10s or more" in p for p in few.problems)


def test_chapters_first_moved_to_zero_and_notes_long_ones():
    r = longform.check_chapters([(12, "Intro"), (200, "Why"), (300, "Plan"), (900, "Results")], 1000)
    assert r.lines[0] == "0:00 Intro"
    assert any("opening runs" in n for n in r.notes)
    assert any("'Plan' runs 10:00" in n for n in r.notes)


def test_lost_chapter_blocks_youtube():
    r = longform.check_chapters([(0, "Intro"), (None, "Gone"), (60, "A"), (120, "B")], 600)
    assert any("Gone" in p for p in r.problems)


# ---- structure

def test_strong_opening_passes_the_opening_checks():
    words = talk("For the last 100 days I cut all my workouts in half. Would I lose muscle? "
                 "I'll show you what happened at the end.") + talk("filler " * 30, 20)
    kinds = {f.kind for f in longform.structure_check(words, 60)}
    assert not kinds & {"dead_air", "slow_opener", "premise", "open_loop"}


def test_weak_opening_is_flagged():
    words = talk("what is up youtube welcome back to the channel today we are training chest with my friend", 2.0)
    found = {f.kind: f for f in longform.structure_check(words, 600)}
    assert found["dead_air"].at == 0.0
    assert "slow_opener" in found and "premise" in found and "open_loop" in found
    assert "chapters" in found


def test_long_intro_long_chapter_and_dead_stretch():
    words = talk("Would it work? " + "lift " * 1500)
    found = longform.structure_check(words, 900, chapters=[(0, "Intro"), (150, "Plan"), (500, "Results")])
    kinds = [f.kind for f in found]
    assert "intro" in kinds and "long_chapter" in kinds and "dead_stretch" in kinds


def test_payoff_early_and_long_outro_and_early_pitch():
    words = talk("Can I do it? Use code MIKE for coaching. " + "rep " * 200)
    found = {f.kind for f in longform.structure_check(words, 900, chapters=[(0, "a"), (60, "b"), (200, "c")],
                                                      payoff_at=200)}
    assert {"payoff", "outro", "early_pitch"} <= found


def test_silence_and_slow_pace_are_notes_not_problems():
    words = talk("Is this the heaviest squat I have ever done? " + "go " * 60) + talk("done now", 300)
    found = [f for f in longform.structure_check(words, 600) if f.kind in {"silence", "pace"}]
    assert found and not any(f.serious for f in found)


def test_outline_covers_the_whole_length():
    for kind in longform.OUTLINES:
        plan = longform.outline(kind, 15)
        assert plan[0]["start"] == 0
        assert abs(sum(s["seconds"] for s in plan) - 900) <= len(plan)
    with pytest.raises(ValueError):
        longform.outline("vlogumentary", 10)


# ---- building in Resolve

def test_build_sets_wide_timeline_and_chapter_markers():
    e = EditList.from_clip("/v/a.mov", 24 * 120, 24.0).set_format("longform")
    e = e.add_chapter("Intro", 0).add_chapter("Why", 24 * 30).add_chapter("Gone", 24 * 100).remove_range(24 * 90, 24 * 110)
    project = Project()
    report = build_timeline(Resolve(project), e, "long v1")
    tl = project.timelines[0]
    assert tl.settings["timelineResolutionWidth"] == "1920" and tl.settings["timelineResolutionHeight"] == "1080"
    assert sorted(m["name"] for m in tl.markers.values()) == ["chapter: Intro", "chapter: Why"]
    assert tl.markers[24 * 30]["color"] == "Blue"
    assert report.chapters == 2 and "1920x1080" in report.text()
    assert any("Gone" in p for p in report.problems)


# ---- commands

@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["new", "long", "--source", "a.mov", "--fps", "24", "--frames", str(24 * 700)])
    words = [{"word": w.text, "start": w.start, "end": w.end}
             for w in talk("For 100 days I trained only once a week. Would I get weaker? You'll see at the end.")]
    (tmp_path / "t.json").write_text(json.dumps(words))
    return Store("long")


def test_format_chapter_and_chapters_commands(proj, capsys, tmp_path):
    main(["format", "longform"])
    assert proj.load().format == "longform"
    main(["chapter", "0", "Intro"])
    main(["chapter", "1:10", "Why once a week"])
    main(["chapter", "5:00", "Results"])
    capsys.readouterr()
    main(["chapters", "--out", "desc.txt"])
    out = capsys.readouterr().out
    assert "1:10 Why once a week" in out and "YouTube will show these chapters." in out
    assert (tmp_path / "desc.txt").read_text().splitlines()[0] == "0:00 Intro"
    main(["chapter", "--remove", "Results"])
    assert len(proj.load().chapters) == 2


def test_longform_check_command(proj, capsys):
    main(["chapter", "0", "Intro"])
    main(["chapter", "4:00", "Plan"])
    capsys.readouterr()
    main(["longform-check", "--transcript", "t.json", "--payoff", "1:00"])
    out = capsys.readouterr().out
    assert "long-form check" in out and "[intro]" in out and "[payoff]" in out
