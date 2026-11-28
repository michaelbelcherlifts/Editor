"""House look templates, the two new presets, and the people helpers (no MediaPipe or ffmpeg needed)."""
import pytest

from stylebrain import looks, people, presets
from stylebrain.edl import EditError
from stylebrain.pagekit import font_faces, font_stack, with_font
from stylebrain.templates import build

WORDS = [{"word": w, "start": i * 0.3, "end": i * 0.3 + 0.26} for i, w in
         enumerate("I attempted 315 kilos. And sadly fell just short of 315 one-rep".split())]


def test_fonts_are_embedded_so_pages_never_fall_back_to_arial_black():
    css = font_faces("montserrat", "anton")
    assert css.count("@font-face") == 2 and "base64," in css and "'Montserrat'" in css and "'Anton'" in css
    assert font_stack("montserrat").startswith("'Montserrat'")
    page = with_font("<style></style>", "anton")
    assert "@font-face" in page and "'Anton'" in page and "!important" in page
    assert "'Bebas Neue'" in with_font("<style></style>", "bebas") and "base64," in font_faces("bebas")
    html, _ = build("spaced_title", {"text": "built different", "duration": 2})
    assert "@font-face{font-family:'Bebas Neue'" in html


def test_caption_groups_end_at_a_full_stop_and_stay_short():
    groups = looks.group_words(WORDS)
    texts = [" ".join(w["word"] for w in g) for g in groups]
    assert texts[1].endswith("kilos.")                      # never runs across the end of a sentence
    assert all(len(g) <= 3 and len(t) <= 16 for g, t in zip(groups, texts))


def test_house_captions_use_one_accent_per_group_and_keep_hyphenated_words_together():
    html, seconds = build("house_captions", {"words": WORDS, "accent_words": ["315"], "width": 1080, "height": 1920})
    assert html.count("class='hot'") == 2                   # 315 appears twice, in two groups: once each
    assert "ONE‑REP" in html and "@font-face" in html and seconds >= WORDS[-1]["end"]
    with pytest.raises(EditError):
        looks.house_captions([])


def test_hook_is_on_the_first_frame_and_titles_and_banner_build():
    html, d = build("house_hook", {"lines": ["315 kg beat me", "on stage"], "duration": 3.7, "accent_words": ["315"]})
    assert d == 3.7 and "animation" not in html.split("<body>")[1] and "class='hot'>315<" in html
    html, _ = build("big_title", {"text": "315", "unit": "KG", "duration": 2, "accent": True, "x": 0.3})
    assert looks.ACCENT in html and "'Anton'" in html and "left:30.0%" in html
    html, _ = build("notification", {"app": "Coach", "message": "You sure about 315?", "duration": 4})
    assert "rotateX(16deg)" in html and "You sure about 315?" in html
    with pytest.raises(EditError):
        looks.notification("", "x")


def test_new_presets_exist_and_build():
    assert {"house", "cinematic"} <= set(presets.PRESETS)
    for name in ("house", "cinematic"):
        p = presets.PRESETS[name]
        html, seconds = build(p["template"], {**p["params"], "words": presets.sample_words(), "width": 1080, "height": 1920})
        assert "@font-face" in html and seconds > 2


def test_wide_filter_keeps_the_crop_inside_the_frame():
    f = people.wide_filter(x=0.9, share=0.62, fill="blur", fps=29.97)
    assert r"crop=iw*0.62:ih*1.0000:max(0\,min(iw-iw*0.62\,iw*0.9-iw*0.62/2)):ih*0.0," in f and "boxblur" in f and "fps=29.97" in f
    film = people.wide_filter(fill="film")
    assert "pad=1080:1920" in film and "ih*1.0000" in film and "/2.0" not in film   # never crops the height (plates stay)
    boxed = people.wide_filter(x=0.35, share=0.5, top=0.1, bottom=0.95)
    assert "crop=iw*0.5:ih*0.8500" in boxed and ":ih*0.1," in boxed and "force_original_aspect_ratio=decrease" in boxed
    with pytest.raises(EditError):
        people.wide_filter(top=0.8, bottom=0.7)
    with pytest.raises(EditError):
        people.wide_filter(fill="stretch")
    with pytest.raises(EditError):
        people.wide_filter(share=0.1)


def test_speech_spans_merge_close_words_and_pad_the_edges():
    words = [{"word": "a", "start": 1.0, "end": 1.2}, {"word": "b", "start": 1.4, "end": 1.6},
             {"word": "c", "start": 5.0, "end": 5.3}]
    assert people.speech_spans(words, pad=0.1) == [pytest.approx((0.9, 1.7)), pytest.approx((4.9, 5.4))]


def test_composite_puts_text_behind_the_person():
    np = pytest.importorskip("numpy")
    bg = np.full((2, 2, 3), 100, np.uint8)
    text = np.zeros((2, 2, 4), np.uint8); text[..., :3] = 250; text[..., 3] = 255
    mask = np.array([[1.0, 0.0], [0.0, 0.0]], np.float32)  # person in the top-left pixel only
    out = people.composite(bg, text, mask)
    assert out[0, 0, 0] == 100 and out[0, 1, 0] == 250
    assert (people.composite(bg, None, mask) == bg).all()
