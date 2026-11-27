import json

from stylebrain import creators, style
from stylebrain.cli import main


def rec(i, views, cuts, text=0.0, fmt="short"):
    return {"creator": "demo", "format": fmt, "subscribers": 1000,
            "meta": {"id": f"c{i}", "title": f"clip {i}", "views": views, "w": 360, "h": 640},
            "attributes": {"seconds": 20, "scanned_seconds": 20, "vertical": 1, "cuts_in_first_3s": 1,
                           "brightness": 0.4, "contrast": 0.7, "saturation": 0.2, "warmth": 0.05, "green_magenta": 0,
                           "black_point": 0.02, "white_point": 0.95, "shadow_r": 20, "shadow_g": 20, "shadow_b": 25,
                           "highlight_r": 230, "highlight_g": 225, "highlight_b": 220, "text_share": text,
                           "text_changes_per_10s": 10 if text else 0, "text_on_frame_1": 1 if text else 0,
                           "hook_question": i % 2, "has_transcript": 1, "speech_share": 1, "words_per_minute": 180,
                           "first_word_at": 0.2},
            "cuts": cuts, "hook": f"hook {i}"}


def test_profile_takes_medians_and_counts_clips():
    recs = [rec(i, 1000 * (i + 1), [2.0 * k for k in range(1, 10)], text=0.8 if i < 6 else 0) for i in range(10)]
    p = creators.profile(recs, "demo")
    assert p["frame"]["shape"] == "vertical"
    assert p["pacing"]["cuts_per_minute"] == 27.0
    assert p["study"]["clips"] == 10 and not p["study"]["thin"]
    assert p["study"]["captions_share"] == 0.6
    assert p["study"]["top"][0]["views"] == 10000
    assert p["speech"]["words_per_minute"] == 180
    text = style.summary({"name": "demo", **p})
    assert "Measured from 10 short clips." in text
    assert "captions in 60% of clips" in text


def test_style_from_study_writes_styles(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "data" / "creator-study" / "records"
    folder.mkdir(parents=True)
    for i in range(4):
        (folder / f"demo__c{i}.json").write_text(json.dumps(rec(i, 100 + i, [5.0, 10.0])))
    main(["style-from-study"])
    assert "saved style 'demo' from 4 clips (thin)" in capsys.readouterr().out
    main(["style-show", "demo"])
    assert "thin" in capsys.readouterr().out
