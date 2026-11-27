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
             + (f", {len(edit.sounds)} sounds" if edit.sounds else "")
             + (f", music {Path(edit.music.source).name} from {edit.music.start:g}s at {edit.music.gain_db:g} dB"
                if edit.music else "")]
    for start, seg in edit.pieces():
        lines.append(f"  {format_time(start, edit.fps):>10}  {Path(seg.source).name}  "
                     f"[{seg.src_in}-{seg.src_out})" + (f"  {seg.note}" if seg.note else "")
                     + (f"  framed x {seg.x:g} y {seg.y:g} zoom {seg.zoom:g}" if seg.framing != (0.5, 0.5, 1.0) else ""))
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
    from . import rules
    args.min_gap, args.pad = rules.pick(args.min_gap, "pause_min_gap"), rules.pick(args.pad, "pause_air")
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
                parse_time(args.duration, edit.fps), args.track, parse_time(args.start, edit.fps))
    _save(store, edit, edit.add_overlay(o), f"add overlay {args.name!r} at {args.at}")


def _source_range(args, edit: EditList) -> tuple[str, int, int]:
    """The file and frame range asked for by --from/--to, checked against the file."""
    path = str(Path(args.source).resolve())
    fps, frames = args.fps, args.frames
    if fps is None or frames is None:
        from .media import probe
        pfps, pframes = probe(path)
        fps, frames = fps or pfps, frames or pframes
    if abs(fps - edit.fps) > 0.01:
        raise EditError(f"{Path(path).name} is {fps:g} fps but this edit is {edit.fps:g} fps; "
                        "convert it to the edit's frame rate first so timings stay exact")
    lo = parse_time(args.start, edit.fps) if args.start else 0
    hi = parse_time(args.end, edit.fps) if args.end else frames
    if not 0 <= lo < hi <= frames:
        raise EditError(f"that range is outside {Path(path).name}, which is {format_time(frames, fps)} long")
    return path, lo, hi


def cmd_add_source(args) -> None:
    store = _store(args); edit = store.load()
    path, lo, hi = _source_range(args, edit)
    at = parse_time(args.at, edit.fps) if args.at else None
    from .edl import Segment
    new = edit.insert_segment(Segment(path, lo, hi, args.note or ""), at)
    where = f"at {args.at}" if args.at else "at the end"
    _save(store, edit, new, f"add {Path(path).name} {where}")
    print(f"  length {format_time(edit.duration, edit.fps)} -> {format_time(new.duration, new.fps)}")


def cmd_broll(args) -> None:
    store = _store(args); edit = store.load()
    path, lo, hi = _source_range(args, edit)
    at = parse_time(args.at, edit.fps)
    length = min(hi - lo, edit.duration - at)
    if args.duration:
        length = min(length, parse_time(args.duration, edit.fps))
    name = args.name or f"broll {Path(path).stem}@{args.at}"
    _save(store, edit, edit.add_overlay(Overlay(name, path, at, length, args.track, lo)),
          f"cover {format_time(length, edit.fps)} from {args.at} with {Path(path).name}")


def cmd_sources(args) -> None:
    edit = _store(args).load()
    for n, src in enumerate(edit.sources(), 1):
        used = sum(s.duration for s in edit.segments if s.source == src)
        print(f"  {n}. {Path(src).name}: {format_time(used, edit.fps)} on the main track  ({src})")
    extra = list(dict.fromkeys(o.source for o in edit.overlays))
    for src in extra:
        print(f"  above: {Path(src).name}  ({src})")


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
    m = reference.motion(args.video, _secs(args.start), _secs(args.end), args.threshold,
                         box=json.loads(args.box) if args.box else None)
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
        mixed = [(kind, str(path.resolve()), count) for kind, path, count in
                 sfx.stems(edit, Path(".stylebrain") / "renders", f"{store.project}-v{store.head()}-sfx")]
    if edit.music:
        from . import export, music
        renders = Path(".stylebrain") / "renders"
        try:
            key = export.voice(edit, renders / f"{store.project}-v{store.head()}-voice.wav")
        except EditError as e:
            key = None
            print(f"note: the music is not lowered under the voice ({e})")
        bed = music.bed(edit, renders / f"{store.project}-v{store.head()}-music.wav", voice=key)
        mixed = (mixed or []) + [("music", str(bed.resolve()), 1)]
    from . import resolve_notes as notes
    resolve = connect()
    project = resolve.GetProjectManager().GetCurrentProject()
    if project is not None:
        last, changed = notes.hand_changes(project, store)
        if changed:
            print(f"warning: {last!r} was changed by hand in Resolve since it was built:")
            for line in changed:
                print(f"  {line}")
            print("  The new timeline is built from the edit list and will NOT have these changes.")
            print(f"  {last!r} is left as it is. Colour grades, effects and keyframes cannot be read, so check those by eye.")
    report = build_timeline(resolve, edit, name, sound_mix=mixed)
    if report.ok and project is not None and project.GetCurrentTimeline() is not None:
        notes.remember_build(store, project.GetCurrentTimeline(), store.head())
    print(report.text())
    if not report.ok:
        sys.exit(1)


def _wh(size: str | None) -> tuple[int, int]:
    if size is None:
        from . import rules
        size = rules.get("frame") or "1080x1920"
    try:
        w, h = (int(x) for x in size.lower().split("x"))
    except ValueError:
        raise EditError("size looks like 1080x1920") from None
    return w, h


def _resolve_timeline(store, edit):
    """The current Resolve timeline, with a warning line when it is not the latest build of this edit."""
    from . import resolve_notes as notes
    from .resolve_builder import connect
    _, timeline = notes.current(connect())
    name = timeline.GetName()
    warn = ""
    if not name.startswith(f"{store.project} v{store.head()}"):
        warn = (f"note: the open timeline is {name!r}, not a build of version {store.head()} of this edit, "
                "so its times may not match the edit; build first to be sure")
    return timeline, warn


def cmd_markers(args) -> None:
    from . import resolve_notes as notes
    store = _store(args); edit = store.load()
    timeline, warn = _resolve_timeline(store, edit)
    if args.clear:
        print(f"removed {notes.clear_notes(timeline)} review marker(s); his own markers were not touched")
        return
    head = notes.playhead(timeline, edit.fps)
    marks = [m for m in notes.read_markers(timeline, edit.fps) if args.all or not m["ours"]]
    if args.json:
        print(json.dumps({"timeline": timeline.GetName(), "playhead": head, "markers": marks, "warning": warn}, indent=2))
        return
    if warn:
        print(warn)
    print("playhead: " + ("unknown" if head is None else f"{format_time(head, edit.fps)}"
                          + ("  (past the end of the edit)" if head >= edit.duration else "")))
    if not marks:
        print("no markers on the timeline")
    for m in marks:
        length = f" for {format_time(m['frames'], edit.fps)}" if m["frames"] > 1 else ""
        text = " ".join(x for x in (m["name"], m["note"]) if x and not x.startswith("Marker "))
        print(f"  {format_time(m['frame'], edit.fps):>10}{length}  {m['colour']:<8} {text}")


def cmd_music_add(args) -> None:
    from . import music
    from .edl import Music
    store = _store(args); edit = store.load()
    path = Path(args.file).resolve()
    info = music.analyse(path)
    new = edit.set_music(Music(str(path), args.start, args.gain, not args.no_duck))
    _save(store, edit, new, f"music: {path.name} from {args.start:g}s at {args.gain:g} dB")
    pulse = "a clear pulse" if info["clear"] >= 0.5 else "no clear pulse, so beat times are a rough guide"
    print(f"  {info['bpm']:g} beats a minute, {pulse}; {len(music.timeline_beats(new, info['beats']))} beats fall in the edit")


def cmd_music_remove(args) -> None:
    store = _store(args); edit = store.load()
    if edit.music is None:
        raise EditError("there is no music on this edit")
    _save(store, edit, edit.set_music(None), "remove the music")


def cmd_music_beats(args) -> None:
    from . import music
    store = _store(args); edit = store.load()
    beats = music.timeline_beats(edit)
    info = music.analyse(edit.music.source)
    cuts = [start / edit.fps for start, _ in edit.pieces()][1:]
    print(f"{info['bpm']:g} beats a minute (pulse clarity {info['clear']:g}), {len(beats)} beats in the edit")
    print("beats: " + " ".join(f"{b:.2f}" for b in beats[:64]) + (" ..." if len(beats) > 64 else ""))
    for c in cuts:
        near = min(beats, key=lambda b: abs(b - c)) if beats else None
        off = "" if near is None else f"  {'on the beat' if abs(near - c) <= 1 / edit.fps else f'{c - near:+.2f}s from the beat at {near:.2f}s'}"
        print(f"  cut at {c:7.2f}s{off}")


def cmd_music_snap(args) -> None:
    from . import music
    store = _store(args); edit = store.load()
    words = None
    if args.transcript:
        from .autopilot import timeline_words
        words = timeline_words(edit, _source_for(edit, args.source), tr.load_words(args.transcript))
    new, lines = music.snap_cuts(edit, music.timeline_beats(edit), args.max_trim, words, args.every)
    for line in lines:
        print("  " + line)
    if new != edit:
        _save(store, edit, new, lines[-1])


def cmd_rules(args) -> None:
    from . import rules
    print(rules.text())


def cmd_rule(args) -> None:
    from . import rules
    if args.clear:
        rules.clear(args.name)
        print(f"house rule cleared: {args.name} is back to {rules._show(rules.get(args.name))}")
        return
    if args.value is None:
        raise EditError("give a value, or --clear")
    print(f"house rule saved: {args.name} {rules._show(rules.set_rule(args.name, args.value))}")


def cmd_rule_note(args) -> None:
    from . import rules
    if args.remove:
        print(f"note removed: {rules.remove_note(args.remove)}")
        return
    if not args.text:
        raise EditError("give the note in quotes, or --remove N")
    print(f"house rule saved as note {rules.add_note(args.text)}")


def cmd_reframe(args) -> None:
    from . import reframe
    store = _store(args); edit = store.load()
    w, h = _wh(args.size)
    if args.auto:
        new, lines = reframe.plan(edit, w, h)
        print("\n".join(lines))
        message = "reframe to follow the subject"
    else:
        if args.x is None and args.y is None and args.zoom is None:
            raise EditError("say --auto, or give --x, --y or --zoom")
        t0 = parse_time(args.start, edit.fps) if args.start else 0
        t1 = parse_time(args.end, edit.fps) if args.end else edit.duration
        new = edit.reframe(t0, t1, args.x, args.y, args.zoom)
        parts = [f"{k} {v:g}" for k, v in (("x", args.x), ("y", args.y), ("zoom", args.zoom)) if v is not None]
        message = f"frame {format_time(t0, edit.fps)} to {format_time(t1, edit.fps)}: " + ", ".join(parts)
        if (args.zoom or 1) > 1 and args.y is None and all(s.y == 0.5 for s in new.segments if s.zoom == args.zoom):
            print("  note: the punch-in closes in on the middle of the picture; add --y 0.4 or lower if it crops his head")
    _save(store, edit, new, message)
    if not args.no_preview:
        sheet = Path(".stylebrain") / "renders" / f"{store.project}-v{store.head()}-framing.jpg"
        try:
            print(f"  frames to look at: {reframe.preview(new, sheet, w, h)}")
        except EditError as e:
            print(f"  note: no preview ({e})")


def cmd_speed(args) -> None:
    from . import speed
    store = _store(args); edit = store.load()
    t0, t1 = parse_time(args.start, edit.fps), parse_time(args.end, edit.fps)
    new, lines = speed.apply(edit, t0, t1, args.speed, store.dir / "speed", ramp=args.ramp,
                             smooth=args.smooth, sound=args.sound)
    how = f"{args.speed:g}x" + (f" with {args.ramp:g}s ramps" if args.ramp else "")
    _save(store, edit, new, f"speed {format_time(t0, edit.fps)} to {format_time(t1, edit.fps)}: {how}")
    print("\n".join(lines))


def cmd_export(args) -> None:
    from . import export
    store = _store(args); edit = store.load()
    w, h = _wh(args.size)
    out = Path(args.out or Path("exports") / f"{store.project}-v{store.head()}.mp4")
    export.render(edit, out, w, h, args.fit, args.lufs, sounds=not args.no_sounds, music=not args.no_music)
    print(f"exported {out} ({format_time(edit.duration, edit.fps)})")
    if args.no_check:
        return
    c = export.check(out, edit.duration / edit.fps, w, h, args.lufs, sheet=out.with_suffix(".frames.jpg"))
    print(c.text())
    if not c.ok:
        sys.exit(1)


def cmd_export_check(args) -> None:
    from . import export
    w, h = _wh(args.size)
    file = Path(args.file)
    c = export.check(file, args.seconds, w, h, args.lufs, sheet=None if args.no_sheet else file.with_suffix(".frames.jpg"))
    print(json.dumps({"file": c.file, **c.facts, "problems": c.problems, "notes": c.notes, "sheet": c.sheet}, indent=2)
          if args.json else c.text())
    if not c.ok:
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


def cmd_style_from_study(args) -> None:
    from . import creators
    for name, n in creators.build(args.folder):
        print(f"saved style {name!r} from {n} clips" + (" (thin)" if n < creators.MIN_CLIPS else ""))


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


def cmd_look_from_style(args) -> None:
    from . import look, style
    src = Path(args.style)
    profile = json.loads(src.read_text()) if src.suffix == ".json" and src.exists() else style.load(args.style)
    path = look.from_profile(args.name, profile, args.footage, args.strength)
    basis = f"measured from {args.footage}" if args.footage else "assuming a typical phone clip"
    print(f"saved look {args.name!r} to {path} ({basis})")


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
    found = tr.find_takes(words, args.min_words)
    if not found:
        print("no likely retakes found")
        return
    for t in found:
        said = " ".join(w.text for w in words if t.start <= w.start < t.end)[:70]
        where = ", ".join(format_time(lo, edit.fps) for lo, _ in _to_timeline(edit, source, [(t.start, t.end)])) or "already cut"
        print(f"  {where}: {t.end - t.start:.1f}s  {t.kind:<10} {'sure ' if t.sure else 'maybe'}  \"{said}\"  ({t.why})")
    if args.cut:
        chosen = [t for t in found if t.sure or args.maybe]
        ranges = _to_timeline(edit, source, [(t.start, t.end - 0.12) for t in chosen if t.end - t.start > 0.12])
        if ranges:
            _save(store, edit, edit.remove_ranges(ranges), f"cut {len(chosen)} likely retakes")
        left = len(found) - len(chosen)
        if left:
            print(f"  {left} marked maybe were left in; cut them by time, or run again with --maybe")


def cmd_srt(args) -> None:
    from .autopilot import timeline_words
    store = _store(args); edit = store.load()
    words = timeline_words(edit, _source_for(edit, args.source), tr.load_words(args.transcript))
    Path(args.out).write_text(tr.to_srt(words))
    print(f"{len(words)} words of the current cut written to {args.out}")


def cmd_review(args) -> None:
    from . import review, story, style
    target = style.load(args.style) if args.style else None
    fps, cuts, words, mine = 30.0, None, None, None
    if args.video:
        words = tr.load_words(args.transcript) if args.transcript else None
        mine = style.measure(args.video, words)
        if words:
            mine["words"] = [[w.text, w.start, w.end] for w in words]
        fps, cuts, duration = mine["frame"]["fps"], mine["cuts"], mine["frame"]["seconds"]
    else:
        from .autopilot import timeline_words
        store = _store(args); edit = store.load()
        fps, duration = edit.fps, edit.duration / edit.fps
        if args.transcript:
            words = timeline_words(edit, _source_for(edit, args.source), tr.load_words(args.transcript))
        mine = review.profile_of_edit(edit, words)
        cuts = mine["cuts"] if len(edit.pieces()) > 1 else None
    hook = [f for f in story.hook_check(words, duration, cuts) if f.serious] if words else []
    found = review.compare(mine, target, args.limit) if target else []
    if args.markers:
        if args.video:
            raise EditError("--markers writes onto the Resolve timeline of the current edit; leave out --video")
        from . import resolve_notes as notes
        timeline, warn = _resolve_timeline(store, edit)
        if warn:
            print(warn)
        notes.clear_notes(timeline)
        placed, failed = notes.add_notes(timeline, [(x.at, x.kind, x.text) for x in [*hook, *found]], fps)
        print(f"wrote {placed} review marker(s) onto {timeline.GetName()!r}"
              + (f"; {failed} could not be placed" if failed else ""))
    if args.json:
        print(json.dumps({"hook": story.to_json(hook), "style": review.to_json(found)}, indent=2))
        return
    if hook:
        print(f"Story and hook first, {len(hook)} to fix:")
        for f in hook:
            print(f.line())
    elif words:
        print("No hook problems measured.")
    if not target:
        if not words:
            raise EditError("give --transcript for the hook check, or a style to compare against")
        return
    if not found:
        print(f"nothing stands out against {args.style!r}")
    else:
        print(f"{len(found)} things to look at, measured against {args.style!r}:")
        for s in found:
            print(s.line(fps))


def cmd_auto(args) -> None:
    from . import autopilot
    result = autopilot.run(args.name, args.source, args.transcript, args.style, args.look,
                           True if args.captions else None, False if args.keep_retakes else None,
                           not args.no_build, args.width, args.height)
    print(result.text(Store(args.name).load().fps))


def cmd_score(args) -> None:
    from . import score as sc
    if args.questions:
        for key, text in {**sc.JUDGEMENTS, **sc.NUMBERS, **sc.FLAGS}.items():
            print(f"  {key}: {text}")
        return
    if not args.transcript and not args.video:
        raise EditError("score needs --video, --transcript, or both")
    words = tr.drop_phantom_speech(tr.load_words(args.transcript)) if args.transcript else []
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


def _json_arg(text: str | None, default):
    if not text:
        return default
    return json.loads(Path(text[1:]).read_text() if text.startswith("@") else text)


def _clip_inputs(args) -> tuple[list, float, list | None]:
    words = tr.drop_phantom_speech(tr.load_words(args.transcript))
    cuts, duration = None, getattr(args, "seconds", None)
    if getattr(args, "video", None):
        from . import style
        m = style.measure(args.video, None)
        cuts, duration = m["cuts"], m["frame"]["seconds"]
    if duration is None:
        duration = words[-1].end if words else 0.0
    return words, duration, cuts


def cmd_hook_check(args) -> None:
    from . import story
    words, duration, cuts = _clip_inputs(args)
    found = story.hook_check(words, duration, cuts, _json_arg(args.judge, {}))
    if args.json:
        print(json.dumps(story.to_json(found), indent=2))
        return
    serious = [f for f in found if f.serious]
    print(f"{len(serious)} hook problems" + (f", {len(found) - len(serious)} things to check by eye" if len(found) > len(serious) else "") + ":")
    for f in found:
        print(f.line())


def cmd_beats(args) -> None:
    from . import story
    words, duration, _ = _clip_inputs(args)
    try:
        bm = story.beat_map(words, duration, _json_arg(args.beats, None), _json_arg(args.questions, None), args.limit)
    except ValueError as e:
        raise EditError(str(e)) from e
    print(json.dumps(bm.to_dict(), indent=2) if args.json else bm.text())


def cmd_hooks(args) -> None:
    from . import story
    if args.spoken is None:
        print("Hook types (write three options, each a different type):")
        for key, (what, example) in story.HOOK_TYPES.items():
            print(f"  {key:<11}{what}. e.g. \"{example}\"")
        return
    problems = story.check_hook_option(args.spoken, args.text or "")
    print("hook ok" if not problems else "\n".join(f"  {p}" for p in problems))


def cmd_script_check(args) -> None:
    from . import story
    if args.questions or not args.script:
        for key, text in story.STORY_QUESTIONS.items():
            print(f"  {key}: {text}")
        return
    text = Path(args.script).read_text()
    out = story.check_script(text)
    if args.story:
        try:
            out["story_points"] = story.story_points(_json_arg(args.story, {}))
        except ValueError as e:
            raise EditError(str(e)) from e
    if args.json:
        print(json.dumps(out, indent=2))
        return
    print(f"{out['lines']} lines, about {out['seconds']:.0f}s spoken, sentences average {out['average_sentence_words']} words")
    if "story_points" in out:
        print(f"story {out['story_points']:g} / 25" + ("" if out["story_points"] >= 20 else ": under 20, rework the story before the lines"))
    print("\n".join(f"  {n}" for n in out["notes"]) if out["notes"] else "  no problems measured")


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
    outcome = {k: getattr(args, k) for k in ("views", "subscribers", "retention", "swiped_away", "reach", "likes",
                                             "comments", "shares", "saves") if getattr(args, k) is not None}
    if duration is None and words:
        duration = words[-1].end
    if duration is None:
        if not outcome and args.age_days is None:
            raise EditError("give --video or --transcript to measure the clip, or results such as --views or --likes")
        attrs = {}  # results only: update what happened to a clip already in the set
    else:
        attrs = learn.attributes(words, duration, cuts, frame, audio, colour, judge)
    if args.age_days is not None:
        attrs["age_days"] = args.age_days
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


def cmd_clip_pull(args) -> None:
    from . import learn
    print(f"took {learn.pull(args.folder)} clip records into the learning set")


def cmd_learn(args) -> None:
    from . import learn
    within = True if args.within else False if args.mixed else None
    result = learn.fit(learn.load_all(), args.target, only_mine=args.mine, within=within)
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
    from . import rules
    args.gain, args.per_minute = rules.pick(args.gain, "sound_gain"), rules.pick(args.per_minute, "sounds_per_minute")
    try:
        beats = tuple(parse_time(b, edit.fps) / edit.fps for b in args.beats.split(",")) if args.beats else ()
    except EditError:
        raise EditError("--beats is a list of times, such as 12.5,31") from None
    new, lines = sfx.auto_place(edit, words, tuple(args.on.split(",")), args.gain, args.duck, args.min_cut_gap,
                                 safe_only=args.ad, per_minute=args.per_minute, beats=beats)
    if not lines:
        print("nothing to place sounds on")
        return
    _save(store, edit, new, f"place {sum(x.name.startswith('auto:') for x in new.sounds)} sounds automatically")
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

# ----- content plan: ideas, series, calendar, weekly plans, shoot lists (nothing ever posts)

def _plan():
    from .content import Plan
    return Plan()


def _kv(pairs) -> dict:
    out = {}
    for item in pairs or []:
        if "=" not in item:
            raise EditError(f"expected KEY=VALUE, got {item!r}")
        k, v = item.split("=", 1)
        out[k.strip()] = None if v.strip().lower() in ("", "none", "null") else v.strip()
    return out


def cmd_idea_add(args) -> None:
    plan = _plan()
    i = plan.add_idea(args.title, args.pillar, format=args.format, hook=args.hook, series=args.series,
                      cta=args.cta, source=args.source, location=args.location,
                      shots=[s.strip() for s in (args.shots or "").split(";") if s.strip()],
                      note=args.note, score=args.score, draft=args.draft, hold=args.hold)
    plan.save()
    ep = f", episode {i['episode']} of {i['series']}" if i["series"] else ""
    print(f"{i['id']}: {i['title']} ({i['format']}, {i['pillar']}{ep})")


def cmd_idea_import(args) -> None:
    plan = _plan()
    items = json.loads(Path(args.file).read_text())
    made = plan.import_ideas(items if isinstance(items, list) else items.get("ideas", []), source=args.source)
    plan.save()
    print(f"added {len(made)} ideas ({made[0]['id']} to {made[-1]['id']})" if made else "no ideas in the file")


def cmd_idea_list(args) -> None:
    plan = _plan()
    ideas = [i for i in plan.ideas if (not args.status or i["status"] == args.status)
             and (not args.pillar or i["pillar"] == args.pillar) and (not args.format or i["format"] == args.format)]
    if args.json:
        print(json.dumps(ideas, indent=2)); return
    for i in ideas:
        when = plan._first_date(i["id"]) or "-"
        print(f"{i['id']:<5}{i['status']:<10}{i['format']:<10}{i['pillar']:<9}{when:<11}{i['title']}"
              + (f"  [{i['series']} #{i['episode']}]" if i["series"] else "")
              + (f"  score {i['score']:g}" if i["score"] is not None else "")
              + (f"  on hold: {i['hold']}" if i.get("hold") else ""))
    print(f"{len(ideas)} ideas")


def cmd_idea_set(args) -> None:
    plan = _plan()
    fields = _kv(args.set)
    if args.status:
        fields["status"] = args.status
    i = plan.set_idea(args.id, **fields)
    plan.save()
    print(f"{i['id']}: " + ", ".join(f"{k} = {i[k]}" for k in fields))


def cmd_series_add(args) -> None:
    plan = _plan()
    plan.add_series(args.key, args.name, args.premise)
    plan.save()
    print(f"series {args.key!r}: {args.name}")


def cmd_series_list(args) -> None:
    for s in _plan().series_view():
        print(f"{s['key']}: {s['name']} ({len(s['episodes'])} episodes)\n  {s['premise']}")
        for e in s["episodes"]:
            print(f"  #{e['episode']} {e['id']} {e['status']:<9}{e['date'] or '-':<11}{e['title']}")


def cmd_plan_settings(args) -> None:
    plan = _plan()
    st = plan.settings
    for k, v in _kv(args.set).items():
        group, _, key = k.partition(".")
        if group in ("volume", "pillars") and key:
            if v is None:
                st[group].pop(key, None)
            else:
                st[group][key] = float(v)
        elif group in st and not key:
            st[group] = float(v) if isinstance(st[group], float) else int(v)
        else:
            raise EditError(f"unknown setting {k!r} (try volume.reel=7, pillars.run=0.2, coaching_per_week=2)")
    plan.save()
    print(json.dumps(st, indent=2))


def cmd_plan_week(args) -> None:
    from .content import format_rows
    plan = _plan()
    result = plan.propose_week(args.week)
    plan.save()
    print(f"Proposed {len(result['posts'])} posts for the week of {result['week']}. Nothing is final until "
          f"`plan-approve {result['week']}`, and nothing posts by itself.")
    print(format_rows(plan.rows(result["week"], 7)))
    for s in result["shortfalls"]:
        print(f"backlog short: {s}")


def cmd_plan_approve(args) -> None:
    plan = _plan()
    done = plan.approve_week(args.week)
    plan.save()
    print(f"approved {len(done)} posts")


def cmd_calendar(args) -> None:
    from .content import format_rows, to_html
    plan = _plan()
    if args.html:
        Path(args.html).write_text(to_html(plan, args.start, args.days))
        print(f"wrote {args.html}")
    elif args.json:
        print(json.dumps(plan.rows(args.start, args.days), indent=2))
    else:
        print(format_rows(plan.rows(args.start, args.days)))


def cmd_post_add(args) -> None:
    plan = _plan()
    p = plan.schedule(args.idea, args.date, cta=args.cta,
                      platforms=args.platforms.split(",") if args.platforms else None)
    plan.save()
    print(f"{p['id']}: {args.idea} on {p['date']} to {', '.join(p['platforms'])}, cta {p['cta']}")


def cmd_post_set(args) -> None:
    plan = _plan()
    p = plan.set_post(args.id, date=args.date, cta=args.cta, status=args.status,
                      platforms=args.platforms.split(",") if args.platforms else None)
    plan.save()
    print(f"{p['id']}: {p['date']}, {', '.join(p['platforms'])}, cta {p['cta']}, {p['status']}")


def cmd_post_result(args) -> None:
    plan = _plan()
    p = plan.record_result(args.id, url=args.url, platform=args.platform, views=args.views, reach=args.reach, likes=args.likes,
                           comments=args.comments, saves=args.saves, sends=args.sends, follows=args.follows,
                           enquiries=args.enquiries)
    plan.save()
    print(f"{p['id']}: {p['status']}" + (f", {p['url']}" if p["url"] else "")
          + "".join(f", {k} {v:g}" for k, v in p["results"].items()))


def cmd_social_import(args) -> None:
    plan = _plan()
    made = plan.import_social(json.loads(Path(args.package).read_text()), args.reel)
    plan.save()
    for p in made:
        print(f"{p['id']}: {p['format']} on {p['date']} ({plan.idea(p['idea'])['title']}), cta {p['cta']}")
    print(f"placed {len(made)} posts around {args.reel}")


def cmd_crosspost(args) -> None:
    from . import crosspost
    plan = _plan()
    r = crosspost.make(plan, args.post, video=args.video, long_video=args.long_video, transcript=args.transcript,
                       out_dir=args.out)
    plan.save()
    print(f"{r['post']} ({r['title']}, {r['date']}): {len(r['versions'])} versions in {r['dir']}")
    for v in r["versions"]:
        state = "ready" if not v["problems"] else f"{len(v['problems'])} to fix"
        print(f"  {v['platform']:<15}{state:<10}{r['dir']}/{v['platform']}.txt")
        for p in v["problems"]:
            print(f"      fix: {p}")
    print("drafts only: rewrite them in his voice before he sees them; nothing was posted")


def cmd_crosspost_week(args) -> None:
    from . import crosspost
    plan = _plan()
    rows = crosspost.week(plan, args.week, make_missing=args.make)
    if args.make:
        plan.save()
    print(json.dumps(rows, indent=2) if args.json else crosspost.format_week(rows))


def cmd_shoot_list(args) -> None:
    from .content import format_shoot_list
    sl = _plan().shoot_list(args.week)
    print(json.dumps(sl, indent=2) if args.json else format_shoot_list(sl))


def cmd_week_report(args) -> None:
    from .content import format_week_report
    rep = _plan().week_report(args.week)
    print(json.dumps(rep, indent=2) if args.json else format_week_report(rep))


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
        A("--min-gap", type=float, help="default: the house rule, else 0.6"),
        A("--pad", type=float, help="default: the house rule, else 0.12"))
    add("overlay-add", cmd_overlay_add, "place a clip above the main track", A("name"),
        A("--source", required=True), A("--at", required=True), A("--duration", required=True),
        A("--track", type=int, default=2), A("--start", default="0", help="where in the clip to start from"))
    clip = [A("source"), A("--from", dest="start", help="where in the clip to start (default: its start)"),
            A("--to", dest="end", help="where in the clip to stop (default: its end)"),
            A("--fps", type=float), A("--frames", type=int)]
    add("add-source", cmd_add_source, "add another clip, or part of one, to the main track", *clip,
        A("--at", help="timeline position (default: the end)"), A("--note"))
    add("broll", cmd_broll, "cover part of the timeline with another clip (picture only), main audio keeps playing",
        *clip, A("--at", required=True), A("--duration"), A("--track", type=int, default=2), A("--name"))
    add("sources", cmd_sources, "list the clips this edit uses")
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
        A("--threshold", type=float, default=0.6), A("--curve", action="store_true"),
        A("--box", help="[x, y, w, h] as fractions: watch only this part of the frame"))
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
    add("style-from-study", cmd_style_from_study, "save one style per creator from the creator study",
        A("folder", nargs="?", default="data/creator-study"))
    add("look-make", cmd_look_make, "make a colour look (LUT) that moves your footage toward a reference",
        A("name"), A("--reference", required=True), A("--footage", required=True, help="your own clip"),
        A("--strength", type=float, default=1.0, help="0 to 1"))
    add("look-from-style", cmd_look_from_style, "make a colour look from a measured style (no reference video)",
        A("name"), A("--style", required=True, help="saved style name, or a profile .json file"),
        A("--footage", help="your own clip, measured so the look starts from it"),
        A("--strength", type=float, default=0.8, help="0 to 1"))
    add("look-preview", cmd_look_preview, "before / after / reference image for a look", A("name"),
        A("--video", required=True), A("--at", default="0"), A("--out", required=True),
        A("--reference"), A("--ref-at", default="0"))
    add("look-list", cmd_look_list, "list saved looks")
    add("look-use", cmd_look_use, "put a saved look on the edit ('none' removes it)", A("name"))
    add("transcribe", cmd_transcribe, "make a word-timing transcript with a local speech-to-text tool",
        A("video"), A("--out"), A("--engine"), A("--model"))
    add("retakes", cmd_retakes, "list likely failed attempts: repeats, restarts, lines said again, 'start over', stutters", *tx,
        A("--min-words", type=int, default=4), A("--cut", action="store_true", help="cut the sure ones"),
        A("--maybe", action="store_true", help="with --cut, also cut the ones marked maybe"))
    add("srt", cmd_srt, "write subtitles for the current cut", *tx, A("--out", required=True))
    add("review", cmd_review, "hook check, then compare the current cut (or a video file) with a saved style", A("style", nargs="?"),
        A("--video", help="a finished video file to review, not the current edit"),
        A("--transcript"), A("--source"), A("--limit", type=int, default=8), A("--json", action="store_true"),
        A("--markers", action="store_true", help="also write the notes onto the Resolve timeline as markers"))
    add("auto", cmd_auto, "first cut in one go: retakes, pauses, look, captions, build, review", A("name"),
        A("--source", required=True), A("--transcript"), A("--style"), A("--look"),
        A("--captions", action="store_true"), A("--keep-retakes", action="store_true"),
        A("--no-build", action="store_true"),
        A("--width", type=int, help="default: the house rule for frame, else 1920"), A("--height", type=int))
    add("score", cmd_score, "score a short clip on the virality rubric, part by part",
        A("--transcript", help="word timings of the clip (leave out for a clip with no speech)"),
        A("--video", help="the clip, to measure cuts, frame and sound"),
        A("--seconds", type=float, help="clip length when no video is given"),
        A("--judge", help="Claude's judgements as JSON or @file (see --questions)"),
        A("--questions", action="store_true", help="list the judgements and flags"), A("--json", action="store_true"))
    clip = [A("--transcript", required=True, help="word timings of the clip"),
            A("--video", help="the clip, to measure cuts"), A("--seconds", type=float, help="length when no video is given")]
    add("hook-check", cmd_hook_check, "what holds the first seconds back, with the second it happens", *clip,
        A("--judge", help="JSON or @file: text_on_frame_1, undelivered, first_point"), A("--json", action="store_true"))
    add("beats", cmd_beats, "beat map of a long-form transcript: dead stretches and \"and then\" runs", *clip,
        A("--beats", help='your labels as JSON or @file: [{"label": "hook", "start": 0}, ...]'),
        A("--questions", help="extra re-hook times you marked, as a JSON list of seconds"),
        A("--limit", type=float, default=60.0, help="longest stretch allowed with no new question"),
        A("--json", action="store_true"))
    add("hooks", cmd_hooks, "list hook types, or check one written hook", A("spoken", nargs="?"),
        A("--text", help="the on-screen text that goes with it"))
    add("script-check", cmd_script_check, "measured checks on a written script (one spoken line per line)", A("script", nargs="?"),
        A("--questions", action="store_true", help="list the five story questions"),
        A("--story", help="your answers to the five story questions, JSON or @file"), A("--json", action="store_true"))
    add("clip-add", cmd_clip_add, "add a clip's attributes and results to the learning set", A("id"),
        A("--transcript"), A("--video"), A("--seconds", type=float), A("--judge"), A("--about"),
        A("--views", type=float), A("--subscribers", type=float), A("--retention", type=float),
        A("--swiped-away", type=float), A("--reach", type=float), A("--likes", type=float),
        A("--comments", type=float), A("--shares", type=float), A("--saves", type=float),
        A("--age-days", type=float, help="days since it was posted, so older clips are compared fairly"),
        A("--mine", action="store_true", help="it is one of your own clips"))
    add("clip-import", cmd_clip_import, "read results from an Instagram (Meta Business Suite) or YouTube Studio export (CSV)", A("csv"),
        A("--subscribers", "--followers", type=int, help="your follower or subscriber count, for the reach target"),
        A("--all-posts", action="store_true", help="include photos and carousels, not only reels"))
    add("clip-list", cmd_clip_list, "list clips in the learning set")
    add("learn", cmd_learn, "learn which attributes go with clips doing well", A("--target", default="reach"),
        A("--mine", action="store_true", help="use only your own clips"), A("--json", action="store_true"),
        A("--within", action="store_true", help="compare each clip with its own creator's usual (the default when there are several creators)"),
        A("--mixed", action="store_true", help="pool all creators together; mostly learns who the creator is"))
    add("clip-pull", cmd_clip_pull, "copy clip records from a shared folder into the learning set", A("folder"))
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
        A("--on", default="cuts,overlays,zooms", help="any of cuts, overlays, zooms, risers"),
        A("--per-minute", type=float, help="most automatic sounds a minute (0 for no limit; default: the house rule, else 8)"),
        A("--beats", help="times of story beats that get a hit and are kept first, such as 12.5,31"),
        A("--gain", type=float, help="default: the house rule, else -14"),
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

    from .content import CTAS, FORMATS
    pillar = A("--pillar", required=True, help="strength, run, humour or life")
    add("idea-add", cmd_idea_add, "add an idea to the backlog", A("title"), pillar,
        A("--format", default="reel", choices=list(FORMATS)), A("--hook"), A("--series"),
        A("--cta", choices=list(CTAS)), A("--source", default="own", help="own, trend, clip, analytics ..."),
        A("--location", help="where it is filmed: gym, track, range, kitchen ..."),
        A("--shots", help="shots to film, separated by ;"), A("--note"), A("--score", type=float), A("--draft"),
        A("--hold", help="keep it out of weekly plans until ready, with the reason"))
    add("idea-import", cmd_idea_import, "add ideas from a JSON list (trend report, clip candidates, notes)",
        A("file"), A("--source"))
    add("idea-list", cmd_idea_list, "list the idea backlog", A("--status"), A("--pillar"), A("--format"),
        A("--json", action="store_true"))
    add("idea-set", cmd_idea_set, "change an idea (status, hook, score, draft ...)", A("id"), A("--status"), sets)
    add("series-add", cmd_series_add, "start a series", A("key"), A("--name", required=True),
        A("--premise", required=True))
    add("series-list", cmd_series_list, "list series and their episodes")
    add("plan-settings", cmd_plan_settings, "show or change weekly volume, pillar mix and call-to-action rules", sets)
    week = A("week", nargs="?", default="next-week", help="any date in the week, this-week or next-week")
    add("plan-week", cmd_plan_week, "propose a week's posts from the backlog (for approval)", week)
    add("plan-approve", cmd_plan_approve, "approve a proposed week onto the calendar", week)
    add("calendar", cmd_calendar, "show the calendar (two weeks by default)", A("--start", default="today"),
        A("--days", type=int, default=14), A("--html", help="write a page instead"), A("--json", action="store_true"))
    add("post-add", cmd_post_add, "put an idea on a date", A("idea"), A("date"), A("--cta", choices=list(CTAS)),
        A("--platforms", help="comma-separated, default by format"))
    add("post-set", cmd_post_set, "move, re-target or drop a post", A("id"), A("--date"),
        A("--cta", choices=list(CTAS)), A("--platforms"), A("--status"))
    add("post-result", cmd_post_result, "record that he posted it, and its numbers", A("id"), A("--url"),
        A("--platform", help="instagram, tiktok, youtube-shorts or youtube: keep a link and numbers per app"),
        *[A(f"--{k}", type=float) for k in ("views", "reach", "likes", "comments", "saves", "sends", "follows",
                                            "enquiries")])
    add("social-import", cmd_social_import, "place a carousel/story package around a reel's post", A("package"),
        A("--reel", required=True, help="the reel's post id"))
    add("crosspost", cmd_crosspost, "prepare a post's versions for each platform (captions, titles, hashtags, checks)",
        A("post", help="the calendar post id"), A("--video", help="the exported cut; default the idea's draft"),
        A("--long-video", help="a 16:9 export for YouTube long-form"),
        A("--transcript", help="word timings; default a .json/.srt next to the video"), A("--out"))
    add("crosspost-week", cmd_crosspost_week, "which of a week's reels are ready for every platform", week,
        A("--make", action="store_true", help="prepare every approved post that has a cut and no package yet"),
        A("--json", action="store_true"))
    add("shoot-list", cmd_shoot_list, "what to film for a week, by location", week, A("--json", action="store_true"))
    add("week-report", cmd_week_report, "planned versus posted for a week, with results", week,
        A("--json", action="store_true"))
    add("undo", cmd_undo, "go back one version")
    add("goto", cmd_goto, "jump to a version", A("version", type=int))
    add("log", cmd_log, "list versions")
    out = [A("--size", help="default: the house rule for frame, else 1080x1920"), A("--lufs", type=float, default=-14.0, help="target loudness")]
    add("markers", cmd_markers, "read his markers and playhead from the open Resolve timeline",
        A("--all", action="store_true", help="include review markers written by this tool"),
        A("--clear", action="store_true", help="remove the review markers this tool wrote"),
        A("--json", action="store_true"))
    add("music-add", cmd_music_add, "put a music track under the edit", A("file"),
        A("--start", type=float, default=0.0, help="seconds into the song where the edit begins"),
        A("--gain", type=float, default=-18.0, help="level in dB"),
        A("--no-duck", action="store_true", help="do not lower it under speech"))
    add("music-remove", cmd_music_remove, "take the music off")
    add("music-beats", cmd_music_beats, "show the tempo, the beats and how far each cut is from one")
    add("music-snap", cmd_music_snap, "move cuts back onto the beat by trimming the clip before each",
        A("--max-trim", type=float, default=0.3, help="most seconds a cut may move"),
        A("--every", type=int, default=1, help="use every Nth beat"),
        A("--transcript", help="word timings, so no word is clipped"), A("--source"))
    add("rules", cmd_rules, "show the house rules: his standing corrections")
    add("rule", cmd_rule, "set a house rule, such as: rule pause_min_gap 0.45", A("name"), A("value", nargs="?"),
        A("--clear", action="store_true", help="go back to the default"))
    add("rule-note", cmd_rule_note, "save a correction in his words for Claude to follow", A("text", nargs="?"),
        A("--remove", type=int, help="remove note N"))
    add("reframe", cmd_reframe, "place the crop when footage fills a frame of another shape, or punch in",
        A("--auto", action="store_true", help="follow the subject through every shot"),
        A("--from", dest="start"), A("--to", dest="end"),
        A("--x", type=float, help="0 is the left edge, 1 the right"), A("--y", type=float, help="0 is the top"),
        A("--zoom", type=float, help="1 is no punch-in"), A("--size", help="default: the house rule for frame, else 1080x1920"),
        A("--no-preview", action="store_true"))
    add("speed", cmd_speed, "slow motion or speed-up on part of the timeline, with optional ramps in and out",
        A("--from", dest="start", required=True), A("--to", dest="end", required=True),
        A("--speed", type=float, required=True, help="0.5 is half speed, 2 is double"),
        A("--ramp", type=float, default=0.0, help="seconds of source to ease in and out of the speed"),
        A("--smooth", action="store_true", help="make in-between frames by motion interpolation (slower to render)"),
        A("--sound", action="store_true", help="keep the clip's own sound, pitch kept (no ramps)"))
    add("export", cmd_export, "render the edit to a file ready to post, then check it", A("out", nargs="?"), *out,
        A("--fit", default="fill", choices=["fill", "fit"], help="fill crops to cover the frame; fit keeps it all with bars"),
        A("--no-sounds", action="store_true"), A("--no-music", action="store_true"),
        A("--no-check", action="store_true"))
    add("export-check", cmd_export_check, "check a finished file (from here or from Resolve) before posting", A("file"), *out,
        A("--seconds", type=float, help="how long it should be"), A("--no-sheet", action="store_true"),
        A("--json", action="store_true"))
    add("build", cmd_build, "build the current edit in Resolve as a new timeline", A("--name"))

    args = p.parse_args(argv)
    try:
        args.fn(args)
    except EditError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
