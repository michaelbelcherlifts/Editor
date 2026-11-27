import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("playwright")
np = pytest.importorskip("numpy")
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

from stylebrain import media, social  # noqa: E402
from stylebrain.cli import main  # noqa: E402
from stylebrain.edl import EditError  # noqa: E402
from stylebrain.transcript import Word  # noqa: E402

TALK = ("So the biggest bench mistake is flaring your elbows. Tuck them about forty five degrees. "
        "Keep your shoulder blades pinned the whole set. Drive your feet into the floor. "
        "Touch the same spot on your chest every rep. Try this next session.")


def words_of(text, start=0.3, each=0.32):
    out, t = [], start
    for w in text.split():
        out.append(Word(w, round(t, 2), round(t + each - 0.04, 2)))
        t += each
    return out


@pytest.fixture(scope="module")
def reel(tmp_path_factory):
    d = tmp_path_factory.mktemp("social")
    path = d / "reel.mp4"
    media.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=360x640:r=10:d=12",
               "-pix_fmt", "yuv420p", str(path)])
    return str(path)


def pixel(path, x, y):
    raw = media.run(["ffmpeg", "-v", "error", "-i", str(path), "-frames:v", "1", "-vf", f"crop=1:1:{x}:{y}",
                     "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]).stdout
    return tuple(raw)


def test_sizes_have_safe_zones_inside_the_frame():
    for sz in social.SIZES.values():
        x, y, w, h = sz.safe
        assert x >= 0 and y >= 0 and x + w <= sz.width and y + h <= sz.height
    story = social.SIZES["story"]
    assert story.safe[1] >= 250 and story.height - (story.safe[1] + story.safe[3]) >= 300
    cover = social.SIZES["cover"]   # the title must survive the 3:4 grid crop (y 240 to 1680)
    assert cover.safe[1] >= 240 and cover.safe[1] + cover.safe[3] <= 1680


def test_prepare_crops_a_video_frame_to_size(reel, tmp_path):
    out = social.prepare(f"{reel}@2.0", tmp_path / "f.jpg", 1080, 1350, focus=(0.5, 0.3))
    i = media.info(str(out))
    assert (i.width, i.height) == (1080, 1350)


def test_prepare_applies_a_look(reel, tmp_path):
    lut = tmp_path / "red.cube"
    rows = [f"{1.0:.6f} 0.000000 0.000000" for _ in range(8)]   # everything becomes pure red
    lut.write_text("LUT_3D_SIZE 2\n" + "\n".join(rows) + "\n")
    out = social.prepare(f"{reel}@1.0", tmp_path / "r.jpg", 200, 200, look=str(lut))
    r, g, b = pixel(out, 100, 100)
    assert r > 200 and g < 40 and b < 40


def test_sharpest_time_avoids_a_blurred_moment(tmp_path):
    path = tmp_path / "blur.mp4"
    # Sharp picture, except a heavily blurred stretch in the middle.
    media.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=10:d=3",
               "-vf", "boxblur=enable='between(t,0.5,2.4)':luma_radius=12", "-pix_fmt", "yuv420p", str(path)])
    t = social.sharpest_time(str(path), 1.5, spread=1.4)
    assert t < 0.6 or t > 2.35


def test_rich_text_marks_accent_words_and_escapes():
    html = social.rich("Stop <flaring> *elbows*", "#ff0")
    assert "&lt;flaring&gt;" in html and "<span style='color:#ff0'>elbows</span>" in html
    assert social.plain("Stop *elbows*") == "Stop elbows"


def test_sentences_and_tidy():
    s = social.sentences(words_of(TALK))
    assert len(s) == 6 and s[0][0].startswith("So the biggest")
    assert social.tidy("so, um okay tuck them") == "Tuck them"


def test_carousel_draft_is_hook_ideas_cta(reel):
    slides = social.carousel_draft(words_of(TALK), reel, cta="save", max_words=12)
    assert slides[0].kind == "hook" and slides[0].text.startswith("The biggest bench mistake")
    assert slides[-1].kind == "cta" and "Save" in slides[-1].text
    ideas = slides[1:-1]
    assert ideas and all(len(s.text.split()) <= 12 for s in ideas)
    assert all(s.image.startswith(reel + "@") for s in slides[:-1])
    # each idea's frame comes from when it was said
    t = float(ideas[0].image.rsplit("@", 1)[1])
    assert ideas[0].said_at <= t
    assert social.check_carousel(slides) == []


def test_carousel_rules():
    long_hook = social.Slide(" ".join(["word"] * 20), kind="hook")
    problems = social.check_carousel([long_hook, social.Slide("x"), social.Slide("y", kind="cta")])
    assert any("hook is 20 words" in p for p in problems)
    assert any("slide 1 must be the hook" in p for p in social.check_carousel([social.Slide("x")] * 3))
    many = [social.Slide("h", kind="hook")] + [social.Slide("x")] * 20
    assert any("Instagram allows 20" in p for p in social.check_carousel(many))


def test_unknown_cta_and_size():
    with pytest.raises(EditError):
        social.cta_text("buy now", social.BRAND_DEFAULTS)
    with pytest.raises(EditError):
        social.size("banner")


def test_render_carousel_sizes_and_safe_zones(reel, tmp_path):
    slides = social.carousel_draft(words_of(TALK), reel, max_words=14)
    slides.insert(2, social.Slide("A slide *without* a picture", "", "idea"))
    stills = social.render_carousel(slides, tmp_path / "c")
    assert len(stills) == len(slides)
    for s in stills:
        i = media.info(s.path)
        assert (i.width, i.height) == (1080, 1350)
        assert s.problems == []
    assert all(v >= social.MIN_FONT for s in stills for v in s.font_sizes.values())


def test_too_many_words_are_reported(tmp_path):
    slides = [social.Slide("hook", kind="hook"), social.Slide(" ".join(["overflowing"] * 200)),
              social.Slide("end", kind="cta")]
    stills = social.render_carousel(slides, tmp_path / "c")
    assert any("too many words" in p for p in stills[1].problems)


def test_text_outside_safe_zone_is_caught():
    sz = social.SIZES["story"]
    assert social.check_boxes([{"role": "t", "x": 100, "y": 100, "w": 50, "h": 50}], sz)
    assert not social.check_boxes([{"role": "t", "x": 100, "y": 300, "w": 50, "h": 50}], sz)


def test_photo_with_text_and_without(reel, tmp_path):
    plain = social.photo(f"{reel}@3", tmp_path / "p.jpg", "square")
    assert (media.info(plain.path).width, media.info(plain.path).height) == (1080, 1080)
    s = social.photo(f"{reel}@3", tmp_path / "t.jpg", "story", text="Leg day *done*", place="top")
    assert (s.width, s.height) == (1080, 1920) and s.problems == []


def test_covers_with_grid_preview_and_thumbnail(reel, tmp_path):
    stills = social.covers(reel, "Stop *flaring* your elbows", tmp_path / "cv", count=2, thumbnail=True)
    names = sorted(p.name for p in (tmp_path / "cv").iterdir())
    assert names == ["cover_1.jpg", "cover_1_grid.jpg", "cover_2.jpg", "cover_2_grid.jpg",
                     "thumbnail_1.jpg", "thumbnail_2.jpg"]
    g = media.info(str(tmp_path / "cv" / "cover_1_grid.jpg"))
    assert (g.width, g.height) == (1080, 1440)
    assert all(s.problems == [] for s in stills)
    with pytest.raises(EditError):
        social.covers(reel, "one two three four five six seven eight", tmp_path / "x")


def test_story_suggestions_are_three_with_coaching_only_when_asked(reel):
    b = {**social.BRAND_DEFAULTS, "site": "example.com"}
    plain = social.story_suggestions("Stop flaring your elbows", reel, "bench", "follow", b)
    assert [s.kind for s in plain] == ["teaser", "poll", "question"]
    assert "bench" in plain[2].sticker
    coach = social.story_suggestions("Stop flaring your elbows", reel, "bench", "coaching", b)
    assert coach[2].kind == "coaching" and "example.com" in coach[2].sticker
    assert [s.day for s in coach] == sorted(s.day for s in coach)


def test_package_makes_everything_in_one_go(reel, tmp_path):
    out = tmp_path / "pkg"
    result = social.package(reel, words_of(TALK), "Stop *flaring* your elbows", out, topic="bench")
    assert result["name"] == "pkg" and result["problems"] == []
    formats = [p["format"] for p in result["posts"]]
    assert formats.count("story") == 3 and "carousel" in formats and "cover" in formats
    for p in result["posts"]:
        assert p["cta"] in {"none", "follow", "comment", "send", "save", "coaching"}
        assert all(Path(f).exists() for f in p["files"])
    for name in ["package.json", "carousel.json", "stories.json", "carousel_overview.jpg",
                 "covers_overview.jpg", "stories_overview.jpg"]:
        assert (out / name).exists()
    plan = json.loads((out / "carousel.json").read_text())
    assert plan["slides"][0]["kind"] == "hook"


def test_cli_carousel_draft_then_render(reel, tmp_path, capsys):
    t = tmp_path / "t.json"
    t.write_text(json.dumps([{"word": w.text, "start": w.start, "end": w.end} for w in words_of(TALK)]))
    plan = tmp_path / "plan.json"
    main(["social", "carousel-draft", "--transcript", str(t), "--video", reel, "--out", str(plan),
          "--hook", "3 bench fixes that add *20 lb*"])
    data = json.loads(plan.read_text())
    assert data["slides"][0]["text"] == "3 bench fixes that add *20 lb*"
    main(["social", "carousel", str(plan), "--out", str(tmp_path / "slides")])
    out = capsys.readouterr().out
    assert "slides" in out and (tmp_path / "slides" / "slide_01.jpg").exists()
    main(["social", "stories", "--hook", "Stop flaring", "--video", reel, "--out", str(tmp_path / "st")])
    assert len(list((tmp_path / "st").glob("story_*.jpg"))) == 3
