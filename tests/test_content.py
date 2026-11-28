import datetime as dt
import json

import pytest

from stylebrain import content
from stylebrain.cli import main
from stylebrain.content import Plan, count_this_week, quotas
from stylebrain.edl import EditError

MON = "2026-11-30"


def backlog(plan, strength=6, run=3, humour=3, life=2):
    for pillar, n in (("strength", strength), ("run", run), ("humour", humour), ("life", life)):
        for k in range(n):
            plan.add_idea(f"{pillar} {k}", pillar, hook=f"hook {pillar} {k}", location="gym" if pillar != "run" else "track")


def test_quotas_and_every_other_week():
    assert quotas(7, {"strength": 0.5, "run": 0.2, "humour": 0.2, "life": 0.1}) == {
        "strength": 4, "run": 1, "humour": 1, "life": 1}
    assert sum(quotas(10, {"a": 1, "b": 1, "c": 1}).values()) == 10
    weeks = [dt.date(2026, 11, 30) + dt.timedelta(days=7 * k) for k in range(4)]
    assert [count_this_week(0.5, w) for w in weeks] in ([1, 0, 1, 0], [0, 1, 0, 1])
    assert [count_this_week(7, w) for w in weeks] == [7, 7, 7, 7]


def test_ideas_series_and_validation(tmp_path):
    plan = Plan(tmp_path)
    a = plan.add_idea("Ep one", "run", series="mid-at-both")
    b = plan.add_idea("Ep two", "run", series="mid-at-both")
    assert (a["episode"], b["episode"]) == (1, 2) and a["status"] == "idea"
    with pytest.raises(EditError, match="unknown pillar"):
        plan.add_idea("x", "golf")
    with pytest.raises(EditError, match="unknown series"):
        plan.add_idea("x", "run", series="nope")
    with pytest.raises(EditError, match="unknown call to action"):
        plan.add_idea("x", "run", cta="buy now")
    plan.set_idea(a["id"], hook="New hook", score="77")
    assert plan.idea(a["id"])["score"] == 77.0
    plan.save()
    again = Plan(tmp_path)
    assert [e["title"] for e in again.series_view()[0]["episodes"]] == ["Ep one", "Ep two"]


def test_week_plan_follows_volume_mix_and_cta_rules(tmp_path):
    plan = Plan(tmp_path)
    plan.settings["volume"] = {"reel": 7}
    backlog(plan)
    plan.add_idea("On hold", "strength", hold="needs a meet")
    plan.add_idea("Ready first", "humour", status="approved")
    week = plan.propose_week(MON)
    posts = week["posts"]
    assert len(posts) == 7 and all(p["status"] == "proposed" for p in posts)
    assert len({p["date"] for p in posts}) == 7  # one a day
    pillars = [plan.idea(p["idea"])["pillar"] for p in sorted(posts, key=lambda p: p["date"])]
    assert pillars.count("strength") == 4 and all(a != b for a, b in zip(pillars, pillars[1:]))
    titles = {plan.idea(p["idea"])["title"] for p in posts}
    assert "Ready first" in titles and "On hold" not in titles
    ctas = [p["cta"] for p in posts]
    assert ctas.count("coaching") <= 2 and ctas.count("none") >= 3
    assert all(p["platforms"] == ["instagram", "tiktok", "youtube-shorts", "facebook"] for p in posts)
    # Proposing again replaces the proposal instead of doubling it.
    plan.propose_week(MON)
    assert len([p for p in plan.posts if p["status"] == "proposed"]) == 7
    plan.approve_week(MON)
    assert all(p["status"] == "planned" for p in plan.posts)
    assert all(plan.idea(p["idea"])["status"] in ("planned", "approved") for p in plan.posts)


def test_explicit_coaching_counts_against_the_limit(tmp_path):
    plan = Plan(tmp_path)
    plan.settings["volume"] = {"reel": 5}
    plan.settings["pillars"] = {"strength": 1}
    for k in range(5):
        plan.add_idea(f"s{k}", "strength", cta="coaching" if k == 4 else None)
    plan.propose_week(MON)
    assert [p["cta"] for p in plan.posts].count("coaching") == 2


def test_shortfall_is_reported(tmp_path):
    plan = Plan(tmp_path)
    plan.settings["volume"] = {"reel": 7}
    backlog(plan, strength=1, run=0, humour=1, life=0)
    week = plan.propose_week(MON)
    assert len(week["posts"]) == 2 and any("empty" in s for s in week["shortfalls"])


def test_shoot_list_and_week_report(tmp_path):
    plan = Plan(tmp_path)
    a = plan.add_idea("Squat cue", "strength", location="gym", shots=["side angle"])
    b = plan.add_idea("5K test", "run", location="track")
    c = plan.add_idea("Already cut", "humour", status="edited")
    pa, pb, pc = (plan.schedule(i["id"], d) for i, d in ((a, "2026-12-01"), (b, "2026-12-03"), (c, "2026-12-04")))
    sl = plan.shoot_list(MON)
    assert set(sl["locations"]) == {"gym", "track"}  # the edited one is already filmed
    assert sl["locations"]["gym"][0]["film_by"] == "2026-11-29" and sl["locations"]["gym"][0]["shots"] == ["side angle"]
    assert sl["locations"]["track"][0]["shots"] == content.DEFAULT_SHOTS["reel"] and sl["guide"]
    plan.record_result(pa["id"], url="https://instagram.com/reel/X/", views=1200, sends=30)
    plan.set_post(pb["id"], status="posted")
    rep = plan.week_report(MON)
    assert (rep["planned"], rep["posted"]) == (3, 2)
    assert rep["missed"][0]["post"] == pc["id"] and rep["totals"] == {"views": 1200, "sends": 30}
    assert plan.idea(a["id"])["status"] == "measured" and plan.idea(b["id"])["status"] == "posted"
    text = content.format_week_report(rep)
    assert "2 of 3" in text and "Already cut" in text


def test_social_package_is_placed_around_the_reel(tmp_path):
    plan = Plan(tmp_path)
    reel = plan.schedule(plan.add_idea("Bench cue", "strength")["id"], "2026-12-02")
    package = {"name": "bench-cue", "reel_title": "Bench cue", "posts": [
        {"format": "cover", "suggested_day": 0, "files": ["cover.png"], "status": "draft"},
        {"format": "story", "suggested_day": 0.1, "caption": "Did you know?", "cta": "comment",
         "sticker": "Poll: Agree / No way", "files": ["s1.png"], "status": "draft"},
        {"format": "carousel", "suggested_day": 3, "caption": "Bench cues\nslide text", "cta": "save",
         "files": ["c1.png", "c2.png"], "status": "draft"}]}
    made = plan.import_social(package, reel["id"])
    assert [(p["format"], p["date"], p["cta"]) for p in made] == [
        ("story", "2026-12-02", "comment"), ("carousel", "2026-12-05", "save")]
    carousel = plan.idea(made[1]["idea"])
    assert carousel["title"] == "Bench cues" and carousel["pillar"] == "strength" and carousel["status"] == "edited"
    assert "sticker: Poll" in plan.idea(made[0]["idea"])["note"]
    assert "cover.png" in plan.idea(reel["idea"])["note"]


def test_commands_end_to_end(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    ideas = [{"title": f"Idea {k}", "pillar": p, "hook": "Hook"} for k, p in
             enumerate(["strength"] * 4 + ["run", "humour", "life"])]
    ideas.append({"title": "Squat carousel", "pillar": "strength", "format": "carousel"})
    (tmp_path / "ideas.json").write_text(json.dumps(ideas))
    main(["series-add", "one-cue", "--name", "One cue", "--premise", "One fix per episode"])
    main(["idea-add", "Cue one", "--pillar", "strength", "--series", "one-cue", "--shots", "side;front"])
    main(["idea-import", "ideas.json", "--source", "trend"])
    main(["plan-settings", "--set", "volume.long-form=0", "--set", "coaching_per_week=1"])
    main(["plan-week", MON])
    out = capsys.readouterr().out
    assert "Proposed 8 posts" in out and "nothing posts by itself" in out
    main(["plan-approve", MON])
    main(["calendar", "--start", MON])
    out = capsys.readouterr().out
    assert "Week of Mon 30 Nov 2026" in out and "One cue #1" in out
    main(["post-set", "p1", "--date", "2026-12-06"])
    main(["shoot-list", MON])
    assert "Recording guide" in capsys.readouterr().out
    main(["calendar", "--start", MON, "--days", "28", "--html", "cal.html"])
    page = (tmp_path / "cal.html").read_text()
    assert page.startswith("<!DOCTYPE html>") and "Squat carousel" in page
    main(["post-result", "p1", "--views", "500"])
    main(["week-report", MON])
    assert "1 of 8" in capsys.readouterr().out
    main(["idea-list", "--status", "measured"])
    assert "1 ideas" in capsys.readouterr().out
    assert (tmp_path / "library" / "content" / "plan.json").exists()
    with pytest.raises(SystemExit):
        main(["post-set", "p999", "--cta", "none"])


def test_bets_are_stated_then_scored(tmp_path, monkeypatch, capsys):
    plan = Plan(tmp_path)
    a = plan.add_idea("How to deadlift", "strength", hook_type="how-to", topic="lift-teach", pace="steady", goal="follows")
    b = plan.add_idea("Powerlifters defend this", "humour", hook_type="tribe", topic="gym-joke", pace="fast", goal="reach")
    c = plan.add_idea("Untagged", "life")
    with pytest.raises(EditError, match="unknown goal"):
        plan.add_idea("x", "run", goal="money")
    with pytest.raises(EditError, match="unknown hook type"):
        plan.set_idea(c["id"], hook_type="vibes")
    assert "expect 1 follows per 1,000" in plan.bet_line(a) and "how-to hook" in plan.bet_line(a)
    pa, pb, pc = (plan.schedule(i["id"], "2026-12-0" + str(k)) for k, i in enumerate((a, b, c), 1))
    assert len(plan.bets()["open"]) == 2
    plan.record_result(pa["id"], reach=20000, follows=40, sends=10)   # 2 follows per 1,000: won
    plan.record_result(pb["id"], reach=12000, sends=30, follows=2)    # 2.5 shares per 1,000, under the hit line: lost
    plan.record_result(pc["id"], reach=5000)
    out = plan.bets()
    won = {s["title"]: s["won"] for s in out["scored"]}
    assert won == {"How to deadlift": True, "Powerlifters defend this": False, "Untagged": None}
    assert out["by"]["goal"]["follows"]["won"] == 1 and not out["by"]["goal"]["follows"]["enough"]
    assert plan.rows("2026-11-30", 7)[0]["bet"].startswith("how-to hook")
    text = content.format_bets(out)
    assert "won " in text and "too few to call" in text


def test_series_keep_their_weekday(tmp_path):
    plan = Plan(tmp_path)
    plan.settings["volume"] = {"reel": 7}
    plan.add_series("normal-things", "Powerlifter does normal things", "Wordless, a normal task done like a lifter.")
    plan.data["series"]["normal-things"]["day"] = "Wed"
    plan.data["series"]["one-cue"]["day"] = "Mon"
    plan.data["series"]["strong-vs-runner"]["merged_into"] = "mid-at-both"
    plan.data["series"]["strong-vs-runner"]["day"] = "Fri"
    plan.add_series("teammate", "Humbling my teammate", "x")
    plan.data["series"]["teammate"]["day"] = "Sat (every other week, when a teammate is free)"
    backlog(plan)
    plan.add_idea("Firewood", "humour", series="normal-things")
    plan.add_idea("Groceries", "humour", series="normal-things")
    plan.add_idea("Cue two", "strength", series="one-cue")
    plan.add_idea("Cue one", "strength", series="one-cue")
    plan.add_idea("Vs", "run", series="strong-vs-runner")
    plan.add_idea("Teammate", "humour", series="teammate")
    weeks = [dt.date(2026, 11, 30) + dt.timedelta(days=7 * k) for k in range(2)]
    for w in weeks:
        plan.propose_week(w)
    by_day = {p["date"]: plan.idea(p["idea"]) for p in plan.posts}
    assert by_day["2026-11-30"]["title"] == "Cue two" and by_day["2026-12-07"]["title"] == "Cue one"
    assert by_day["2026-12-02"]["title"] == "Firewood" and by_day["2026-12-09"]["title"] == "Groceries"
    assert len(plan.posts) == 14 and len(set(by_day)) == 14  # still one reel a day
    assert by_day["2026-12-04"]["title"] != "Vs"  # merged series has no day of its own
    sats = [by_day[d]["title"] for d in ("2026-12-05", "2026-12-12")]
    assert sats.count("Teammate") == 1  # every other week only


def test_replanning_keeps_hand_placed_proposals(tmp_path):
    plan = Plan(tmp_path)
    plan.settings["volume"] = {"reel": 7}
    backlog(plan)
    trend = plan.add_idea("Trend joke", "humour")
    plan.schedule(trend["id"], "2026-12-02", status="proposed")
    plan.propose_week(MON)
    plan.propose_week(MON)
    week = [p for p in plan.posts if p["status"] == "proposed"]
    assert len(week) == 7 and any(p["idea"] == trend["id"] and p["date"] == "2026-12-02" for p in week)
