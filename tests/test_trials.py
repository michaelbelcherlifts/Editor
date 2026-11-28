import json
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

from stylebrain import media, publish, trials  # noqa: E402
from stylebrain.cli import main  # noqa: E402
from test_publish import FakeApps  # noqa: E402


def _clip(path, colour, seconds, size="108x192"):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={colour}:s={size}:r=30:d={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-af", "volume=0.1",
                    "-pix_fmt", "yuv420p", "-shortest", str(path)], check=True)
    return path


@pytest.fixture(scope="module")
def reel(tmp_path_factory):
    """A 6 s reel: 2 s red, then 4 s blue (one hard cut at 2 s)."""
    d = tmp_path_factory.mktemp("reel")
    a, b = _clip(d / "a.mp4", "red", 2), _clip(d / "b.mp4", "blue", 4)
    out = d / "reel.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(a), "-i", str(b), "-filter_complex",
                    "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]",
                    "-pix_fmt", "yuv420p", str(out)], check=True)
    return out


@pytest.fixture
def card(monkeypatch):
    """The hook card without a browser: a white box with alpha."""
    def fake(v, seconds, width, height, fps, out):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"color=c=white@1.0:s={width}x{height // 4}:r={fps}:d={seconds},format=yuva444p10le",
                        "-vf", f"pad={width}:{height}:0:0:color=black@0.0", "-c:v", "prores_ks", "-profile:v", "4444",
                        "-pix_fmt", "yuva444p10le", str(out)], check=True)
        return out
    monkeypatch.setattr(trials, "_hook_card", fake)


def spec(reel, **extra):
    return {"reel": "Squat 501!", "video": str(reel), "goal": "reach", "caption": "Two years off. Then 501.",
            "variants": [
                {"kind": "control"},
                {"kind": "hook_text", "text": "2 YEARS|OFF", "accent": "2", "seconds": 1.0, "cover": [0, 0, 108, 40],
                 "tags": {"hook_type": "stakes"}, "hypothesis": "stakes beat the number"},
                {"kind": "opening", "start": 2.0},
                {"kind": "length", "cut": [[3.0, 4.5]]},
                {"kind": "pace", "speed": 1.5},
            ], **extra}


def _colour(file, t):
    r, g, b = media.read_frame(str(file), t, width=16).reshape(-1, 3).mean(axis=0)
    return "red" if r > 150 and b < 90 else "blue" if b > 150 and r < 90 else "white" if min(r, g, b) > 200 else "other"


# ---------------------------------------------------------------- the spec

def test_spec_needs_one_control_and_one_change_each(reel):
    s = spec(reel)
    assert trials.check_spec(s, 6.0) == []
    bad = spec(reel)
    bad["variants"][0] = {"kind": "pace", "speed": 1.1}
    bad["variants"][1]["speed"] = 1.2                     # hook text and pace in one version
    bad["variants"][3] = {"kind": "length", "cut": [[5.0, 9.0]]}
    bad["variants"][4] = {"kind": "caption", "caption": "Hit [weight] today"}
    problems = " | ".join(trials.check_spec(bad, 6.0))
    assert "exactly one control" in problems
    assert "changes more than one thing: speed" in problems
    assert "runs past the end" in problems
    assert "[placeholder]" in problems


def test_suggest_drafts_five_with_a_sharp_story_first_opening(reel):
    s = trials.suggest(reel, "My Reel", hooks=["2 years off squatting"], goal="follows")
    kinds = [v["kind"] for v in s["variants"]]
    assert kinds == ["control", "hook_text", "opening", "length", "pace"]
    assert s["reel"] == "my-reel" and s["goal"] == "follows"
    opening = s["variants"][2]
    assert 2.0 <= opening["start"] <= 2.2                 # the cut at 2 s
    a, b = s["variants"][3]["cut"][0]
    assert 2.0 < a < b < 6.0                              # inside the longest shot
    with pytest.raises(trials.TrialError):
        trials.suggest(reel, "x", goal="likes")


# ---------------------------------------------------------------- rendering

def test_make_renders_five_labelled_versions_each_changing_one_thing(reel, tmp_path, card):
    pytest.importorskip("numpy")
    r = trials.make(spec(reel), base=tmp_path, log=lambda *a: None)
    folder = tmp_path / "library" / "trials" / "squat-501"
    assert r["reel"] == "squat-501"
    names = [p.name for p in sorted(folder.glob("*.mp4"))]
    assert names == ["squat-501-v1-control.mp4", "squat-501-v2-hook-text.mp4", "squat-501-v3-opening.mp4",
                     "squat-501-v4-length.mp4", "squat-501-v5-pace.mp4"]
    secs = {v["id"]: v["seconds"] for v in r["variants"]}
    assert secs["v1"] == pytest.approx(6.0, abs=0.1) and secs["v2"] == pytest.approx(6.0, abs=0.1)
    assert secs["v3"] == pytest.approx(4.0, abs=0.1)       # starts at the cut
    assert secs["v4"] == pytest.approx(4.5, abs=0.1)       # 1.5 s cut out
    assert secs["v5"] == pytest.approx(4.0, abs=0.15)      # 1.5x
    files = {v["id"]: v["file"] for v in r["variants"]}
    assert _colour(files["v1"], 0.5) == "red" and _colour(files["v3"], 0.2) == "blue"
    top = media.read_frame(files["v2"], 0.3, width=16)
    assert top[:3].mean() > 200 and _colour(files["v2"], 1.5) == "red"   # the card, then gone
    assert all(media.has_audio(f) for f in files.values())
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags=comment", "-of", "default=nw=1:nk=1",
                            files["v4"]], capture_output=True, text=True).stdout
    assert probe.strip() == "trial squat-501 v4 length"
    saved = json.loads((folder / "trial.json").read_text())
    assert [v["kind"] for v in saved["variants"]] == ["control", "hook_text", "opening", "length", "pace"]
    assert saved["variants"][1]["tags"] == {"hook_type": "stakes"}
    assert saved["variants"][3]["change"] == "cuts 3-4.5s"
    assert (folder / "first-frames.jpg").exists()
    sheet = (folder / "post-sheet.md").read_text()
    assert "Share to everyone automatically" in sheet and "squat-501-v5-pace.mp4" in sheet
    # a posted set is never overwritten
    saved["variants"][0]["posted"] = "2026-11-30T18:00"
    (folder / "trial.json").write_text(json.dumps(saved))
    with pytest.raises(trials.TrialError, match="already has posted"):
        trials.make(spec(reel), base=tmp_path, log=lambda *a: None)


def test_opening_can_move_a_stretch_to_the_front(reel, tmp_path):
    pytest.importorskip("numpy")
    s = {"reel": "front", "video": str(reel),
         "variants": [{"kind": "control"}, {"kind": "opening", "front": [4.0, 5.0]}]}
    r = trials.make(s, base=tmp_path, log=lambda *a: None)
    v = r["variants"][1]
    assert v["seconds"] == pytest.approx(6.0, abs=0.1)
    assert _colour(v["file"], 0.2) == "blue" and _colour(v["file"], 1.5) == "red"


# ---------------------------------------------------------------- schedule, results, winner

def _record(n=5):
    return {"reel": "r", "goal": "reach", "seconds": 20,
            "variants": [{"id": f"v{i}", "kind": "control" if i == 1 else "hook_text", "seconds": 20, "change": "",
                          "file": f"v{i}.mp4", "tags": {}, "results": {}, "posted": None, "scheduled": None}
                         for i in range(1, n + 1)]}


def test_schedule_ends_two_days_before_the_feed_day_and_warns_past_the_cap(tmp_path):
    r = _record()
    assert trials.schedule(r, share_on="2026-12-06", base=tmp_path) == []
    assert [v["scheduled"] for v in r["variants"]] == [f"2026-11-{d}T18:00" for d in (30,)] + \
        [f"2026-12-0{d}T18:00" for d in (1, 2, 3, 4)]
    trials.save(r, tmp_path)
    other = _record()
    other["reel"] = "other"
    warn = trials.schedule(other, start="2026-12-02 09:00", gap_hours=1, base=tmp_path)
    assert warn and "2026-12-02: 6 trials" in warn[0]


def test_score_names_a_clear_winner_only_when_beyond_chance():
    r = _record(3)
    base = {"views": 5000, "reach": 4800, "skip_rate": 45, "avg_watch": 8, "likes": 100, "shares": 20, "saves": 10}
    trials.record_result(r, "v1", url="u1", hours=24, **base)
    trials.record_result(r, "v2", url="u2", hours=24, **{**base, "skip_rate": 35, "shares": 60, "avg_watch": 11})
    trials.record_result(r, "v3", url="u3", hours=25, **{**base, "shares": 22})
    s = trials.score(r)
    assert s["winner"] == "v2" and s["confidence"] == "clear"
    assert s["lift"]["v2"]["shares_k"] == 3.0 and s["lift"]["v2"]["skip"] == pytest.approx(-0.1)
    assert "v2" in trials.format_score(s, r) and "trial-promote" in trials.format_score(s, r)

    close = _record(2)
    trials.record_result(close, "v1", url="a", **base)
    trials.record_result(close, "v2", url="b", **{**base, "shares": 23})
    assert trials.score(close)["confidence"] == "lean"

    early = _record(2)
    trials.record_result(early, "v1", url="a", **{**base, "views": 120})
    trials.record_result(early, "v2", url="b", **base)
    assert trials.score(early)["confidence"] == "too early"

    with pytest.raises(trials.TrialError):
        trials.record_result(r, "v1", skip_rate=140)


def test_promote_keeps_his_choice_and_learn_reads_across_reels():
    sets = []
    for n in range(3):
        r = _record(3)
        r["reel"] = f"r{n}"
        r["variants"][2]["kind"] = "pace"
        r["variants"][1]["tags"] = {"hook_type": "stakes"}
        base = {"views": 3000, "reach": 3000, "skip_rate": 50, "avg_watch": 8, "shares": 10}
        trials.record_result(r, "v1", url="a", posted="2026-12-01T18:00", **base)
        trials.record_result(r, "v2", url="b", posted="2026-12-02T18:00", **{**base, "skip_rate": 40, "shares": 30})
        trials.record_result(r, "v3", url="c", posted="2026-12-03T18:00", **{**base, "skip_rate": 55, "shares": 8})
        sets.append(r)
    trials.promote(sets[0], "v3")
    assert sets[0]["promoted"] == "v3" and sets[0]["winner"] == "v2"
    res = trials.learn(sets)
    assert res["reels"] == 3
    assert res["kinds"]["hook_text"] == {"tests": 3, "beat_control": 3, "won": 3, "mean_gain": pytest.approx(
        res["kinds"]["hook_text"]["mean_gain"])}
    assert res["kinds"]["pace"]["beat_control"] == 0
    assert res["tags"]["hook_type=stakes"]["tests"] == 3
    assert set(res["by_position"]) == {1, 2, 3}
    assert "Fewer than 5 reels" in trials.format_learn(res)


# ---------------------------------------------------------------- posting as a trial, and the commands

def test_trial_publish_posts_a_trial_with_manual_sharing_once(reel, tmp_path, monkeypatch):
    fake = FakeApps()
    monkeypatch.setattr(publish, "http", fake)
    monkeypatch.setattr(publish, "sleep", lambda s: None)
    vid = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=1080x1920:r=30:d=1",
                    "-pix_fmt", "yuv420p", str(vid)], check=True)
    r = _record(2)
    r["caption"] = "Two years off. Then 501."
    for v in r["variants"]:
        v["file"] = str(vid)
    trials.save(r, tmp_path)
    publish.save_account("instagram", {"ig_user_id": "17", "access_token": "t"}, tmp_path)
    assert publish.publish_trial("r", "v2", dry_run=True, base=tmp_path)["trial"] is True
    assert not fake.calls
    got = publish.publish_trial("r", "v2", base=tmp_path)
    assert got["privacy"] == "trial" and got["url"] == "https://www.instagram.com/reel/XYZ/"
    form = [c for c in fake.calls if c["url"].endswith("/17/media")][0]["form"]
    assert json.loads(form["trial_params"]) == {"graduation_strategy": "MANUAL"}
    assert "share_to_feed" not in form
    assert trials.load("r", tmp_path)["variants"][1]["url"] == got["url"]
    with pytest.raises(publish.PublishError, match="already posted"):
        publish.publish_trial("r", "v2", base=tmp_path)


def test_commands_record_results_and_score(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    trials.save(_record(2), tmp_path)
    main(["trial-result", "r", "v1", "--url", "https://instagram.com/reel/a", "--views", "4000", "--reach", "3900",
          "--skip-rate", "50", "--shares", "10", "--avg-watch", "7", "--hours", "24"])
    main(["trial-result", "r", "2", "--url", "https://instagram.com/reel/b", "--views", "4000", "--reach", "3900",
          "--skip-rate", "38", "--shares", "40", "--avg-watch", "10", "--hours", "24"])
    main(["trial-score", "r"])
    out = capsys.readouterr().out
    assert "v2" in out and "winner" in out and "confidence: clear" in out
    main(["trial-promote", "r", "v2"])
    main(["trial-list"])
    assert "promoted v2" in capsys.readouterr().out
