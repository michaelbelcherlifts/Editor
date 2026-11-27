import itertools
import json
import shutil

import pytest

from stylebrain import autoclip as ac
from stylebrain.cli import main
from stylebrain.edl import EditError
from stylebrain.transcript import Word, from_subtitles


def _talk(lines: list[str], start: float = 0.0, gap: float = 0.3, pace: float = 0.3) -> list[Word]:
    out, t = [], start
    for line in lines:
        for tok in line.split():
            out.append(Word(tok, round(t, 3), round(t + pace * 0.9, 3)))
            t += pace
        t += gap
    return out


FILLER = ["and then we walked over to the rack and set up the bar for the next set today."] * 6
STRONG = ["Why do most lifters never add weight to their bench?",
          "I tested it for eight weeks with two different programs on myself.",
          "The first program had me benching heavy three times every single week.",
          "The second one had one heavy day and two lighter speed days instead.",
          "My shoulders hated the first one and the bar stalled after week four.",
          "Turns out the lighter days were the reason the second program kept moving.",
          "So the lesson is simple: recover between heavy days and the bar goes up."]


def _recording():
    a = _talk(FILLER)
    b = _talk(STRONG, start=a[-1].end + 1.5)
    c = _talk(FILLER, start=b[-1].end + 1.5)
    return a + b + c, b


def test_find_picks_the_moment_with_a_question_and_its_answer():
    words, strong = _recording()
    cands = ac.find(words, count=3, min_seconds=10, max_seconds=40)
    best = cands[0]
    assert best.lines[0]["text"].startswith("Why do most lifters")
    assert abs(best.start - strong[0].start) < 0.01
    assert best.lines[-1]["text"] in STRONG[-2:]          # ends on a payoff line, not in the chatter after
    assert any("answer" in r for r in best.reasons)


def test_find_never_overlaps_and_drops_repeats():
    words, _ = _recording()
    cands = ac.find(words, count=10, min_seconds=5, max_seconds=20)
    spans = sorted((c.start, c.end) for c in cands)
    assert all(a[1] <= b[0] for a, b in itertools.pairwise(spans))
    # the filler is said twelve times; it may be offered once, not again and again
    assert sum("walked over to the rack" in c.text for c in cands) <= 1


def test_rough_marks_a_start_that_leans_back():
    from stylebrain.story import sentences
    leaning = sentences(_talk(["And that is why it failed for me last week at the gym honestly.", *STRONG[1:]]))
    plain = sentences(_talk(STRONG))
    lean_score, reasons = ac._rough(leaning, 1.0)
    assert any("leans on what came before" in r for r in reasons)
    assert lean_score < ac._rough(plain, 1.0)[0]


def test_find_checks_its_limits():
    with pytest.raises(EditError):
        ac.find(_talk(STRONG), min_seconds=30, max_seconds=20)
    with pytest.raises(EditError):
        ac.find([], count=1)


def test_plan_cut_tightens_pauses_and_lists_every_cut():
    words = _talk(STRONG[:3], gap=1.2)
    c = ac.Candidate("c01", words[0].start, words[-1].end, 50, [], [])
    spans, log = ac.plan_cut(c, words)
    assert len(spans) == 3
    assert sum(1 for line in log if line.startswith("pause cut")) == 2
    played = sum(b - a for a, b in spans)
    assert played < (words[-1].end - words[0].start)


def test_plan_cut_cold_open_plays_first_and_once():
    words = _talk(STRONG)
    c = ac.Candidate("c01", words[0].start, words[-1].end, 50, [], [])
    last = [w for w in words if w.start >= _talk(STRONG[:6])[-1].end]
    cold = [last[0].start, last[-1].end]
    spans, log = ac.plan_cut(c, words, {"cold_open": cold})
    assert spans[0][0] <= cold[0] and spans[0][1] >= cold[1] - 0.01
    assert not any(a < cold[1] - 0.2 and b > cold[0] + 0.2 for a, b in spans[1:])
    assert any(line.startswith("cold open") for line in log)
    edit = ac.build_edit("src.mp4", 30.0, spans)
    heard = ac.timeline_words(edit, words)
    assert [w.text for w in heard[:3]] == ["So", "the", "lesson"]
    assert sum(w.text == "lesson" for w in heard) == 1


def test_plan_cut_refuses_a_long_cold_open():
    words = _talk(STRONG)
    c = ac.Candidate("c01", words[0].start, words[-1].end, 50, [], [])
    with pytest.raises(EditError):
        ac.plan_cut(c, words, {"cold_open": [0, 20]})


def _fake_steps(calls):
    def reframe(edit, w, h):
        calls.append("reframe")
        return edit, ["0.00s to 5.00s  x 0.40, y 0.30  (face)"]

    def captions(edit, words, w, h):
        calls.append(("captions", len(words)))
        return edit

    def hook(text, secs, fps, w, h):
        calls.append(("hook", text))
        return "hook.mov"

    return {"reframe": reframe, "captions": captions, "hook": hook}


def test_make_scores_with_the_judgement_and_story_gate(tmp_path):
    words = _talk(STRONG)
    c = ac.find(words, count=1, min_seconds=5, max_seconds=40)[0]
    calls = []
    good = ac.make(c, "src.mp4", words, tmp_path, {"story": 5, "promise": 5, "payoff": 5, "value": 4, "share": 4,
                                                    "trend": 3, "hook_text": "Bench stuck? Try this"},
                   render=False, fps=30.0, total_frames=100000, steps=_fake_steps(calls))
    flat = ac.make(c, "src.mp4", words, tmp_path / "flat", {"story": 1, "promise": 2, "payoff": 2, "value": 2, "share": 1},
                   render=False, fps=30.0, total_frames=100000, steps=_fake_steps([]))
    assert good.total > flat.total
    assert flat.score["cap"]["at"] == 55
    assert "reframe" in calls and ("hook", "Bench stuck? Try this") in calls
    assert (tmp_path / "c01.edit.json").exists() and (tmp_path / "c01.srt").read_text().strip()
    edit = json.loads((tmp_path / "c01.edit.json").read_text())
    assert edit["fill"] is True and edit["overlays"][0]["name"] == "text hook"


def test_make_skips_and_rejects_unknown_keys(tmp_path):
    words = _talk(STRONG)
    c = ac.find(words, count=1, min_seconds=5, max_seconds=40)[0]
    m = ac.make(c, "src.mp4", words, tmp_path, {"skip": "needs the earlier context"}, render=False, fps=30.0,
                total_frames=10000)
    assert m.skipped and m.score is None
    with pytest.raises(EditError):
        ac.make(c, "src.mp4", words, tmp_path, {"virality": 5}, render=False, fps=30.0, total_frames=10000)


def test_rank_orders_by_score_and_marks_repeats(tmp_path):
    words = _talk(STRONG)
    c1 = ac.find(words, count=1, min_seconds=5, max_seconds=40)[0]
    c2 = ac.Candidate("c02", c1.start, c1.end, 10, [], c1.lines)
    hi = ac.make(c1, "s.mp4", words, tmp_path, {"story": 5, "payoff": 5}, render=False, fps=30.0, total_frames=10 ** 6,
                 steps=_fake_steps([]))
    lo = ac.make(c2, "s.mp4", words, tmp_path, {"story": 3, "payoff": 2}, render=False, fps=30.0, total_frames=10 ** 6,
                 steps=_fake_steps([]))
    ranked = ac.rank([lo, hi])
    assert ranked[0] is hi and ranked[1].skipped == "repeats c01"
    page = ac.sheet(ranked, tmp_path / "review.html", "long.mp4")
    text = page.read_text()
    assert "One fix" in text and "Every cut" in text and "Nothing has been posted" in text


def test_youtube_vtt_word_times():
    vtt = """WEBVTT
Kind: captions
Language: en

00:00:04.080 --> 00:00:05.550 align:start position:0%

One<00:00:04.200><c> of</c><00:00:04.280><c> my</c>

00:00:05.550 --> 00:00:05.560 align:start position:0%
One of my

00:00:05.560 --> 00:00:06.790 align:start position:0%
One of my
big<00:00:05.760><c> [music]</c><00:00:05.900><c> &gt;&gt;</c><00:00:06.000><c> things.</c>

00:00:06.790 --> 00:00:06.800 align:start position:0%
big things.

00:00:06.800 --> 00:00:08.670 align:start position:0%
big things.
Mysteries.
"""
    words = from_subtitles(vtt)
    assert [w.text for w in words] == ["One", "of", "my", "big", "things.", "Mysteries."]
    assert words[1].start == 4.2 and words[3].start == 5.56 and words[4].start == 6.0
    assert words[5].start == 6.8 and words[5].end <= 7.8


def test_clip_commands_end_to_end_without_rendering(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    words, _ = _recording()
    t = tmp_path / "long.words.json"
    t.write_text(json.dumps([{"word": w.text, "start": w.start, "end": w.end} for w in words]))
    video = tmp_path / "long.mp4"
    if not shutil.which("ffmpeg"):
        pytest.skip("needs ffmpeg")
    from stylebrain import media
    media.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=gray:s=320x180:r=30:d={words[-1].end + 1:.1f}",
               "-pix_fmt", "yuv420p", str(video)])
    main(["clip-find", str(video), "--count", "3", "--min", "10", "--max", "40", "--out", "clips"])
    out = capsys.readouterr().out
    assert "c01" in out and "Judge each clip" in out
    (tmp_path / "clips" / "judgements.json").write_text(json.dumps({"c01": {"story": 4, "payoff": 4}}))
    main(["clip-cut", "clips", "--no-render", "--no-reframe", "--no-captions"])
    out = capsys.readouterr().out
    assert "#1 c01" in out and "nothing has been posted" in out
    review = json.loads((tmp_path / "clips" / "review.json").read_text())
    assert review[0]["id"] == "c01" and review[0]["cuts"]
    assert (tmp_path / "clips" / "review.html").exists()
