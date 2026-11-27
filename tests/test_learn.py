import json
import random

import pytest

np = pytest.importorskip("numpy")

from stylebrain import learn  # noqa: E402
from stylebrain.cli import main  # noqa: E402
from stylebrain.edl import EditError  # noqa: E402
from stylebrain.transcript import Word  # noqa: E402


def say(text, start, each=0.25, gap=0.05):
    out, t = [], start
    for w in text.split():
        out.append(Word(w, round(t, 3), round(t + each, 3)))
        t += each + gap
    return out


def test_attributes_read_the_hook_and_the_pace():
    a = learn.attributes(say("stop making these 3 mistakes on your bench", 0.1) + say("tuck your elbows", 6.0), 20.0,
                         cuts=[1.0, 2.5, 8.0], frame={"width": 1080, "height": 1920}, judge={"promise": 4})
    assert a["hook_warning"] == 1 and a["hook_number"] == 1 and a["hook_you"] == 1 and a["hook_question"] == 0
    assert a["first_word_at"] == 0.1 and a["longest_pause"] > 3
    assert a["cuts_in_first_3s"] == 2 and a["cuts_per_minute"] == 9.0 and a["vertical"] == 1
    assert a["judge_promise"] == 4 and 0 <= a["score_hook"] <= 1 and "score_total" in a
    assert "cuts_per_minute" not in learn.attributes(say("hello there", 0), 5.0)


def synthetic(n, seed=1, noise=0.15):
    """Clips where an early first word and more cuts really do raise reach, and warmth does nothing."""
    r = random.Random(seed)
    clips = []
    for i in range(n):
        first, cuts, warm = r.uniform(0, 3), r.uniform(5, 40), r.uniform(-0.1, 0.1)
        reach = 1.0 - 0.4 * first + 0.03 * cuts + r.gauss(0, noise)
        parts = {f"score_{p}": r.random() for p in learn.PARTS}
        parts["score_hook"] = 1 - first / 3
        clips.append({"id": f"c{i}", "mine": i % 2 == 0,
                      "attributes": {"first_word_at": first, "cuts_per_minute": cuts, "warmth": warm, **parts},
                      "outcome": {"views": 10 ** (reach + 4), "subscribers": 10 ** 4}})
    return clips


def test_fit_finds_the_planted_signal_and_ignores_the_decoy():
    result = learn.fit(synthetic(60))
    effect = {e["attribute"]: e for e in result["effects"]}
    assert effect["first_word_at"]["effect"] < 0 and effect["cuts_per_minute"]["effect"] > 0
    assert effect["first_word_at"]["steady"] > 0.95
    assert abs(effect["warmth"]["effect"]) < abs(effect["cuts_per_minute"]["effect"]) / 4
    assert result["predicts_unseen_r2"] > 0.6 and result["trust"] == "a usable signal"
    assert result["weights"]["hook"] > learn.PARTS["hook"]
    assert sum(result["weights"].values()) == pytest.approx(100, abs=0.5)
    assert "Goes with doing better" in learn.report(result)


def test_fit_says_so_when_there_is_nothing_to_learn():
    clips = synthetic(40, noise=0.1)
    r = random.Random(5)
    for c in clips:
        c["outcome"]["views"] = 10 ** r.uniform(3, 6)
    assert learn.fit(clips)["trust"] == "no better than guessing the average"


def test_fit_refuses_too_few_clips_and_small_sets_are_marked_rough():
    with pytest.raises(EditError, match="12 is the least"):
        learn.fit(synthetic(8))
    assert learn.fit(synthetic(20))["trust"] == "a rough read; treat as hints"
    assert learn.fit(synthetic(60), only_mine=True)["clips"] == 30


def test_analytics_import_and_commands(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "studio.csv").write_text(
        "Content,Video title,Views,Average percentage viewed (%),Shares\n"
        "Total,,5000,60,10\nabc123XYZ_-,Bench tips,\"4,000\",72.5,9\nzzz999AAA11,Squat tips,1000,41,1\n")
    main(["clip-import", "studio.csv", "--subscribers", "2000"])
    assert "2 clips read" in capsys.readouterr().out
    words = tmp_path / "w.json"
    words.write_text(json.dumps([{"word": w.text, "start": w.start, "end": w.end} for w in say("want a bigger bench", 0.2)]))
    main(["clip-add", "abc123XYZ_-", "--transcript", str(words), "--seconds", "20", "--judge", '{"promise": 5}'])
    clip = next(c for c in learn.load_all() if c["id"] == "abc123XYZ_-")
    assert clip["mine"] and clip["about"] == "Bench tips"
    assert clip["outcome"] == {"views": 4000.0, "retention": 72.5, "shares": 9.0, "subscribers": 2000}
    assert clip["attributes"]["hook_question"] == 1
    assert learn.target_value(clip["outcome"], "reach") == pytest.approx(0.301, abs=0.001)
    assert learn.target_value(clip["outcome"], "retention") == 72.5
    main(["clip-list"])
    assert "2 clips" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["learn"])


def test_instagram_export_is_read_by_permalink_and_reels_only(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ig.csv").write_text(
        "sep=,\n"
        "Post ID,Account username,Description,Duration (sec),Publish time,Permalink,Post type,Views,Reach,Likes,Shares,Follows,Comments,Saves\n"
        '178,michael,"Bench cue, try it",31,11/01/2026 09:00,https://www.instagram.com/reel/DAbc_12-xyz/,IG reel,12000,9000,800,90,12,40,150\n'
        "179,michael,Gym selfie,0,11/02/2026 09:00,https://www.instagram.com/p/DPhoto00001/,IG image,900,700,80,1,0,2,3\n")
    main(["clip-import", "ig.csv", "--followers", "3000"])
    assert "1 clips read" in capsys.readouterr().out
    clip = learn.load_all()[0]
    assert clip["id"] == "DAbc_12-xyz" and clip["mine"] and clip["about"] == "Bench cue, try it"
    o = clip["outcome"]
    assert (o["views"], o["reach"], o["shares"], o["saves"], o["seconds"], o["subscribers"]) == (12000, 9000, 90, 150, 31, 3000)
    assert learn.target_value(o, "sends") == pytest.approx(10.0)
    assert learn.target_value(o, "saves") == pytest.approx(16.67, abs=0.01)
    assert learn.target_value(o, "reach") == pytest.approx(0.602, abs=0.001)
    main(["clip-add", "DAbc_12-xyz", "--retention", "64"])
    assert learn.load_all()[0]["outcome"]["retention"] == 64 and learn.load_all()[0]["outcome"]["views"] == 12000
    main(["clip-import", "ig.csv", "--all-posts"])
    assert "2 clips read" in capsys.readouterr().out
    (tmp_path / "bad.csv").write_text("Date,Followers\n1,2\n")
    with pytest.raises(SystemExit):
        main(["clip-import", "bad.csv"])
    assert "Columns in the file: Date, Followers" in capsys.readouterr().err
