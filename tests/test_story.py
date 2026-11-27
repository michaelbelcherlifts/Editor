import json

import pytest

from stylebrain import story
from stylebrain.cli import main
from stylebrain.transcript import Word


def say(text, start, each=0.25, gap=0.05):
    out, t = [], start
    for w in text.split():
        out.append(Word(w, round(t, 3), round(t + each, 3)))
        t += each + gap
    return out


GOOD = say("Stop benching like this. It wrecks your shoulders. Tuck your elbows and stop benching like this.", 0.0)
SLOW = say("So um hey guys, welcome back to the channel.", 0.4) + say("Today we fix your bench press arch for good.", 4.5)


def test_sentences_split_on_punctuation_and_pauses():
    ss = story.sentences(say("one two three.", 0) + say("four five six", 3.0))
    assert [s.words for s in ss] == [3, 3] and ss[1].start == 3.0
    assert story.average_sentence_words(GOOD) == pytest.approx(16 / 3, 0.01)


def test_hook_check_names_the_slow_start_and_the_second():
    found = story.hook_check(SLOW, 12.0, cuts=[5.0], judge={"text_on_frame_1": False, "undelivered": True})
    kinds = {f.kind: f for f in found}
    assert "first meaningful word is at 1.6s" in kinds["dead_air"].text and "(So um hey guys,)" in kinds["dead_air"].text
    assert "welcome back" in kinds["slow_opener"].text
    assert kinds["first_point"].at == 4.5
    assert kinds["first_change"].at == 5.0
    assert {"text", "payoff"} <= set(kinds)


def test_a_tight_hook_has_no_serious_problems_and_loops():
    found = story.hook_check(GOOD, 6.0, cuts=[0.5, 2.0], judge={"text_on_frame_1": True, "undelivered": False})
    assert [f for f in found if f.serious] == []
    assert not any(f.kind == "loop" for f in found)  # the last line echoes the first


def test_unjudged_checks_are_named_not_guessed():
    found = story.hook_check(GOOD, 6.0)
    assert {f.kind for f in found if not f.serious} >= {"text", "payoff"}


def test_beat_map_flags_dead_stretches_and_and_then_runs():
    words = say("Can I squat 500 by June?", 0)
    t = 5.0
    for _ in range(30):  # 90 s of flat narration
        words += say("And then I did another set of squats.", t)
        t += 3.0
    words += say("But my knee gave out.", t)
    bm = story.beat_map(words, beats=[{"label": "hook", "start": 0}, {"label": "setup", "start": 5},
                                      {"label": "low point", "start": t}])
    assert bm.dead and bm.dead[0][0] == 0.0 and bm.dead[0][1] == pytest.approx(t, 0.01)
    assert bm.and_then and bm.and_then[0][2] >= 30
    assert "no payoff marked" in bm.problems
    assert any("setup is" in p for p in bm.problems)
    assert "dead stretch 0:00.0" in bm.text()
    assert story.beat_map(words, extra_questions=[50.0]).dead == []
    with pytest.raises(ValueError):
        story.beat_map(words, beats=[{"label": "vibes", "start": 0}])


def test_hook_option_and_script_checks():
    assert story.check_hook_option("I have 30 days to hit a 500 lb deadlift.", "30 days to 500 lbs") == []
    bad = story.check_hook_option("So welcome back guys today I want to talk about a thing", "hi")
    assert len(bad) == 3
    script = "\n".join([
        "I hate the term hybrid athlete.",
        "It means you're mid at both.",
        "So I tested it: a 516 DOTS lifter against a sub-22 5K.",
        "Week one went fine.",
        "But at mile two my legs were gone.",
        "Therefore I changed one thing: I slowed the first mile by 30 seconds.",
        "I ran 21:48.",
        "Hybrid athlete? Still hate the term.",
    ])
    out = story.check_script(script)
    assert out["has_numbers"] and out["new_question_late"] and out["ending_echoes_opening"]
    assert out["notes"] == []
    flat = story.check_script("I lifted.\nAnd then I ate.\nAnd then I slept.\nAnd then I lifted again.")
    assert any("and then" in n for n in flat["notes"]) and any("numbers" in n for n in flat["notes"])


def test_story_points():
    assert story.story_points({k: 5 for k in story.STORY_QUESTIONS}) == 25
    assert story.story_points({}) == 12.5
    with pytest.raises(ValueError):
        story.story_points({"want": 7})


def test_commands(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    t = tmp_path / "w.json"
    t.write_text(json.dumps([{"word": w.text, "start": w.start, "end": w.end} for w in SLOW]))
    main(["hook-check", "--transcript", str(t), "--seconds", "12"])
    out = capsys.readouterr().out
    assert "[dead_air]" in out and "1.6s" in out
    main(["beats", "--transcript", str(t), "--json"])
    assert "dead" in json.loads(capsys.readouterr().out)
    main(["hooks"])
    assert "stakes" in capsys.readouterr().out
    main(["hooks", "I have 30 days to hit a 500 lb deadlift.", "--text", "30 days to 500"])
    assert "hook ok" in capsys.readouterr().out
    s = tmp_path / "s.txt"
    s.write_text("I lifted.\nAnd then I ate.\nAnd then I slept.")
    main(["script-check", str(s), "--story", json.dumps({k: 2 for k in story.STORY_QUESTIONS})])
    out = capsys.readouterr().out
    assert "story 6.2 / 25: under 20" in out


def test_first_change_can_come_from_the_frame_sheet():
    """Cuts miss overlays: a judged first_change replaces the measured one."""
    from stylebrain import story
    from stylebrain.transcript import Word
    words = [Word("This", 0.0, 0.2), Word("helped", 0.2, 0.5), Word("me", 0.5, 0.6), Word("squat", 0.6, 1.0)]
    measured = {f.kind: f for f in story.hook_check(words, 16.8, [5.1])}
    assert "Only cuts are measured" in measured["first_change"].text
    assert "first_change" not in {f.kind for f in story.hook_check(words, 16.8, [5.1], {"first_change": 0.4})}
    assert {f.kind: f for f in story.hook_check(words, 16.8, [5.1], {"first_change": 2.8})}["first_change"].at == 2.8


def test_song_lyrics_are_flagged_and_can_be_dropped():
    from stylebrain.transcript import Word, keep_speech, maybe_sung
    spoken = [Word(w, i * 0.3, i * 0.3 + 0.22) for i, w in enumerate("so if we die we die".split())]
    sung = [Word(w, 6 + i * 0.9, 6 + i * 0.9 + 0.7) for i, w in enumerate("I came a long way from the bottom".split())]
    assert not maybe_sung(spoken) and maybe_sung(sung)
    assert [w.text for w in keep_speech(spoken + sung, [(0, 3.4)])] == [w.text for w in spoken]


def test_loop_check_reads_the_seam():
    from stylebrain import story
    from stylebrain.transcript import Word

    def say(text, start=0.0, each=0.3):
        return [Word(w, start + i * each, start + i * each + 0.25) for i, w in enumerate(text.split())]

    opening = say("This one cue fixed my bench.")
    kinds = lambda found: {f.kind: f for f in found}                         # noqa: E731
    k = kinds(story.loop_check(opening + say("Push your feet forward. So yeah.", 3.0), 8.0, end_dark=True))
    assert k["tail"].serious and "(`loop-trim`)" in k["tail"].text and k["fade"].serious and k["sign_off"].serious
    k = kinds(story.loop_check(opening + say("Push your feet forward and that's why", 3.0), 5.1, frame_gap=0.05))
    assert set(k) == {"leads_in"} and not k["leads_in"].serious
    k = kinds(story.loop_check(opening + say("Now your bench is fixed with one cue.", 3.0), 5.2, frame_gap=0.6))
    assert set(k) == {"echo", "picture"}
    k = kinds(story.loop_check(opening + say("Go get stronger today.", 3.0), 4.3, end_level=-60.0))
    assert set(k) == {"no_loop", "silence"} and "cannot be cut in" in k["no_loop"].text
    assert story.loop_check([], 10.0) == []
