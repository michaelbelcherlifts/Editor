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
