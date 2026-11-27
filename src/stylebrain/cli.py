"""Command line for Style Brain. Claude Code runs these while you talk through an edit.

Every command that changes the edit saves a new version, so `undo` always works.
Times are timeline times: seconds ("83.5"), "1:23.5", timecode "00:01:23:12", or frames "120f".
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import transcript as tr
from .edl import EditError, EditList, Overlay, format_time, parse_time
from .store import Store, current_project, set_current_project


def _store(args) -> Store:
    name = args.project or current_project()
    if not name:
        raise EditError("no project selected; run `stylebrain new NAME --source FILE` first")
    return Store(name)


def _summary(edit: EditList) -> str:
    lines = [f"{len(edit.segments)} clips, {format_time(edit.duration, edit.fps)} long, "
             f"{len(edit.overlays)} overlays, {edit.fps:g} fps" + (f", look {Path(edit.look).stem}" if edit.look else "")
             + (f", {len(edit.sounds)} sounds" if edit.sounds else "")]
    for start, seg in edit.pieces():
        lines.append(f"  {format_time(start, edit.fps):>10}  {Path(seg.source).name}  "
                     f"[{seg.src_in}-{seg.src_out})" + (f"  {seg.note}" if seg.note else ""))
    for o in sorted(edit.overlays, key=lambda o: o.at):
        lines.append(f"  {format_time(o.at, edit.fps):>10}  overlay {o.name!r} on V{o.track}, "
                     f"{format_time(o.duration, edit.fps)}  {Path(o.source).name}")
    for x in sorted(edit.sounds, key=lambda x: x.at):
        lines.append(f"  {format_time(x.at, edit.fps):>10}  sound {x.name!r}  {Path(x.source).name}  {x.gain_db:+g} dB")
    return "\n".join(lines)


def _save(store: Store, before: EditList, after: EditList, message: str) -> None:
    version = store.commit(after, message)
    saved = before.duration - after.duration
    print(f"v{version}: {message}")
    if saved:
        print(f"  length {format_time(before.duration, before.fps)} -> {format_time(after.duration, after.fps)}")
    lost = len(before.overlays) - len(after.overlays)
    if lost > 0:
        print(f"  note: {lost} overlay(s) sat on the removed part and were removed with it")


def cmd_new(args) -> None:
    store = Store(args.name)
    if store.exists():
        raise EditError(f"a project named {args.name!r} already exists")
    fps, frames = args.fps, args.frames
    if fps is None or frames is None:
        from .media import probe
        pfps, pframes = probe(args.source)
        fps, frames = fps or pfps, frames or pframes
    edit = EditList.from_clip(str(Path(args.source).resolve()), frames, fps)
    store.commit(edit, f"start from {Path(args.source).name}")
    set_current_project(args.name)
    print(f"project {args.name!r} started\n" + _summary(edit))


def cmd_use(args) -> None:
    if not Store(args.name).exists():
        raise EditError(f"no project named {args.name!r}")
    set_current_project(args.name)
    print(f"now working on {args.name!r}")


def cmd_show(args) -> None:
    store = _store(args)
    print(f"{store.project} v{store.head()}\n" + _summary(store.load()))


def cmd_cut(args) -> None:
    store = _store(args); edit = store.load()
    t0, t1 = parse_time(args.start, edit.fps), parse_time(args.end, edit.fps)
    _save(store, edit, edit.remove_range(t0, t1), f"cut {args.start} to {args.end}")


def cmd_move(args) -> None:
    store = _store(args); edit = store.load()
    t = [parse_time(x, edit.fps) for x in (args.start, args.end, args.to)]
    _save(store, edit, edit.move_range(*t), f"move {args.start}-{args.end} to {args.to}")


def cmd_swap(args) -> None:
    store = _store(args); edit = store.load()
    t = [parse_time(x, edit.fps) for x in (args.a_start, args.a_end, args.b_start, args.b_end)]
    _save(store, edit, edit.swap_ranges(*t), f"swap {args.a_start}-{args.a_end} with {args.b_start}-{args.b_end}")


def _source_for(edit: EditList, source: str | None) -> str:
    sources = sorted({s.source for s in edit.segments})
    if source:
        match = [s for s in sources if s == source or Path(s).name == source]
        if len(match) != 1:
            raise EditError(f"{source!r} does not match exactly one source in this edit")
        return match[0]
    if len(sources) != 1:
        raise EditError("this edit uses several sources; say which with --source")
    return sources[0]


def _to_timeline(edit: EditList, source: str, spans: list[tuple[float, float]]) -> list[tuple[int, int]]:
    out = []
    for lo, hi in spans:
        out += edit.timeline_ranges_for_source(source, round(lo * edit.fps), round(hi * edit.fps))
    return out


def cmd_find(args) -> None:
    store = _store(args); edit = store.load()
    source = _source_for(edit, args.source)
    hits = tr.find_phrase(tr.load_words(args.transcript), args.phrase)
    ranges = _to_timeline(edit, source, hits)
    if not ranges:
        print("not found on the timeline (never said, or already cut)")
    for t0, t1 in ranges:
        print(f"{format_time(t0, edit.fps)} to {format_time(t1, edit.fps)}  ({t0}f-{t1}f)")


def cmd_cut_phrase(args) -> None:
    store = _store(args); edit = store.load()
    source = _source_for(edit, args.source)
    ranges = _to_timeline(edit, source, tr.find_phrase(tr.load_words(args.transcript), args.phrase))
    if not ranges:
        raise EditError("that phrase is not on the timeline (never said, or already cut)")
    if len(ranges) > 1 and not args.all:
        listing = ", ".join(format_time(t0, edit.fps) for t0, _ in ranges)
        raise EditError(f"said {len(ranges)} times (at {listing}); pass --all or cut by time")
    _save(store, edit, edit.remove_ranges(ranges), f"cut the words {args.phrase!r}")


def cmd_tighten(args) -> None:
    store = _store(args); edit = store.load()
    source = _source_for(edit, args.source)
    length = max(s.src_out for s in edit.segments if s.source == source) / edit.fps
    cuts = tr.tighten_ranges(tr.load_words(args.transcript), args.min_gap, args.pad, length)
    ranges = _to_timeline(edit, source, cuts)
    if not ranges:
        print("no pauses that long; nothing changed")
        return
    _save(store, edit, edit.remove_ranges(ranges),
          f"tighten {len(ranges)} pauses of {args.min_gap:g}s or more")


def cmd_overlay_add(args) -> None:
    store = _store(args); edit = store.load()
    o = Overlay(args.name, str(Path(args.source).resolve()), parse_time(args.at, edit.fps),
                parse_time(args.duration, edit.fps), args.track)
    _save(store, edit, edit.add_overlay(o), f"add overlay {args.name!r} at {args.at}")


def cmd_overlay_remove(args) -> None:
    store = _store(args); edit = store.load()
    _save(store, edit, edit.remove_overlay(args.name), f"remove overlay {args.name!r}")


def _values(pairs: list[str] | None) -> dict:
    """Read --set key=value pairs; values are JSON when they parse as JSON, else text."""
    out = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise EditError(f"--set takes key=value, got {pair!r}")
        key, value = pair.split("=", 1)
        try:
            out[key] = json.loads(value)
        except json.JSONDecodeError:
            out[key] = value
    return out


def _params(text: str | None) -> dict:
    if not text:
        return {}
    try:
        data = json.loads(Path(text[1:]).read_text() if text.startswith("@") else text)
    except (json.JSONDecodeError, OSError) as e:
        raise EditError(f"--params must be JSON, or @file.json: {e}") from None
    if not isinstance(data, dict):
        raise EditError("--params must be a JSON object")
    return data


def cmd_templates(args) -> None:
    from .templates import TEMPLATES
    for name, fn in sorted(TEMPLATES.items()):
        print(f"{name}: {(fn.__doc__ or '').strip().splitlines()[0]}")


def cmd_render(args) -> None:
    from .effects import render_template
    r = render_template(args.template, {**_params(args.params), **_values(args.set)}, args.out,
                        args.fps, args.width, args.height)
    print(f"rendered {r.path}: {r.frames} frames at {r.fps:g} fps")


def cmd_effect_save(args) -> None:
    from .effects import save
    path = save(args.name, args.template, _params(args.params), args.about or "", args.reference or "")
    print(f"saved effect {args.name!r} to {path}")


def cmd_effect_list(args) -> None:
    from .effects import list_effects
    effects = list_effects()
    if not effects:
        print("no saved effects yet")
    for e in effects:
        print(f"{e['name']} ({e['template']})" + (f": {e['about']}" if e.get("about") else ""))


def cmd_effect_render(args) -> None:
    from .effects import render_effect
    r = render_effect(args.name, _values(args.set), args.out, args.fps, args.width, args.height)
    print(f"rendered {r.path}: {r.frames} frames at {r.fps:g} fps")


def cmd_effect_place(args) -> None:
    from .effects import render_effect
    store = _store(args); edit = store.load()
    at = parse_time(args.at, edit.fps)
    r = render_effect(args.name, _values(args.set), None, edit.fps, args.width, args.height)
    label = args.label or f"{args.name}@{args.at}"
    o = Overlay(label, str(Path(r.path).resolve()), at, r.frames, args.track)
    _save(store, edit, edit.add_overlay(o), f"place effect {args.name!r} at {args.at}")
    print(f"  rendered {r.path}")


def _secs(text: str) -> float:
    return parse_time(text, 1000.0) / 1000.0


def cmd_ref_fetch(args) -> None:
    from . import reference
    path = reference.fetch(args.url, args.dest)
    print(json.dumps(reference.describe(str(path)), indent=2))


def cmd_ref_sheet(args) -> None:
    from . import reference
    times = reference.contact_sheet(args.video, _secs(args.start), _secs(args.end), args.out, args.count, args.columns)
    print(f"wrote {args.out}; frames in reading order at: " + ", ".join(f"{t:.2f}s" for t in times))


def cmd_ref_frames(args) -> None:
    from . import reference
    for f in reference.frames(args.video, _secs(args.start), _secs(args.end), args.out, args.count):
        print(f"{f['time']:.2f}s  {f['path']}")


def cmd_ref_motion(args) -> None:
    from . import reference
    m = reference.motion(args.video, _secs(args.start), _secs(args.end), args.threshold)
    data = m.to_dict()
    if not args.curve:
        data.pop("curve")
    print(json.dumps(data, indent=2))


def cmd_ref_palette(args) -> None:
    from . import reference
    box = json.loads(args.box) if args.box else None
    for c in reference.palette(args.video, _secs(args.at), args.colours, box):
        print(f"{c['hex']}  {c['share'] * 100:.0f}%")


def cmd_ref_compare(args) -> None:
    from . import reference
    reference.compare_sheet(args.reference, _secs(args.ref_start), args.mine, _secs(args.mine_start),
                            args.seconds, args.out, args.count, background=args.background)
    print(f"wrote {args.out}: reference on top, yours below")


def cmd_undo(args) -> None:
    store = _store(args)
    print(f"back to v{store.undo()}\n" + _summary(store.load()))


def cmd_goto(args) -> None:
    store = _store(args)
    print(f"now at v{store.goto(args.version)}\n" + _summary(store.load()))


def cmd_log(args) -> None:
    for r in _store(args).log():
        print(f"{'*' if r['head'] else ' '} v{r['version']:<4} {r['time']}  {r['message']}")


def cmd_build(args) -> None:
    from .resolve_builder import build_timeline, connect
    store = _store(args); edit = store.load()
    name = args.name or f"{store.project} v{store.head()}"
    mixed = None
    if edit.sounds:
        from . import sfx
        mixed = str(sfx.mix(edit, Path(".stylebrain") / "renders" / f"{store.project}-v{store.head()}-sfx.wav").resolve())
    report = build_timeline(connect(), edit, name, sound_mix=mixed)
    print(report.text())
    if not report.ok:
        sys.exit(1)


def cmd_style_learn(args) -> None:
    from . import style
    words = tr.load_words(args.transcript) if args.transcript else None
    profile = style.measure(args.video, words, args.threshold)
    path = style.save(args.name, profile, args.about or "")
    print(f"saved style {args.name!r} to {path}")
    print(style.summary(profile))


def cmd_style_show(args) -> None:
    from . import style
    p = style.load(args.name)
    print(json.dumps(p, indent=2) if args.json else style.summary(p))


def cmd_style_list(args) -> None:
    from . import style
    for name in style.list_styles():
        p = style.load(name)
        print(f"{name}: {p.get('about') or Path(p['source']).name}")


def cmd_look_make(args) -> None:
    from . import look
    path = look.make(args.name, args.reference, args.footage, args.strength)
    print(f"saved look {args.name!r} to {path}")


def cmd_look_preview(args) -> None:
    from . import look
    out = look.preview(args.video, look.find(args.name), _secs(args.at), args.out, args.reference,
                       _secs(args.ref_at))
    print(f"{out}: before, after" + (", reference" if args.reference else ""))


def cmd_look_list(args) -> None:
    from . import look
    for name in look.list_looks():
        print(name)


def cmd_look_use(args) -> None:
    from . import look
    store = _store(args); edit = store.load()
    if args.name == "none":
        _save(store, edit, edit.set_look(""), "remove the look")
    else:
        path = str(look.find(args.name).resolve())
        _save(store, edit, edit.set_look(path), f"use the look {args.name!r}")


def cmd_transcribe(args) -> None:
    from .transcribe import transcribe
    path, words = transcribe(args.video, args.out, args.engine, args.model)
    print(f"{len(words)} words, saved to {path}")


def cmd_retakes(args) -> None:
    store = _store(args); edit = store.load()
    source = _source_for(edit, args.source)
    words = tr.load_words(args.transcript)
    found = tr.find_retakes(words, args.min_words)
    if not found:
        print("no likely retakes found")
        return
    for a, b in found:
        said = " ".join(w.text for w in words if a <= w.start < b)[:70]
        where = ", ".join(format_time(lo, edit.fps) for lo, _ in _to_timeline(edit, source, [(a, b)])) or "already cut"
        print(f"  {where}: {b - a:.1f}s  \"{said}\"")
    if args.cut:
        ranges = _to_timeline(edit, source, [(a, b - 0.12) for a, b in found if b - a > 0.12])
        if ranges:
            _save(store, edit, edit.remove_ranges(ranges), f"cut {len(found)} likely retakes")


def cmd_srt(args) -> None:
    from .autopilot import timeline_words
    store = _store(args); edit = store.load()
    words = timeline_words(edit, _source_for(edit, args.source), tr.load_words(args.transcript))
    Path(args.out).write_text(tr.to_srt(words))
    print(f"{len(words)} words of the current cut written to {args.out}")


def cmd_review(args) -> None:
    from . import review, style
    target = style.load(args.style)
    fps = 30.0
    if args.video:
        words = tr.load_words(args.transcript) if args.transcript else None
        mine = style.measure(args.video, words)
        if words:
            mine["words"] = [[w.text, w.start, w.end] for w in words]
        fps = mine["frame"]["fps"]
    else:
        from .autopilot import timeline_words
        store = _store(args); edit = store.load()
        fps = edit.fps
        words = None
        if args.transcript:
            words = timeline_words(edit, _source_for(edit, args.source), tr.load_words(args.transcript))
        mine = review.profile_of_edit(edit, words)
    found = review.compare(mine, target, args.limit)
    if args.json:
        print(json.dumps(review.to_json(found), indent=2))
    elif not found:
        print(f"nothing stands out against {args.style!r}")
    else:
        print(f"{len(found)} things to look at, measured against {args.style!r}:")
        for s in found:
            print(s.line(fps))


def cmd_auto(args) -> None:
    from . import autopilot
    result = autopilot.run(args.name, args.source, args.transcript, args.style, args.look, args.captions,
                           not args.keep_retakes, not args.no_build, args.width, args.height)
    print(result.text(Store(args.name).load().fps))


def cmd_score(args) -> None:
    from . import score as sc
    if args.questions:
        for key, text in {**sc.JUDGEMENTS, **sc.FLAGS}.items():
            print(f"  {key}: {text}")
        return
    if not args.transcript:
        raise EditError("score needs --transcript")
    words = tr.load_words(args.transcript)
    judge = json.loads(Path(args.judge[1:]).read_text() if args.judge and args.judge.startswith("@") else args.judge or "{}")
    cuts = frame = audio = None
    duration = args.seconds
    if args.video:
        from . import style
        m = style.measure(args.video, None)
        cuts, frame, audio, duration = m["cuts"], m["frame"], m["audio"], m["frame"]["seconds"]
    if duration is None:
        duration = words[-1].end if words else 0.0
    result = sc.score(words, duration, cuts, frame, audio, judge)
    print(json.dumps(result.to_dict(), indent=2) if args.json else result.text())


def cmd_clip_add(args) -> None:
    from . import learn
    words = tr.load_words(args.transcript) if args.transcript else []
    judge = json.loads(Path(args.judge[1:]).read_text() if args.judge and args.judge.startswith("@") else args.judge or "{}")
    cuts = frame = audio = colour = None
    duration = args.seconds
    if args.video:
        from . import style
        m = style.measure(args.video, None)
        cuts, frame, audio, colour, duration = m["cuts"], m["frame"], m["audio"], m["colour"], m["frame"]["seconds"]
    outcome = {k: v for k, v in (("views", args.views), ("subscribers", args.subscribers),
                                 ("retention", args.retention), ("swiped_away", args.swiped_away)) if v is not None}
    if duration is None and words:
        duration = words[-1].end
    if duration is None:
        if not outcome:
            raise EditError("give --video or --transcript to measure the clip, or results such as --views")
        attrs = {}  # results only: update what happened to a clip already in the set
    else:
        attrs = learn.attributes(words, duration, cuts, frame, audio, colour, judge)
    path = learn.add(args.id, attrs, outcome, args.about or "", args.mine)
    print(f"saved {path}")


def cmd_clip_import(args) -> None:
    from . import learn
    ids = learn.import_analytics(args.csv, args.subscribers, reels_only=not args.all_posts)
    need = [c["id"] for c in learn.load_all() if c["id"] in ids and not c["attributes"]]
    print(f"{len(ids)} clips read from the analytics file; {len(need)} still need attributes (clip-add ID --video ...)")


def cmd_clip_list(args) -> None:
    from . import learn
    clips = learn.load_all()
    for c in clips:
        o = c["outcome"]
        print(f"{c['id']:<16}{'mine ' if c.get('mine') else '     '}{len(c['attributes']):>3} attributes  "
              f"views {o.get('views', '-')}  {c.get('about', '')[:50]}")
    print(f"{len(clips)} clips")


def cmd_learn(args) -> None:
    from . import learn
    result = learn.fit(learn.load_all(), args.target, only_mine=args.mine)
    print(json.dumps(result, indent=2) if args.json else learn.report(result))


def cmd_sfx_basics(args) -> None:
    from . import sfx
    for i in sfx.make_basics():
        print(f"  {i['file']}: {', '.join(i['tags'])}")


def cmd_sfx_add(args) -> None:
    from . import sfx
    i = sfx.add(args.file, args.tags.split(","), args.licence, args.source or "", args.credit or "")
    print(f"added {i['file']} ({i['seconds']:g}s): {', '.join(i['tags'])}")


def cmd_sfx_list(args) -> None:
    from . import sfx
    for i in sfx.load():
        print(f"  {i['file']:<40}{i['seconds']:>6g}s  {i['licence']:<10}{', '.join(i['tags'])}")


def cmd_sfx_fetch(args) -> None:
    from . import sfx
    added, skipped = sfx.fetch(args.query, (args.tags or args.query).split(","), args.count, args.max_seconds,
                                licence=args.licence)
    for i in added:
        print(f"  added {i['file']} ({i['seconds']:g}s, licence {i['licence']}) from {i['source']}")
    for line in skipped:
        print(f"  skipped {line}")
    print(f"{len(added)} added, {len(skipped)} skipped")


def cmd_sfx_place(args) -> None:
    from . import sfx
    store = _store(args); edit = store.load()
    at = parse_time(args.at, edit.fps)
    sound = sfx.sound_for(edit, args.tag, at, args.name or f"{args.tag}@{args.at}", args.gain, safe_only=args.ad)
    _save(store, edit, edit.add_sound(sound), f"place sound {args.tag!r} at {args.at}")


def cmd_sfx_auto(args) -> None:
    from . import sfx
    store = _store(args); edit = store.load()
    words = None
    if args.transcript:
        from .autopilot import timeline_words
        words = timeline_words(edit, _source_for(edit, args.source), tr.load_words(args.transcript))
    new, lines = sfx.auto_place(edit, words, tuple(args.on.split(",")), args.gain, args.duck, args.min_cut_gap,
                                 safe_only=args.ad)
    if not lines:
        print("nothing to place sounds on")
        return
    _save(store, edit, new, f"place {len(lines)} sounds automatically")
    for line in lines:
        print("  " + line)


def cmd_sfx_remove(args) -> None:
    store = _store(args); edit = store.load()
    prefix = "" if args.name == "all" else "auto:" if args.name == "auto" else args.name
    new = edit.remove_sounds(prefix)
    _save(store, edit, new, f"remove {len(edit.sounds) - len(new.sounds)} sounds")


def _focus(text: str | None) -> tuple[float, float]:
    if not text:
        return (0.5, 0.5)
    try:
        x, y = (float(v) for v in text.split(","))
    except ValueError:
        raise EditError("--focus is two fractions, like 0.5,0.3") from None
    return x, y


def _report(stills, what: str) -> None:
    print(f"{len(stills)} {what}:")
    for s in stills:
        print(f"  {s.path}  {s.width}x{s.height}")
        for problem in s.problems:
            print(f"    problem: {problem}")


def cmd_social_sizes(args) -> None:
    from . import social
    for sz in social.SIZES.values():
        x, y, w, h = sz.safe
        print(f"  {sz.name:10} {sz.width}x{sz.height}  text inside x {x}-{x + w}, y {y}-{y + h}  ({sz.about})")


def cmd_social_photo(args) -> None:
    from . import social
    s = social.photo(args.source, args.out, args.size, args.look, args.text or "", args.place, _focus(args.focus))
    _report([s], "image")


def cmd_social_carousel_draft(args) -> None:
    from . import social
    words = tr.load_words(args.transcript)
    slides = social.carousel_draft(words, args.video, args.hook, args.cta, args.max_words, args.max_ideas,
                                   social.brand())
    social.save_plan(args.out, slides, look=args.look or "", size="portrait")
    print(f"{len(slides)} slides drafted from what was said, saved to {args.out}. Rewrite the text, then render:")
    for n, s in enumerate(slides, 1):
        print(f"  {n:2}. [{s.kind}] {s.text}")
    for problem in social.check_carousel(slides):
        print(f"  problem: {problem}")


def cmd_social_carousel(args) -> None:
    from . import social
    slides, data = social.load_plan(args.plan)
    for problem in social.check_carousel(slides):
        print(f"problem: {problem}")
    stills = social.render_carousel(slides, args.out, args.look or data.get("look") or None,
                                    data.get("size", "portrait"))
    social.contact([s.path for s in stills], Path(args.out) / "overview.jpg")
    _report(stills, "slides")


def cmd_social_covers(args) -> None:
    from . import social
    times = [_secs(t) for t in args.at.split(",")] if args.at else None
    stills = social.covers(args.video, args.title, args.out, args.count, args.look, args.thumbnail, times)
    _report(stills, "covers (each cover_N.jpg has a cover_N_grid.jpg showing the profile grid crop)")


def cmd_social_stories(args) -> None:
    from . import social
    stories = social.story_suggestions(args.hook, args.video, args.topic or "", args.cta, social.brand())
    Path(args.out).mkdir(parents=True, exist_ok=True)
    (Path(args.out) / "stories.json").write_text(json.dumps([s.to_dict() for s in stories], indent=2) + "\n")
    stills = social.render_stories(stories, args.out, args.look)
    for s, st in zip(stories, stills):
        print(f"  day +{s.day:g} {s.kind}: \"{social.plain(s.text)}\"  sticker: {s.sticker}")
        print(f"     {st.path}" + "".join(f"\n     problem: {p}" for p in st.problems))


def cmd_social_package(args) -> None:
    from . import social
    words = tr.load_words(args.transcript)
    out = args.out or str(Path("library") / "social" / args.name)
    r = social.package(args.video, words, args.title, out, args.hook, args.look, args.topic or "", args.cta,
                       args.caption or "", args.thumbnail)
    count = lambda f: sum(len(p["files"]) if f == "cover" else 1 for p in r["posts"] if p["format"] == f)  # noqa: E731
    print(f"package {r['name']!r} in {out}: {count('cover')} cover options, a carousel of {count('carousel') and len(next(p for p in r['posts'] if p['format'] == 'carousel')['files'])} slides, {count('story')} stories")
    for problem in r["problems"]:
        print(f"  problem: {problem}")
    print(f"  look at {out}/carousel_overview.jpg, covers_overview.jpg and stories_overview.jpg")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="stylebrain", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-p", "--project", help="project name (default: the current one)")
    sub = p.add_subparsers(dest="command", required=True)

    def add(name, fn, help, *arguments):
        s = sub.add_parser(name, help=help)
        for flags, kw in arguments:
            s.add_argument(*flags, **kw)
        s.set_defaults(fn=fn)

    A = lambda *flags, **kw: (flags, kw)  # noqa: E731
    tx = [A("--transcript", required=True, help="word-timing JSON for the source clip"),
          A("--source", help="which source clip the transcript belongs to")]

    add("new", cmd_new, "start a project from one source clip", A("name"), A("--source", required=True),
        A("--fps", type=float), A("--frames", type=int))
    add("use", cmd_use, "switch to another project", A("name"))
    add("show", cmd_show, "show the current edit")
    add("cut", cmd_cut, "cut a stretch of the timeline and close the gap", A("start"), A("end"))
    add("move", cmd_move, "move a section to another point", A("start"), A("end"), A("to"))
    add("swap", cmd_swap, "swap two sections", A("a_start"), A("a_end"), A("b_start"), A("b_end"))
    add("find", cmd_find, "find where a phrase is on the timeline", A("phrase"), *tx)
    add("cut-phrase", cmd_cut_phrase, "cut the words of a phrase", A("phrase"), *tx,
        A("--all", action="store_true", help="cut every time it is said"))
    add("tighten", cmd_tighten, "shorten long pauses", *tx,
        A("--min-gap", type=float, default=0.6), A("--pad", type=float, default=0.12))
    add("overlay-add", cmd_overlay_add, "place a clip above the main track", A("name"),
        A("--source", required=True), A("--at", required=True), A("--duration", required=True),
        A("--track", type=int, default=2))
    add("overlay-remove", cmd_overlay_remove, "remove an overlay", A("name"))
    size = [A("--width", type=int, default=1920), A("--height", type=int, default=1080)]
    sets = A("--set", action="append", metavar="KEY=VALUE", help="change one setting (repeatable)")
    add("templates", cmd_templates, "list animation templates")
    add("render", cmd_render, "render a template to a transparent .mov", A("template"),
        A("--params", help="JSON object, or @file.json"), sets, A("--out"),
        A("--fps", type=float, default=30.0), *size)
    add("effect-save", cmd_effect_save, "save a named effect recipe", A("name"),
        A("--template", required=True), A("--params", help="JSON object, or @file.json"),
        A("--about"), A("--reference", help="where the effect was copied from"))
    add("effect-list", cmd_effect_list, "list saved effects")
    add("effect-render", cmd_effect_render, "render a saved effect to a file", A("name"), sets, A("--out"),
        A("--fps", type=float, default=30.0), *size)
    add("effect-place", cmd_effect_place, "render a saved effect and place it on the timeline", A("name"),
        A("--at", required=True), sets, A("--track", type=int, default=2), A("--label"), *size)
    span = [A("video"), A("--start", required=True), A("--end", required=True)]
    add("ref-fetch", cmd_ref_fetch, "download a reference video for private study", A("url"),
        A("--dest", default="references"))
    add("ref-sheet", cmd_ref_sheet, "one image of evenly spaced frames from a moment", *span,
        A("--out", required=True), A("--count", type=int, default=24), A("--columns", type=int, default=6))
    add("ref-frames", cmd_ref_frames, "save larger single frames from a moment", *span,
        A("--out", required=True), A("--count", type=int, default=12))
    add("ref-motion", cmd_ref_motion, "when things move in a moment, and for how long", *span,
        A("--threshold", type=float, default=0.6), A("--curve", action="store_true"))
    add("ref-palette", cmd_ref_palette, "main colours of a frame", A("video"), A("--at", required=True),
        A("--colours", type=int, default=5), A("--box", help="[x, y, w, h] as fractions"))
    add("ref-compare", cmd_ref_compare, "reference on top, your render below, at matching moments",
        A("reference"), A("mine"), A("--ref-start", default="0"), A("--mine-start", default="0"),
        A("--seconds", type=float, required=True), A("--out", required=True),
        A("--count", type=int, default=8), A("--background"))
    add("style-learn", cmd_style_learn, "measure a video's editing style and save it", A("video"),
        A("--name", required=True), A("--transcript", help="word-timing JSON, for speech pace"),
        A("--about"), A("--threshold", type=float, default=0.3, help="how big a change counts as a cut"))
    add("style-show", cmd_style_show, "describe a saved style", A("name"), A("--json", action="store_true"))
    add("style-list", cmd_style_list, "list saved styles")
    add("look-make", cmd_look_make, "make a colour look (LUT) that moves your footage toward a reference",
        A("name"), A("--reference", required=True), A("--footage", required=True, help="your own clip"),
        A("--strength", type=float, default=1.0, help="0 to 1"))
    add("look-preview", cmd_look_preview, "before / after / reference image for a look", A("name"),
        A("--video", required=True), A("--at", default="0"), A("--out", required=True),
        A("--reference"), A("--ref-at", default="0"))
    add("look-list", cmd_look_list, "list saved looks")
    add("look-use", cmd_look_use, "put a saved look on the edit ('none' removes it)", A("name"))
    add("transcribe", cmd_transcribe, "make a word-timing transcript with a local speech-to-text tool",
        A("video"), A("--out"), A("--engine"), A("--model"))
    add("retakes", cmd_retakes, "list likely false starts (a phrase said again straight after)", *tx,
        A("--min-words", type=int, default=4), A("--cut", action="store_true", help="cut them"))
    add("srt", cmd_srt, "write subtitles for the current cut", *tx, A("--out", required=True))
    add("review", cmd_review, "compare the current cut (or a video file) with a saved style", A("style"),
        A("--video", help="a finished video file to review, not the current edit"),
        A("--transcript"), A("--source"), A("--limit", type=int, default=8), A("--json", action="store_true"))
    add("auto", cmd_auto, "first cut in one go: retakes, pauses, look, captions, build, review", A("name"),
        A("--source", required=True), A("--transcript"), A("--style"), A("--look"),
        A("--captions", action="store_true"), A("--keep-retakes", action="store_true"),
        A("--no-build", action="store_true"), *size)
    add("score", cmd_score, "score a short clip on the virality rubric, part by part",
        A("--transcript", help="word timings of the clip"), A("--video", help="the clip, to measure cuts, frame and sound"),
        A("--seconds", type=float, help="clip length when no video is given"),
        A("--judge", help="Claude's judgements as JSON or @file (see --questions)"),
        A("--questions", action="store_true", help="list the judgements and flags"), A("--json", action="store_true"))
    add("clip-add", cmd_clip_add, "add a clip's attributes and results to the learning set", A("id"),
        A("--transcript"), A("--video"), A("--seconds", type=float), A("--judge"), A("--about"),
        A("--views", type=float), A("--subscribers", type=float), A("--retention", type=float),
        A("--swiped-away", type=float), A("--mine", action="store_true", help="it is one of your own clips"))
    add("clip-import", cmd_clip_import, "read results from an Instagram (Meta Business Suite) or YouTube Studio export (CSV)", A("csv"),
        A("--subscribers", "--followers", type=int, help="your follower or subscriber count, for the reach target"),
        A("--all-posts", action="store_true", help="include photos and carousels, not only reels"))
    add("clip-list", cmd_clip_list, "list clips in the learning set")
    add("learn", cmd_learn, "learn which attributes go with clips doing well", A("--target", default="reach"),
        A("--mine", action="store_true", help="use only your own clips"), A("--json", action="store_true"))
    add("sfx-basics", cmd_sfx_basics, "make a starter set of sounds (pop, click, whoosh, thud, riser)")
    add("sfx-add", cmd_sfx_add, "add a sound file to the library", A("file"), A("--tags", required=True),
        A("--licence", required=True, help="recorded, not enforced: own, cc0, by, unknown ..."), A("--source"), A("--credit"))
    add("sfx-list", cmd_sfx_list, "list the sound library")
    add("sfx-fetch", cmd_sfx_fetch, "download sounds from Openverse into the library (CC0 unless told otherwise)", A("query"),
        A("--licence", default="cc0", help="cc0 (default), a list such as cc0,by, or any"),
        A("--tags", help="tags to file them under (default: the query)"), A("--count", type=int, default=5),
        A("--max-seconds", type=float, default=4.0))
    add("sfx-place", cmd_sfx_place, "place one sound by tag", A("tag"), A("--at", required=True),
        A("--gain", type=float, default=-12.0), A("--name"), A("--ad", action="store_true", help="paid ad: use only your own, made-here, CC0 or public-domain sounds"))
    add("sfx-auto", cmd_sfx_auto, "place sounds on cuts, graphics and zooms, lowered under speech",
        A("--transcript", help="word timings, to lower sounds under speech"), A("--source"),
        A("--on", default="cuts,overlays,zooms"), A("--gain", type=float, default=-14.0),
        A("--duck", type=float, default=6.0), A("--min-cut-gap", type=float, default=2.5), A("--ad", action="store_true", help="paid ad: use only your own, made-here, CC0 or public-domain sounds"))
    add("sfx-remove", cmd_sfx_remove, "remove a sound by name, or 'auto' or 'all'", A("name"))

    soc = sub.add_parser("social", help="photos, carousels, covers and stories for Instagram and YouTube")
    ssub = soc.add_subparsers(dest="social_command", required=True)

    def sadd(name, fn, help, *arguments):
        s = ssub.add_parser(name, help=help)
        for flags, kw in arguments:
            s.add_argument(*flags, **kw)
        s.set_defaults(fn=fn)

    lk = A("--look", help="a saved colour look, or a .cube file")
    ctas = A("--cta", default="follow", choices=["follow", "save", "send", "comment", "coaching", "none"])
    sadd("sizes", cmd_social_sizes, "list sizes and where text must stay")
    sadd("photo", cmd_social_photo, "crop a photo or video frame (video.mp4@12.5) to a size, with a look and text",
         A("source"), A("--out", required=True), A("--size", default="portrait"), lk, A("--text"),
         A("--place", default="bottom", choices=["top", "middle", "bottom"]),
         A("--focus", help="point to keep in view when cropping, as x,y fractions"))
    sadd("carousel-draft", cmd_social_carousel_draft, "draft carousel slides from what was said in a reel",
         A("--transcript", required=True), A("--video", help="the reel, for each slide's picture"),
         A("--hook", help="slide 1 text (default: the first sentence)"), ctas, lk,
         A("--max-words", type=int, default=22), A("--max-ideas", type=int, default=8), A("--out", required=True))
    sadd("carousel", cmd_social_carousel, "render a carousel plan (JSON) to slides", A("plan"),
         A("--out", required=True), lk)
    sadd("covers", cmd_social_covers, "reel cover options (and YouTube thumbnails) from a video and its title",
         A("video"), A("--title", required=True), A("--out", required=True), A("--count", type=int, default=3),
         A("--at", help="cover moments, comma separated (default: sharpest frames)"), lk,
         A("--thumbnail", action="store_true", help="also make 1280x720 YouTube thumbnails"))
    sadd("stories", cmd_social_stories, "three story suggestions with drafts, to post around a reel",
         A("--hook", required=True), A("--video"), A("--topic"), ctas, lk, A("--out", required=True))
    sadd("package", cmd_social_package, "one reel in: carousel, covers and three stories out, with package.json",
         A("video"), A("--transcript", required=True), A("--title", required=True), A("--name", required=True),
         A("--hook"), A("--topic"), ctas, lk, A("--caption"), A("--thumbnail", action="store_true"), A("--out"))
    add("undo", cmd_undo, "go back one version")
    add("goto", cmd_goto, "jump to a version", A("version", type=int))
    add("log", cmd_log, "list versions")
    add("build", cmd_build, "build the current edit in Resolve as a new timeline", A("--name"))

    args = p.parse_args(argv)
    try:
        args.fn(args)
    except EditError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
