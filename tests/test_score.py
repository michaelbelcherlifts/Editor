import json

import pytest

from stylebrain import score as sc
from stylebrain.cli import main
from stylebrain.edl import EditError
from stylebrain.transcript import Word


def say(text, start, each=0.25, gap=0.05):
    out, t = [], start
    for w in text.split():
        out.append(Word(w, round(t, 3), round(t + each, 3)))
        t += each + gap
    return out


GOOD = say("stop benching like this it wrecks your shoulders tuck your elbows and watch the bar path", 0.1)
BEST = {"promise": 5, "payoff": 5, "value": 5, "share": 5, "trend": 5, "text_on_frame_1": True, "captions": True}


def test_a_clip_that_does_everything_scores_100():
    s = sc.score(GOOD, 30.0, cuts=[0.8, 3, 6, 9, 12, 15, 18, 21, 24, 27], frame={"width": 1080, "height": 1920},
                 audio={"loudness_lufs": -14.0}, judge=BEST)
    assert s.total == 100 and s.verdict == "post first" and not s.penalties
    assert [p.out_of for p in s.parts] == [25, 20, 15, 15, 10, 10, 5]


def test_slow_start_pauses_and_wide_frame_lose_points_where_expected():
    slow = say("so um hey guys", 0.5) + say("today we bench", 4.0) + say("and that is it", 8.0)
    s = sc.score(slow, 80.0, cuts=[20.0], frame={"width": 1920, "height": 1080}, audio={"loudness_lufs": -25.0},
                 judge={**BEST, "text_on_frame_1": False, "captions": False})
    by = {p.name: p for p in s.parts}
    assert by["Hook"].points == 5.0 and "first real word at 4.0s" in by["Hook"].why
    assert by["Pacing"].points < 3 and by["Craft"].points == 0
    assert ("Over 60 seconds with no new beat after 30 s", 5) in s.penalties
    assert s.weakest.name == "Craft"


def test_fillers_do_not_count_as_the_first_word():
    assert sc.first_real_word(say("so hey guys stop", 0)).text == "stop"
    assert sc.first_real_word(say("um uh", 0)) is None


def test_missing_judgements_are_neutral_and_flagged():
    s = sc.score(GOOD, 30.0)
    assert 45 <= s.total <= 65
    assert "not fully judged" in s.text()
    assert not next(p for p in s.parts if p.name == "Payoff").judged


def test_penalties_and_bad_input():
    s = sc.score(GOOD, 30.0, judge={**BEST, "needs_context": True, "undelivered": True, "mid_sentence": True})
    assert sum(v for _, v in s.penalties) == 30
    with pytest.raises(EditError):
        sc.score(GOOD, 30.0, judge={"promise": 9})
    with pytest.raises(EditError):
        sc.score(GOOD, 30.0, judge={"vibes": 3})


def test_score_command(tmp_path, capsys):
    t = tmp_path / "w.json"
    t.write_text(json.dumps([{"word": w.text, "start": w.start, "end": w.end} for w in GOOD]))
    main(["score", "--transcript", str(t), "--seconds", "30", "--judge", json.dumps(BEST), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert data["parts"][0]["name"] == "Hook" and data["total"] > 80
    main(["score", "--questions"])
    assert "promise:" in capsys.readouterr().out
