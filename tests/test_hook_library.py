import json
from pathlib import Path

import pytest

from stylebrain import story
from stylebrain.cli import main

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("line, kind", [
    ("Can I run a sub 5 minute mile?!", "challenge"),
    ("If you could bench 225 one time, I will fill your tank", "test"),
    ("Powerlifters vs bodybuilders between sets", "versus"),
    ("How many frying pans does it take to stop a bullet?", "how-many"),
    ("Elite powerlifter pretended to be a cleaner", "underdog"),
    ("Ranking best gym fails", "ranking"),
    ("How to deadlift: 5 simple steps", "how-to"),
    ("Powerlifters will genuinely defend this", "tribe"),
    ("How to build muscle for $8/day", "constraint"),
    ("Stop flaring your elbows on bench", "mistake"),
    ("POV: someone takes your bench mid-set", "pov"),
])
def test_classify_hook_finds_the_type(line, kind):
    assert kind in story.classify_hook(line)


def test_a_greeting_fits_no_type():
    assert story.classify_hook("So welcome back guys, today I want to talk") == []
    assert "stop" not in story.classify_hook("How many pans does it take to stop a bullet")


def test_every_mark_has_a_type_and_every_type_a_mark():
    assert set(story.HOOK_MARKS) == set(story.HOOK_TYPES)


def _lib(tmp_path):
    d = tmp_path / "library" / "hooks"
    d.mkdir(parents=True)
    (d / "patterns.json").write_text(json.dumps({"patterns": {
        "challenge": {"why": "a bar to clear", "for_michael": ["Can I run a sub [time] mile at [bodyweight]?"],
                      "examples": [{"title": "Can I run a sub 5 minute mile?!", "views": 21000000, "niche": "running",
                                    "creator": "A", "opening": "I'm going to attempt"},
                                   {"title": "Can a noob fly FPV in 4 hours?", "views": 675000, "niche": "fpv"}]},
        "versus": {"examples": [{"title": "Powerlifters vs bodybuilders", "views": 21000000, "niche": "powerlifting"}]},
    }}))
    return d


def test_proven_examples_sort_and_filter(tmp_path):
    d = _lib(tmp_path)
    all_ = story.proven_examples(path=d)
    assert [e["views"] for e in all_] == sorted((e["views"] for e in all_), reverse=True)
    assert [e["title"] for e in story.proven_examples("challenge", "fpv", path=d)] == ["Can a noob fly FPV in 4 hours?"]
    with pytest.raises(ValueError):
        story.proven_examples("nope", path=d)
    assert story.hook_library(tmp_path / "missing") == {"patterns": {}}


def test_hooks_command_shows_examples_and_type(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _lib(tmp_path)
    main(["hooks", "--examples", "challenge"])
    out = capsys.readouterr().out
    assert "21,000,000 views" in out and "a bar to clear" in out and "opens:" in out
    main(["hooks", "--niche", "powerlifting"])
    assert "Powerlifters vs bodybuilders" in capsys.readouterr().out
    main(["hooks"])
    assert "[2 proven]" in capsys.readouterr().out
    main(["hooks", "Can I squat 500 for a single?", "--text", "500 lb squat attempt"])
    out = capsys.readouterr().out
    assert "type: challenge" in out and "hook ok" in out


def test_committed_library_is_valid():
    lib = json.loads((REPO / "library/hooks/patterns.json").read_text())
    for key, pat in lib["patterns"].items():
        assert key in story.HOOK_TYPES, key
        for e in pat["examples"]:
            assert e["title"] and e["niche"] and isinstance(e["views"], int)
    ideas = json.loads((REPO / "library/hooks/ideas.json").read_text())
    from stylebrain.content import PILLARS, FORMATS
    for i in ideas:
        assert i["title"] and i["pillar"] in PILLARS and i.get("format", "reel") in FORMATS
        assert i["hook_type"] in story.HOOK_TYPES
        assert "worlds" not in json.dumps(i).lower()


def test_hook_layers_climb_the_ladder():
    ladder = ["How to make a good hook",
              "This is the best way to make a good hook",
              "I tested 30 hooks and these are the 3 things that make a hook impossible to scroll past"]
    counts = [story.hook_layers(x)["layers"] for x in ladder]
    assert counts == sorted(counts) and counts[0] < counts[-1]
    top = story.hook_layers(ladder[-1])
    assert {"claim", "number", "credibility"} <= set(top["have"])
    assert story.hook_layers("So today I want to talk")["layers"] == 0


def test_retention_names_the_part_to_fix():
    assert story.retention_diagnosis([(0, 100), (3, 40), (15, 36), (20, 33)])["worst"] == "hook"
    assert story.retention_diagnosis([(0, 1), (3, .8), (8, .4), (20, .35)])["worst"] == "buildup"
    assert story.retention_diagnosis([(0, 1), (3, .95), (15, .9), (17, .4), (20, .38)])["worst"] == "payoff"
    assert story.retention_diagnosis([(0, 100), (3, 75), (15, 70), (20, 69)])["worst"] is None
    with pytest.raises(ValueError):
        story.retention_diagnosis([(0, 1)])


def test_retention_and_layers_commands(capsys):
    main(["retention", "[[0,100],[3,40],[15,36],[20,33]]"])
    out = capsys.readouterr().out
    assert "fix the hook" in out and "kept to the end: 33%" in out
    main(["hooks", "How to make a good hook", "--text", "how to make a hook"])
    out = capsys.readouterr().out
    assert "layers: 1 of 5" in out and "could add credibility" in out


def test_playbook_is_valid():
    pb = json.loads((REPO / "library/hooks/playbooks/mckeaveney.json").read_text())
    assert pb["rules"] and all(r["rule"] and r["part"] for r in pb["rules"])
    assert "worlds" not in json.dumps(pb["fits_michael"]).lower().replace("never framed around worlds", "")
