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
             f"{len(edit.overlays)} overlays, {edit.fps:g} fps"]
    for start, seg in edit.pieces():
        lines.append(f"  {format_time(start, edit.fps):>10}  {Path(seg.source).name}  "
                     f"[{seg.src_in}-{seg.src_out})" + (f"  {seg.note}" if seg.note else ""))
    for o in sorted(edit.overlays, key=lambda o: o.at):
        lines.append(f"  {format_time(o.at, edit.fps):>10}  overlay {o.name!r} on V{o.track}, "
                     f"{format_time(o.duration, edit.fps)}  {Path(o.source).name}")
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
    report = build_timeline(connect(), edit, name)
    print(report.text())
    if not report.ok:
        sys.exit(1)


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
