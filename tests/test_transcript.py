import json
import pytest
from stylebrain.transcript import Word, find_phrase, find_silences, load_words, tighten_ranges

WORDS = [Word("So,", 1.0, 1.2), Word("the", 1.3, 1.4), Word("Bench", 1.4, 1.8), Word("press!", 1.8, 2.3),
         Word("Um", 4.0, 4.2), Word("the", 4.3, 4.4), Word("bench", 4.4, 4.8), Word("press", 4.8, 5.2)]


def test_find_phrase_ignores_case_and_punctuation():
    assert find_phrase(WORDS, "bench press") == [(1.4, 2.3), (4.4, 5.2)]
    assert find_phrase(WORDS, "So the") == [(1.0, 1.4)]
    assert find_phrase(WORDS, "squat") == []
    assert find_phrase(WORDS, "...") == []


def test_silences_include_lead_in_and_tail():
    assert find_silences(WORDS, 0.6, clip_length=8.0) == [(0.0, 1.0), (2.3, 4.0), (5.2, 8.0)]
    assert find_silences(WORDS, 0.6) == [(0.0, 1.0), (2.3, 4.0)]
    assert find_silences(WORDS, 2.0, clip_length=8.0) == [(5.2, 8.0)]


def test_tighten_leaves_air_around_speech():
    cuts = tighten_ranges(WORDS, 0.6, pad=0.1, clip_length=8.0)
    assert [(round(a, 2), round(b, 2)) for a, b in cuts] == [(0.0, 0.9), (2.4, 3.9), (5.3, 8.0)]


def test_load_words_shapes(tmp_path):
    flat = tmp_path / "flat.json"
    flat.write_text(json.dumps([{"word": " hi", "start": 0.5, "end": 0.7}, {"word": "x"}]))
    assert load_words(flat) == [Word("hi", 0.5, 0.7)]
    whisper = tmp_path / "w.json"
    whisper.write_text(json.dumps({"segments": [{"words": [{"word": "b", "start": 2, "end": 3}]},
                                                {"words": [{"text": "a", "start": 0, "end": 1}]}]}))
    assert [w.text for w in load_words(whisper)] == ["a", "b"]


def _say(text, start, each=0.25, gap=0.05):
    from stylebrain.transcript import Word
    out, t = [], start
    for w in text.split():
        out.append(Word(w, round(t, 3), round(t + each, 3)))
        t += each + gap
    return out


def test_takes_restart_after_breaking_off():
    from stylebrain import transcript as tr
    # Breaks off after three words, pauses, starts again with the same two.
    words = _say("The reason I-", 1.0) + _say("The reason most people stall is sleep.", 3.0) + _say("Fix that first.", 7.0)
    takes = tr.find_takes(words)
    assert [(t.kind, t.sure, t.start, t.end) for t in takes] == [("restart", True, 1.0, 3.0)]
    assert tr.find_retakes(words) == [(1.0, 3.0)]


def test_takes_leave_deliberate_repetition_alone():
    from stylebrain import transcript as tr
    # Finished sentences that open the same way are a device, not a mistake.
    words = _say("I trained hard.", 0.0) + _say("I trained smart.", 1.5) + _say("I trained every single day.", 3.0)
    assert tr.find_takes(words) == []
    emphasis = _say("it was very very heavy.", 0.0)
    assert tr.find_takes(emphasis) == []


def test_takes_line_said_again_in_other_words():
    from stylebrain import transcript as tr
    words = (_say("Your bench is stuck because of your setup.", 0.0)
             + _say("Your bench is stuck because of the setup.", 4.0) + _say("Here is the fix.", 8.0))
    (take,) = tr.find_takes(words)
    assert (take.start, take.end, take.sure) == (0.0, 4.0, True)      # an exact run of four words: the old rule
    loose = (_say("Your bench stalls because your setup is off.", 0.0)
             + _say("Your bench stalls since the setup is off.", 4.0))
    (take,) = tr.find_takes(loose)
    assert (take.kind, take.sure, take.start, take.end) == ("said-again", False, 0.0, 4.0)


def test_takes_spoken_cue_removes_the_flub_and_the_cue():
    from stylebrain import transcript as tr
    words = (_say("Today we are testing my deadlift max.", 0.0) + _say("So the first thing is um the bar", 3.0)
             + _say("sorry let me start over.", 6.5) + _say("The first thing is bar path.", 9.0))
    takes = tr.find_takes(words)
    assert [(t.kind, t.sure, t.start, t.end) for t in takes] == [("cue", True, 3.0, 9.0)]
    maybe = _say("That was heavy.", 0.0) + _say("One more time.", 2.0) + _say("Up it goes.", 4.0)
    (take,) = tr.find_takes(maybe)
    assert (take.kind, take.sure) == ("cue", False)


def test_takes_stutter_is_only_a_suggestion():
    from stylebrain import transcript as tr
    words = _say("so I I think the bar path matters.", 0.0)
    (take,) = tr.find_takes(words)
    assert (take.kind, take.sure) == ("stutter", False) and take.end - take.start == pytest.approx(0.3)
    assert tr.find_retakes(words) == []


def test_takes_without_punctuation_only_trust_short_fragments():
    from stylebrain import transcript as tr
    words = _say("the reason I", 1.0) + _say("the reason most people stall is sleep", 3.0)
    assert [(t.kind, t.sure) for t in tr.find_takes(words)] == [("restart", True)]
    long = _say("the reason most people stall is sleep", 0.0) + _say("the reason most lifters stall is food", 4.0)
    assert all(t.kind != "restart" for t in tr.find_takes(long))
