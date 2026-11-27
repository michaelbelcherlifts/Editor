"""The W8 additions: type templates, lift explainers, the caption safe zone, looks from styles."""

import json
import shutil

import pytest

from stylebrain.edl import EditError
from stylebrain.explainers import LIFTS, joint_angle, lift_key
from stylebrain.pagekit import CAPTION_BAND, keep_clear_box
from stylebrain.templates import TEMPLATES, build

WORDS = [{"word": w, "start": 0.2 + i * 0.3, "end": 0.45 + i * 0.3} for i, w in enumerate("do steroids work".split())]

NEW = {
    "kinetic_type": {"words": WORDS, "accent_words": ["work"]},
    "mid_captions": {"text": "three words here and two more", "duration": 2},
    "title_bar": {"text": "Day 37", "duration": 2},
    "end_card": {"items": [{"label": "Protein", "value": 210, "unit": "g"}, {"label": "Mood", "value": "great"}]},
    "counter": {"ticks": [0.3, 0.8], "total": 5},
    "clipper": {"headline": "He benched 405", "duration": 2, "width": 1080, "height": 1920},
    "lift_diagram": {"lift": "bench"},
    "form_cue": {"arrows": [{"from": [0.6, 0.2], "to": [0.5, 0.4], "label": "Drive"}],
                 "angles": [{"vertex": [0.5, 0.5], "a": [0.7, 0.5], "b": [0.5, 0.3]}]},
    "tempo_counter": {"tempo": "3-1-X-0", "reps": 2},
    "compare_chart": {"bars": [{"label": "Me", "value": 516}, {"label": "Avg", "value": 300}], "highlight": 0},
    "hud_card": {"text": "Squat 500", "kind": "mission"},
}


@pytest.mark.parametrize("name", sorted(NEW))
def test_new_templates_build(name):
    html, duration = build(name, NEW[name])
    assert name in TEMPLATES and duration > 0 and "<!DOCTYPE html>" in html


@pytest.mark.parametrize("name,params", [
    ("kinetic_type", {}), ("title_bar", {"text": " ", "duration": 1}), ("end_card", {"items": []}),
    ("counter", {}), ("clipper", {"headline": "x", "duration": 1, "width": 1920, "height": 1080}),  # no bands
    ("lift_diagram", {"lift": "curl"}), ("form_cue", {}), ("form_cue", {"arrows": [{"from": [2, 0], "to": [0, 0]}]}),
    ("hud_card", {"text": "x", "kind": "boss"}), ("hud_card", {"text": " "}),
    ("tempo_counter", {"tempo": "3-1-1"}), ("compare_chart", {"bars": [{"label": "a", "value": 0}]}),
])
def test_new_templates_reject_bad_input(name, params):
    with pytest.raises(EditError):
        build(name, params)


def test_text_is_escaped():
    html, _ = build("kinetic_type", {"text": "<b>hi</b>"})
    assert "<B>" not in html and "&lt;B&gt;" in html


def test_cards_keep_out_of_the_caption_band():
    for h in (1080, 1920):
        top, height = keep_clear_box(h, 940, CAPTION_BAND)
        assert top + height <= CAPTION_BAND[0] * h
    top, height = keep_clear_box(1080, 940, [0.05, 0.3])        # band high up: card goes below it
    assert top >= 0.3 * 1080 and top + height <= 1080
    assert keep_clear_box(1080, 940, None) == (70, 940)
    with pytest.raises(EditError):
        keep_clear_box(1080, 100, [0.8, 0.2])


def test_muscle_card_no_longer_covers_captions_on_a_landscape_frame():
    html, _ = build("muscle_diagram", {"highlights": ["chest"]})
    top = float(html.split(".card{position:absolute;right:4%;top:")[1].split("px")[0])
    height = float(html.split(f"top:{top:.0f}px;width:560px;height:")[1].split("px")[0])
    assert top + height <= CAPTION_BAND[0] * 1080


def test_lift_presets():
    assert lift_key("Bench Press") == "bench" and lift_key("OHP") == "overhead_press"
    for lift in ("bench", "squat", "deadlift"):
        html, _ = build("lift_diagram", {"lift": lift})
        assert LIFTS[lift][0] in html
    html, _ = build("lift_diagram", {"lift": "deadlift", "only": ["glutes"]})
    assert "Glutes" in html and "Hamstrings" not in html


def test_joint_angle():
    assert joint_angle((0, 0), (1, 0), (0, 1)) == pytest.approx(90)
    assert joint_angle((0, 0), (1, 0), (-1, 0.0001)) == pytest.approx(180, abs=0.01)
    html, _ = build("form_cue", {"angles": [{"vertex": [0.5, 0.5], "a": [0.6, 0.5], "b": [0.5, 0.4]}]})
    assert "90°" in html


def test_look_from_a_creator_profile(tmp_path):
    np = pytest.importorskip("numpy")
    from stylebrain import look
    bright = {"colour": {"brightness": 0.73, "black_point": 0.28, "white_point": 0.95, "saturation": 0.1,
                         "warmth": 0.0, "green_magenta": 0.0, "shadow_rgb": [39, 27, 44],
                         "highlight_rgb": [230, 226, 229]}}
    table = look.lut_from_profile(bright, strength=1.0, size=5)
    assert table.shape == (125, 3) and table.min() >= 0 and table.max() <= 1
    black, mid = table[0], table[62]                 # (0,0,0) and (.5,.5,.5)
    assert black.mean() > 0.2                        # blacks lifted like the reference
    assert mid.mean() > 0.5                          # brighter overall
    none = look.lut_from_profile(bright, strength=0.0, size=5)
    grid = np.linspace(0, 1, 5)
    assert np.allclose(none[1], [grid[1], 0, 0])     # strength 0: no change, red fastest
    path = look.from_profile("togi", bright, base=tmp_path, size=5)
    assert path.read_text().startswith('TITLE "togi"\nLUT_3D_SIZE 5')
    with pytest.raises(EditError):
        look.lut_from_profile({"colour": {"brightness": 0.5}})


def test_look_from_style_command(tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    from stylebrain.cli import main
    monkeypatch.chdir(tmp_path)
    prof = tmp_path / "creator-sam.json"
    prof.write_text(json.dumps({"colour": {"brightness": 0.32, "black_point": 0.03, "white_point": 0.85,
                                           "saturation": 0.4, "warmth": -0.1}}))
    main(["look-from-style", "sam", "--style", str(prof)])
    assert (tmp_path / "library/looks/sam.cube").exists()


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_counter_shows_the_rep_number_on_each_tick(tmp_path):
    pytest.importorskip("playwright")
    np = pytest.importorskip("numpy")
    from stylebrain import media
    from stylebrain.render import render_html
    html, _ = build("counter", {"ticks": [0.5], "x": 0.9, "y": 0.1, "width": 320, "height": 180})
    r = render_html(html, tmp_path / "c.mov", 1.0, fps=10, width=320, height=180)

    def alpha(t):
        raw = media.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", r.path, "-frames:v", "1",
                         "-f", "rawvideo", "-pix_fmt", "rgba", "-"]).stdout
        return np.frombuffer(raw, np.uint8).reshape(180, 320, 4)[..., 3]

    assert alpha(0.2).max() < 10 and alpha(0.8).max() > 200


def test_kinetic_scatter_splits_layers_and_snaps():
    words = [{"word": w, "start": i * 0.2, "end": i * 0.2 + 0.15} for i, w in enumerate("one of my big things".split())]
    p = {"words": words, "accent_words": ["big"], "tilt_words": ["things"]}
    back, _ = build("kinetic_scatter", {**p, "layer": "back"})
    front, _ = build("kinetic_scatter", {**p, "layer": "front"})
    assert "THINGS" in back and "BIG" not in back and "--r:-35.0deg" in back
    assert "BIG" in front and "ONE" not in front
    assert "@keyframes sp" in back and "class='p'" not in back      # no pop by default: words snap on
    html, _ = build("kinetic_scatter", {**p, "breaks": [0, 3], "positions": [[0.5, 0.5, 2]]})
    assert html.count("animation:vis") == 5
    with pytest.raises(EditError):
        build("kinetic_scatter", {**p, "layer": "middle"})


@pytest.mark.parametrize("kind", ["mission", "passed", "failed", "warning"])
def test_hud_card_kinds(kind):
    html, d = build("hud_card", {"text": "Don't let a <runner> see this", "kind": kind, "sub": "+RESPECT", "duration": 2})
    assert d == 2 and "&lt;runner&gt;" in html and "+RESPECT" in html
    assert ("class='dim'" in html) == (kind == "failed")
