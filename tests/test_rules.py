import pytest

from stylebrain import autopilot, rules
from stylebrain.cli import main
from stylebrain.edl import EditError
from stylebrain.store import Store
from stylebrain.transcript import Word


def say(text, start, each=0.3, gap=0.05):
    out, t = [], start
    for w in text.split():
        out.append(Word(w, round(t, 3), round(t + each, 3)))
        t += each + gap
    return out


def test_settings_are_checked_and_defaults_hold(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert rules.get("pause_min_gap") == 0.6 and rules.get("captions") is False and rules.changed() == []
    assert rules.set_rule("pause_min_gap", "0.45") == 0.45
    assert rules.set_rule("captions", "on") is True and rules.set_rule("frame", "1080x1920") == "1080x1920"
    assert rules.changed() == ["pause_min_gap 0.45", "captions on", "frame 1080x1920"]
    assert rules.pick(None, "pause_min_gap") == 0.45 and rules.pick(0.9, "pause_min_gap") == 0.9
    for name, value, message in [("pause_min_gap", "9", "runs from"), ("captions", "maybe", "on or off"),
                                 ("frame", "tall", "looks like"), ("volume", "1", "no setting named"),
                                 ("pause_air", "lots", "is a number")]:
        with pytest.raises(EditError, match=message):
            rules.set_rule(name, value)
    rules.clear("captions")
    assert rules.get("captions") is False


def test_notes_are_kept_in_his_words(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert rules.add_note("  never cut the breath   before a heavy pull ") == 1
    rules.add_note("no whooshes on talking-head cuts")
    text = rules.text()
    assert "1. never cut the breath before a heavy pull" in text and "2. no whooshes" in text
    assert rules.remove_note(1).startswith("never cut") and len(rules.load()["notes"]) == 1
    with pytest.raises(EditError):
        rules.remove_note(5)
    with pytest.raises(EditError, match="empty"):
        rules.add_note("   ")


def test_first_cut_follows_the_rules_and_a_flag_still_wins(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import json
    words = say("one two three", 0.0) + say("four five six", 1.55) + say("seven eight nine", 4.0)   # pauses of 0.55s and 1.45s
    (tmp_path / "a.words.json").write_text(json.dumps([{"word": w.text, "start": w.start, "end": w.end} for w in words]))
    monkeypatch.setattr("stylebrain.media.probe", lambda path: (30.0, 180))
    plain = autopilot.run("plain", "a.mov", str(tmp_path / "a.words.json"), build=False)
    assert "tighten 2 pauses of 0.6s" in plain.text(30.0)        # the long pause and the silent tail
    rules.set_rule("pause_min_gap", "0.4")
    rules.set_rule("pause_air", "0.05")
    ruled = autopilot.run("ruled", "a.mov", str(tmp_path / "a.words.json"), build=False)
    text = ruled.text(30.0)
    assert "house rules in force: pause_min_gap 0.4, pause_air 0.05" in text and "tighten 3 pauses of 0.4s" in text
    assert Store("ruled").load().duration < Store("plain").load().duration


def test_rule_commands(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["rule", "sounds_per_minute", "4"])
    main(["rule-note", "keep the chalk clap at the start of every deadlift clip"])
    main(["rules"])
    out = capsys.readouterr().out
    assert "house rule saved: sounds_per_minute 4" in out and "saved as note 1" in out
    assert "sounds_per_minute  4" in out and "his" in out and "1. keep the chalk clap" in out
    main(["rule", "sounds_per_minute", "--clear"])
    main(["rule-note", "--remove", "1"])
    out = capsys.readouterr().out
    assert "back to 8" in out and "note removed" in out
    with pytest.raises(SystemExit):
        main(["rule", "captions", "sometimes"])
