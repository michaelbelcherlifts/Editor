import json
import shutil

import pytest

pytest.importorskip("playwright")
np = pytest.importorskip("numpy")
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

from stylebrain import bake, effects, media  # noqa: E402
from stylebrain.anatomy import resolve_muscles  # noqa: E402
from stylebrain.cli import main  # noqa: E402
from stylebrain.edl import EditError  # noqa: E402
from stylebrain.render import render_html  # noqa: E402
from stylebrain.store import Store  # noqa: E402
from stylebrain.templates import TEMPLATES, build  # noqa: E402

SMALL = dict(width=320, height=180)


def alpha_at(path, t):
    raw = media.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(path), "-frames:v", "1",
                     "-f", "rawvideo", "-pix_fmt", "rgba", "-"]).stdout
    return np.frombuffer(raw, np.uint8).reshape(180, 320, 4)


def test_render_steps_css_time_and_keeps_transparency(tmp_path):
    html = ("<style>html,body{margin:0;background:transparent}"
            "div{position:absolute;top:40px;width:40px;height:40px;background:#f00;"
            "animation:m 1s linear both}@keyframes m{from{left:0}to{left:280px}}</style><div></div>")
    r = render_html(html, tmp_path / "a.mov", 1.0, fps=10, **SMALL)
    i = media.info(r.path)
    assert (i.frames, i.width, i.height, i.has_alpha) == (10, 320, 180, True)
    first, later = alpha_at(r.path, 0.0), alpha_at(r.path, 0.5)
    assert first[60, 20, 3] > 200 and first[60, 20, 0] > 200      # red square starts at the left
    assert first[60, 160, 3] < 10                                  # the rest is transparent
    assert later[60, 160, 3] > 200 and later[60, 20, 3] < 10       # half a second on, it has moved


def test_window_seek_hook_drives_js_animations(tmp_path):
    html = ("<style>html,body{margin:0;background:transparent}div{position:absolute;top:0;left:0;"
            "width:320px;height:180px;background:#0f0;opacity:0}</style><div id='d'></div>"
            "<script>window.seek=t=>{document.getElementById('d').style.opacity=t>=0.5?1:0}</script>")
    r = render_html(html, tmp_path / "s.mov", 1.0, fps=10, **SMALL)
    assert alpha_at(r.path, 0.1)[90, 160, 3] < 10 and alpha_at(r.path, 0.8)[90, 160, 3] > 200


def test_transparent_render_must_be_mov(tmp_path):
    with pytest.raises(EditError):
        render_html("<p>x</p>", tmp_path / "a.mp4", 0.2)


@pytest.mark.parametrize("name,params", [
    ("caption_pop", {"text": "Hello there", "accent_words": ["there"]}),
    ("lower_third", {"name": "Michael", "title": "Coach"}),
    ("callout", {"text": "Here", "box": [0.2, 0.3, 0.3, 0.3]}),
    ("captions", {"words": [{"word": "one", "start": 0.1, "end": 0.4}, {"word": "two", "start": 0.5, "end": 0.9}]}),
    ("muscle_diagram", {"title": "Bench", "highlights": ["chest", {"muscle": "triceps", "role": "secondary"}]}),
])
def test_every_template_renders_something_visible(tmp_path, name, params):
    html, duration = build(name, {**params, **SMALL})
    assert duration > 0
    r = render_html(html, tmp_path / f"{name}.mov", min(duration, 1.2), fps=5, **SMALL)
    assert max(alpha_at(r.path, t)[..., 3].max() for t in (0.4, 0.8, 1.0)) > 200


def test_templates_escape_text_and_reject_bad_input():
    html, _ = build("lower_third", {"name": "<b>Tom & Co</b>"})
    assert "<b>Tom" not in html and "&lt;b&gt;Tom &amp; Co" in html
    for name, params in [("nope", {}), ("caption_pop", {"text": " "}), ("callout", {"text": "x", "box": [2, 0, 1, 1]}),
                         ("muscle_diagram", {"highlights": ["wing"]}), ("lower_third", {"nme": "x"})]:
        with pytest.raises(EditError):
            build(name, params)
    assert set(TEMPLATES) >= {"caption_pop", "lower_third", "callout", "captions", "muscle_diagram", "html"}


def test_muscles_choose_their_views():
    assert resolve_muscles(["pecs", "Front delts", "triceps"])[0] == ["front"]
    assert resolve_muscles(["hamstrings", "glutes", "triceps"])[0] == ["back"]
    assert resolve_muscles(["quads", "glutes"])[0] == ["front", "back"]
    assert resolve_muscles(["lower back"])[1] == [("lower_back", "Lower back")]


def test_muscle_lights_up_at_its_time(tmp_path):
    html, _ = build("muscle_diagram", {"highlights": [{"muscle": "chest", "at": 1.0}], "width": 640, "height": 360})
    r = render_html(html, tmp_path / "m.mov", 2.0, fps=5, width=640, height=360)

    def red_pixels(t):
        f = media.read_frame(r.path, t).astype(int)
        return int(((f[..., 0] > 200) & (f[..., 1] < 120) & (f[..., 2] < 90)).sum())

    assert red_pixels(0.6) == 0 and red_pixels(1.8) > 30


def test_effect_library_round_trip_and_place(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["new", "demo", "--source", "a.mov", "--fps", "10", "--frames", "100"])
    main(["effect-save", "pop", "--template", "caption_pop",
          "--params", json.dumps({"text": "x", "duration": 1.0}), "--about", "house caption"])
    assert [e["name"] for e in effects.list_effects()] == ["pop"]
    main(["effect-place", "pop", "--at", "2", "--set", "text=Bench press", "--width", "320", "--height", "180"])
    o = Store("demo").load().overlays[0]
    assert (o.at, o.duration, o.track) == (20, 10, 2)
    assert media.info(o.source).has_alpha
    with pytest.raises(EditError):
        effects.load("missing")
    with pytest.raises(EditError):
        effects.save("bad name!", "caption_pop", {})


def test_html_file_template_fills_placeholders(tmp_path):
    f = tmp_path / "fx.html"
    f.write_text("<p>{{label}}</p>")
    html, duration = build("html", {"path": str(f), "duration": 2, "label": "A & B"})
    assert html == "<p>A &amp; B</p>" and duration == 2.0


@pytest.fixture
def clip(tmp_path):
    out = tmp_path / "src.mp4"
    media.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=duration=2:size=320x180:rate=10",
               "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-pix_fmt", "yuv420p", "-shortest", str(out)])
    return str(out)


def diff(a, b):
    return float(np.abs(a.astype(int) - b.astype(int)).mean())


def test_punch_in_zooms_only_inside_its_window(clip, tmp_path):
    out = bake.punch_in(clip, str(tmp_path / "z.mp4"), 1.0, 1.6, zoom=1.5, ease=0.1)
    a, b = media.info(clip), media.info(out)
    assert (b.frames, b.width, b.height) == (a.frames, a.width, a.height)
    assert media.has_audio(out)
    assert diff(media.read_frame(clip, 0.3), media.read_frame(out, 0.3)) < 6
    assert diff(media.read_frame(clip, 1.3), media.read_frame(out, 1.3)) > 15
    with pytest.raises(EditError):
        bake.punch_in(clip, "x.mp4", 1.0, 0.5)


def test_change_speed(clip, tmp_path):
    fast = bake.change_speed(clip, str(tmp_path / "f.mp4"), 2.0)
    assert abs(media.info(fast).duration - 1.0) < 0.21 and media.has_audio(fast)
    with pytest.raises(EditError):
        bake.change_speed(clip, "x.mp4", 20)
