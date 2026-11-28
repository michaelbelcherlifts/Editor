"""The effects arsenal: catalogue integrity, search, and that every graphic builds."""

import json

import pytest

from stylebrain import arsenal, effects
from stylebrain.edl import EditError
from stylebrain.templates import TEMPLATES, build
from stylebrain.textfx import CAPTION_STYLES, ENTRIES, EXITS, LOOKS, WIPES

ALL = arsenal.load()


def test_catalogue_is_well_formed():
    assert len(ALL) >= 90
    for e in ALL:
        assert e["kind"] in arsenal.KINDS, e["id"]
        assert 1 <= e["energy"] <= 5 and e["beats"], e["id"]
        assert ("template" in e) or e.get("how"), e["id"]
        for s in e.get("sfx", []):
            assert s["tag"] and isinstance(s["at"], (int, float)), e["id"]


@pytest.mark.parametrize("entry", [e for e in ALL if "template" in e], ids=lambda e: e["id"])
def test_every_graphic_builds(entry):
    assert entry["template"] in TEMPLATES
    html, seconds = build(entry["template"], {**entry["params"], "width": 540, "height": 960})
    assert seconds > 0 and "<!DOCTYPE html>" in html


def test_search_filters():
    hooks = arsenal.search(beat="hook")
    assert hooks and all("hook" in e["beats"] for e in hooks)
    calm = arsenal.search(energy="1-2")
    assert calm and all(e["energy"] <= 2 for e in calm)
    assert all(e["kind"] == "transition" for e in arsenal.search(kind="transition"))
    assert [e["id"] for e in arsenal.search(creator="togi", kind="text")]
    with pytest.raises(EditError):
        arsenal.search(energy="loud")


def test_entries_place_like_effects_and_list_their_sounds():
    recipe = effects.load("hook-slam")
    assert recipe["template"] == "text_fx"
    steps = arsenal.sound_steps(arsenal.get("hook-zoom-through"), 2.0)
    assert steps[0] == "stylebrain sfx-place whoosh --at 1.85"
    with pytest.raises(EditError):
        arsenal.as_recipe(arsenal.get("cut-j"))
    with pytest.raises(EditError):
        arsenal.get("nope")


def test_duplicate_ids_are_refused(tmp_path):
    e = {"id": "x", "kind": "cut", "name": "x", "beats": ["hook"], "energy": 1, "about": "", "how": ["y"]}
    (tmp_path / "a.json").write_text(json.dumps([e, e]))
    with pytest.raises(EditError):
        arsenal.load(tmp_path)


@pytest.mark.parametrize("entry", sorted(ENTRIES))
def test_every_text_entry_builds(entry):
    html, _ = build("text_fx", {"text": "big lift day", "entry": entry})
    assert "@keyframes in" in html


def test_text_fx_options_and_errors():
    for look in LOOKS:
        build("text_fx", {"text": "x", "look": look})
    for ex in EXITS:
        build("text_fx", {"text": "x", "exit": ex})
    for bad in ({"text": " "}, {"text": "x", "entry": "nope"}, {"text": "x", "look": "nope"},
                {"text": "x", "family": "comic"}):
        with pytest.raises(EditError):
            build("text_fx", bad)
    html, _ = build("text_fx", {"text": "<b>", "entry": "decode"})
    assert "<B>" not in html and "window.seek" in html


def test_caption_styles_and_wipes():
    words = [{"word": w, "start": i * 0.3, "end": i * 0.3 + 0.25} for i, w in enumerate("add sixty pounds now".split())]
    for style in CAPTION_STYLES:
        html, seconds = build("caption_style", {"words": words, "style": style})
        assert seconds >= 1.2
    for kind in WIPES:
        html, seconds = build("wipe", {"kind": kind, "text": "later"})
        assert seconds == 0.5
    with pytest.raises(EditError):
        build("wipe", {"kind": "word"})
    with pytest.raises(EditError):
        build("caption_style", {"words": words, "style": "nope"})


def test_wipe_covers_the_frame_at_the_cut_and_mask_rise_shows(tmp_path):
    pytest.importorskip("playwright")
    np = pytest.importorskip("numpy")
    import shutil
    if not shutil.which("ffmpeg"):
        pytest.skip("needs ffmpeg")
    from stylebrain import media
    from stylebrain.render import render_html

    def alpha(path, t):
        raw = media.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(path), "-frames:v", "1",
                         "-f", "rawvideo", "-pix_fmt", "rgba", "-"]).stdout
        return np.frombuffer(raw, np.uint8).reshape(180, 320, 4)[..., 3]

    for kind in ("swipe", "iris", "shutter", "blinds"):
        html, d = build("wipe", {"kind": kind, "duration": 1.0, "width": 320, "height": 180})
        r = render_html(html, tmp_path / f"{kind}.mov", d, fps=10, width=320, height=180)
        assert alpha(r.path, 0.5).min() > 200, kind      # fully covered on the cut
        assert alpha(r.path, 0.0).mean() < 60, kind       # clear at the start
    html, d = build("text_fx", {"text": "THE PLAN", "entry": "mask_rise", "size": 60, "width": 320, "height": 180})
    r = render_html(html, tmp_path / "m.mov", d, fps=10, width=320, height=180)
    assert alpha(r.path, 1.0).max() > 200
