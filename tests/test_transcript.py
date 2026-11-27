import json

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
