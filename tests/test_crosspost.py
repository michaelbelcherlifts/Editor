import json
import subprocess
from pathlib import Path

import pytest

from stylebrain import crosspost
from stylebrain.cli import main
from stylebrain.content import Plan
from stylebrain.edl import EditError
from stylebrain.transcript import Word

MON = "2026-11-30"


def words_from(text, start=0.0, step=0.4):
    out, t = [], start
    for w in text.split():
        out.append(Word(w, t, t + step * 0.8))
        t += step
    return out


def idea(**kw):
    base = {"id": "i1", "title": "Fix your bench arch", "pillar": "strength", "hook": "Your bench arch is costing you [weight]",
            "series": None, "episode": None}
    base.update(kw)
    return base


def test_each_platform_gets_its_own_words_and_limits():
    w = words_from("Your bench arch is costing you. Squeeze your shoulder blades before you unrack the bar. "
                   "Then drive your feet into the floor the whole set.")
    vs = crosspost.build(idea(), ["instagram", "tiktok", "youtube-shorts"], "coaching", words=w,
                         brand={"site": "nospotter.com"}, facts={"width": 1080, "height": 1920, "seconds": 30})
    ig, tt, yt = vs
    assert ig.text["caption"].startswith("Your bench arch")
    assert "Squeeze your shoulder blades" in ig.text["caption"]
    assert "link in bio" in ig.text["caption"] and len(ig.hashtags) <= 5
    assert ig.hashtags[0] == "#benchpress"
    assert "powerlifting tips" in tt.text["caption"] and len(tt.hashtags) == 4
    assert yt.text["title"] == "Fix your bench arch" and len(yt.hashtags) == 3
    assert yt.text["description"].startswith("Your bench arch")
    assert "channel page" in yt.text["description"] and "link in bio" not in yt.text["description"]
    # the placeholder must be filled before posting, on every platform
    assert all(any("[weight]" in p for p in v.problems) for v in vs)


def test_none_cta_means_no_ask_and_worlds_is_flagged():
    vs = crosspost.build(idea(hook="Training for worlds", title="Worlds prep"), ["instagram"], "none",
                         facts={"width": 1080, "height": 1920, "seconds": 20})
    cap = vs[0].text["caption"]
    assert "Follow" not in cap and "link" not in cap
    assert any("worlds" in p for p in vs[0].problems)


def test_follow_names_the_next_episode():
    line = crosspost.cta_line("follow", "tiktok", idea(episode=3), {}, "Mid at both?")
    assert line == 'Follow for episode 4 of "Mid at both?".'
    assert crosspost.cta_line("follow", "youtube-shorts", idea(), {}).startswith("Subscribe")


def test_video_checks_shape_and_length():
    vs = crosspost.build(idea(hook="Clean hook"), ["youtube-shorts", "youtube"], "none",
                         facts={"width": 1080, "height": 1920, "seconds": 200},
                         long_facts={"width": 1080, "height": 1920, "seconds": 600}, video="a.mp4", long_video="a.mp4")
    shorts, long = vs
    assert any("3 minute limit" in p for p in shorts.problems)
    assert any("1920x1080" in p for p in long.problems)
    nothing = crosspost.build(idea(hook="Clean hook"), ["tiktok"], "none")[0]
    assert any("no video yet" in p for p in nothing.problems)
    with pytest.raises(EditError, match="unknown platform"):
        crosspost.build(idea(), ["myspace"], "none")


def test_long_form_chapters_and_tags():
    text = " ".join(f"Point number {k} is about the squat and it matters a lot." for k in range(60))
    w = words_from(text, step=0.5)  # about 330 s
    v = crosspost.build(idea(title="How I squat 300 kg", hook="Clean hook", format="long-form"), ["youtube"], "coaching",
                        words=w, brand={"site": "nospotter.com"},
                        long_facts={"width": 1920, "height": 1080, "seconds": 330}, long_video="a.mp4")[0]
    ch = v.text["chapters"]
    assert len(ch) >= 3 and ch[0]["at"] == "0:00"
    secs = [c["seconds"] for c in ch]
    assert all(b - a >= 10 for a, b in zip(secs, secs[1:]))
    assert "0:00 " in v.text["description"] and "nospotter.com" in v.text["description"]
    assert len(", ".join(v.text["tags"])) <= 500 and "squat" in v.text["tags"]
    assert not v.problems


def test_hand_set_chapters_win_over_drafted_ones():
    text = " ".join(f"Point number {k} is about the squat and it matters a lot." for k in range(60))
    mine = [{"at": "0:00", "label": "Intro"}, {"at": "1:10", "label": "Why"}, {"at": "4:00", "label": "Results"}]
    v = crosspost.build(idea(title="How I squat 300 kg", hook="Clean hook", format="long-form"), ["youtube"], "coaching",
                        words=words_from(text, step=0.5), brand={"site": "nospotter.com"},
                        long_facts={"width": 1920, "height": 1080, "seconds": 330}, long_video="a.mp4",
                        chapter_list=mine)[0]
    assert v.text["chapters"] == mine
    assert "0:00 Intro\n1:10 Why\n4:00 Results" in v.text["description"]


def test_titles_are_cut_at_a_word():
    long = "word " * 40
    assert len(crosspost._fit_title(long, 100)) <= 100
    assert crosspost._fit_title(long, 100).endswith("…")


def _video(path, w, h, secs=2):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=gray:s={w}x{h}:r=30:d={secs}",
                    "-pix_fmt", "yuv420p", str(path)], check=True)


def test_make_writes_files_and_ties_into_the_calendar(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    plan = Plan(tmp_path)
    vid = tmp_path / "cut.mp4"
    _video(vid, 1080, 1920)
    (tmp_path / "cut.json").write_text(json.dumps([{"word": "Bench", "start": 0, "end": 0.3},
                                                   {"word": "tip.", "start": 0.3, "end": 0.6}]))
    a = plan.add_idea("Bench tip", "strength", hook="One bench cue", draft=str(vid), status="edited")
    b = plan.add_idea("Run day", "run", hook="Can a powerlifter run a mile")
    p1 = plan.schedule(a["id"], MON, cta="save")
    plan.schedule(b["id"], "2026-12-01")
    plan.save()

    rows = crosspost.week(plan, MON)
    assert [r["state"] for r in rows] == ["cut, not prepared", "waiting for the cut"]

    rows = crosspost.week(plan, MON, make_missing=True, base=tmp_path)
    assert rows[0]["state"] == "ready" and rows[0]["made"]
    folder = plan.post(p1["id"])["crosspost"]
    data = json.loads(Path(folder, "crosspost.json").read_text())
    assert {v["platform"] for v in data["versions"]} == {"instagram", "tiktok", "youtube-shorts", "facebook"}
    assert data["transcript"].endswith("cut.json")
    txt = Path(folder, "instagram.txt").read_text()
    assert "CAPTION" in txt and "One bench cue" in txt

    plan.record_result(p1["id"], url="https://instagram.com/reel/x", platform="instagram", views=100, saves=5)
    plan.record_result(p1["id"], url="https://tiktok.com/x", platform="tiktok", views=50)
    p = plan.post(p1["id"])
    assert p["urls"]["tiktok"] == "https://tiktok.com/x" and p["results"]["views"] == 150
    with pytest.raises(EditError, match="not planned for youtube"):
        plan.record_result(p1["id"], platform="youtube", views=1)
    assert "instagram" in crosspost.week(plan, MON)[0]["posted"]


def test_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    plan = Plan()
    a = plan.add_idea("Deadlift cue", "strength", hook="Pull the slack out first")
    p = plan.schedule(a["id"], MON, cta="follow")
    plan.save()
    vid = tmp_path / "d.mp4"
    _video(vid, 1080, 1920)
    main(["crosspost", p["id"], "--video", str(vid)])
    out = capsys.readouterr().out
    assert "4 versions" in out and "nothing was posted" in out
    main(["crosspost-week", MON])
    assert "1 of 1 ready to post" in capsys.readouterr().out
    main(["post-result", p["id"], "--platform", "tiktok", "--url", "https://tiktok.com/y", "--views", "10"])
    assert Plan().post(p["id"])["urls"] == {"tiktok": "https://tiktok.com/y"}


def test_facebook_added_to_older_reels_unless_turned_off(tmp_path):
    plan = Plan(tmp_path)
    a = plan.add_idea("Old reel", "strength", hook="Clean hook")
    p = plan.schedule(a["id"], MON, platforms=["instagram", "tiktok", "youtube-shorts"])
    r = crosspost.make(plan, p["id"], base=tmp_path)
    assert "facebook" in plan.post(p["id"])["platforms"] and len(r["versions"]) == 4
    main_settings = plan.settings
    main_settings["facebook_reels"] = False
    p2 = plan.schedule(a["id"], MON, platforms=["instagram"])
    crosspost.make(plan, p2["id"], base=tmp_path)
    assert plan.post(p2["id"])["platforms"] == ["instagram"]
