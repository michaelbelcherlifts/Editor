import pytest

from stylebrain.edl import EditError, EditList, Overlay, Segment, format_time, parse_time


def clip(frames=1000, fps=24.0):
    return EditList.from_clip("a.mov", frames, fps)


def spans(edit):
    return [(s.source, s.src_in, s.src_out) for s in edit.segments]


def test_remove_range_closes_the_gap():
    e = clip().remove_range(100, 300)
    assert spans(e) == [("a.mov", 0, 100), ("a.mov", 300, 1000)]
    assert e.duration == 800


def test_remove_at_start_and_end():
    assert spans(clip().remove_range(0, 50)) == [("a.mov", 50, 1000)]
    assert spans(clip().remove_range(900, 5000)) == [("a.mov", 0, 900)]


def test_remove_everything_is_refused():
    with pytest.raises(EditError):
        clip().remove_range(0, 1000)


def test_empty_range_is_refused():
    with pytest.raises(EditError):
        clip().remove_range(300, 300)


def test_remove_ranges_uses_original_positions():
    e = clip().remove_ranges([(100, 200), (500, 600), (150, 250)])
    assert spans(e) == [("a.mov", 0, 100), ("a.mov", 250, 500), ("a.mov", 600, 1000)]


def test_split_is_invisible_and_rejoins():
    e = clip().split_at(400)
    assert e.duration == 1000 and len(e.segments) == 2
    assert spans(e.move_range(0, 400, 0)) == [("a.mov", 0, 1000)]


def test_move_later_and_earlier():
    later = clip().move_range(0, 100, 500)
    assert spans(later) == [("a.mov", 100, 500), ("a.mov", 0, 100), ("a.mov", 500, 1000)]
    earlier = clip().move_range(800, 1000, 0)
    assert spans(earlier) == [("a.mov", 800, 1000), ("a.mov", 0, 800)]
    assert later.duration == earlier.duration == 1000


def test_move_into_itself_is_refused():
    with pytest.raises(EditError):
        clip().move_range(100, 300, 200)


def test_swap_in_either_order():
    want = [("a.mov", 0, 100), ("a.mov", 600, 700), ("a.mov", 200, 600), ("a.mov", 100, 200), ("a.mov", 700, 1000)]
    assert spans(clip().swap_ranges(100, 200, 600, 700)) == want
    assert spans(clip().swap_ranges(600, 700, 100, 200)) == want


def test_swap_overlapping_is_refused():
    with pytest.raises(EditError):
        clip().swap_ranges(100, 300, 200, 400)


def test_overlay_follows_its_footage_and_dies_with_it():
    e = clip().add_overlay(Overlay("title", "t.mov", at=500, duration=48))
    assert e.remove_range(100, 300).overlays[0].at == 300
    assert e.remove_range(450, 550).overlays == ()
    assert e.move_range(400, 600, 0).overlays[0].at == 100
    assert e.swap_ranges(0, 100, 450, 550).overlays[0].at == 50


def test_overlay_rules():
    e = clip().add_overlay(Overlay("t", "t.mov", 10, 10))
    with pytest.raises(EditError):
        e.add_overlay(Overlay("t", "t.mov", 20, 10))
    with pytest.raises(EditError):
        e.add_overlay(Overlay("late", "t.mov", 1000, 10))
    with pytest.raises(EditError):
        e.remove_overlay("nope")
    assert e.remove_overlay("t").overlays == ()


def test_where_source_sits_after_edits():
    e = clip().remove_range(100, 300).move_range(0, 100, 800)
    # source 0-100 moved to the end, source 300-1000 now first
    assert e.timeline_ranges_for_source("a.mov", 350, 400) == [(50, 100)]
    assert e.timeline_ranges_for_source("a.mov", 150, 250) == []
    assert e.timeline_ranges_for_source("a.mov", 50, 320) == [(0, 20), (750, 800)]


def test_round_trip_through_json():
    e = clip().remove_range(1, 5).add_overlay(Overlay("t", "t.mov", 10, 10, track=3))
    assert EditList.from_dict(e.to_dict()) == e


def test_bad_segment():
    with pytest.raises(EditError):
        Segment("a.mov", 10, 10)


@pytest.mark.parametrize("text,frames", [
    ("83.5", 2004), ("1:23.5", 2004), ("1:00:00", 86400), ("00:01:23:12", 2004), ("120f", 120), (2, 48),
])
def test_parse_time(text, frames):
    assert parse_time(text, 24.0) == frames


def test_parse_time_rejects_nonsense():
    for bad in ("soon", "1:2:3:4:5", ""):
        with pytest.raises(EditError):
            parse_time(bad, 24.0)


def test_format_time():
    assert format_time(2004, 24.0) == "1:23.50"
    assert format_time(86400 + 24, 24.0) == "1:00:01.00"
