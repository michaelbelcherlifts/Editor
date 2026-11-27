"""One command from a raw recording to a first cut.

Each step is saved as its own version, so any of them can be undone alone:
retakes out, pauses tightened, look on, captions placed. Then the timeline is
built in Resolve and the cut is reviewed against a style when one is named.

Autopilot makes a first pass for Michael to react to. It reports every cut it
made so nothing is removed silently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import transcript as tr
from .edl import EditError, EditList, Overlay, format_time
from .store import Store, set_current_project

CHUNK_SECONDS = 20.0


@dataclass
class Result:
    project: str
    steps: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    built: bool = False

    def text(self, fps: float = 30.0) -> str:
        lines = [f"autopilot: {self.project}"] + [f"  done: {s}" for s in self.steps]
        lines += [f"  note: {n}" for n in self.notes]
        if self.suggestions:
            lines.append("  review:")
            lines += ["  " + s.line(fps) for s in self.suggestions]
        return "\n".join(lines)


def mapper(edit: EditList, source: str):
    """A function turning a source range in seconds into timeline ranges in seconds."""
    def spans(a: float, b: float) -> list[tuple[float, float]]:
        return [(lo / edit.fps, hi / edit.fps)
                for lo, hi in edit.timeline_ranges_for_source(source, round(a * edit.fps), round(b * edit.fps))]
    return spans


def timeline_words(edit: EditList, source: str, words: list[tr.Word]) -> list[tr.Word]:
    return tr.on_timeline(words, mapper(edit, source))


def _frames(edit: EditList, source: str, spans: list[tuple[float, float]]) -> list[tuple[int, int]]:
    out = []
    for lo, hi in spans:
        out += edit.timeline_ranges_for_source(source, round(lo * edit.fps), round(hi * edit.fps))
    return out


def caption_chunks(words: list[tr.Word], chunk: float = CHUNK_SECONDS) -> list[list[tr.Word]]:
    """Split timeline words into runs of about `chunk` seconds, breaking between caption lines."""
    chunks: list[list[tr.Word]] = []
    for line in tr.caption_lines(words, max_chars=26):
        if chunks and line[-1].end - chunks[-1][0].start <= chunk:
            chunks[-1] += line
        else:
            chunks.append(list(line))
    return chunks


def place_captions(edit: EditList, words: list[tr.Word], width: int, height: int, track: int = 2,
                   render=None, template: str = "captions", extra: dict | None = None) -> EditList:
    """Render running captions for timeline words and add them as overlays."""
    if render is None:
        from .effects import render_template as render
    for n, chunk in enumerate(caption_chunks(words), 1):
        start = chunk[0].start
        params = {**(extra or {}), "words": [{"word": w.text, "start": round(w.start - start, 3), "end": round(w.end - start, 3)}
                            for w in chunk]}
        r = render(template, params, None, edit.fps, width, height, f"captions{n:03d}")
        at = round(start * edit.fps)
        frames = min(r.frames, edit.duration - at)
        if frames > 0:
            edit = edit.add_overlay(Overlay(f"captions {n}", str(Path(r.path).resolve()), at, frames, track))
    return edit


def run(name: str, source: str, transcript: str | None = None, style_name: str | None = None,
        look_name: str | None = None, captions: bool | None = None, retakes: bool | None = None, build: bool = True,
        width: int | None = None, height: int | None = None, connect=None, render=None,
        preset: str | None = None) -> Result:
    """Anything left as None follows the house rules (`rules.py`), then the defaults.

    `preset` names a ready-made style (`presets.py`): its caption treatment is
    used, and its pause length unless a house rule or a learned style sets one.
    """
    from . import presets, rules
    from .media import probe

    chosen = presets.get(preset) if preset else None
    if chosen and captions is None:
        captions = bool(chosen["template"])

    style_name = rules.pick(style_name, "style") or None
    look_name = rules.pick(look_name, "look") or None
    captions = rules.pick(captions, "captions")
    retakes = rules.pick(retakes, "cut_retakes")
    if width is None or height is None:
        frame = rules.get("frame")
        width, height = (int(x) for x in frame.split("x")) if frame else (1920, 1080)

    store = Store(name)
    if store.exists():
        raise EditError(f"a project named {name!r} already exists")
    source = str(Path(source).resolve())
    result = Result(name)

    # Transcript first, so nothing is created if it cannot be made.
    if transcript is None:
        beside = Path(source).with_suffix(".words.json")
        if beside.exists():
            transcript = str(beside)
        else:
            from .transcribe import transcribe
            path, _ = transcribe(source)
            transcript = str(path)
            result.steps.append(f"transcribed to {path.name}")
    if str(transcript).lower().endswith((".srt", ".vtt")):
        raise EditError("subtitle files only have rough timings, too rough to cut on; "
                        "use a word-timing transcript (`stylebrain transcribe`)")
    words = tr.load_words(transcript)
    if not words:
        raise EditError("the transcript has no word timings")

    target = None
    if style_name:
        from . import style
        target = style.load(style_name)
    lut = None
    if look_name:
        from . import look
        lut = str(look.find(look_name).resolve())

    fps, frames = probe(source)
    edit = EditList.from_clip(source, frames, fps)
    store.commit(edit, f"start from {Path(source).name}")
    set_current_project(name)
    result.steps.append(f"started from {Path(source).name}, {format_time(edit.duration, fps)}")
    if chosen:
        result.steps.append(f"preset {preset!r}: {chosen['about']}")
    if rules.changed():
        result.steps.append("house rules in force: " + ", ".join(rules.changed()))

    def save(new: EditList, message: str) -> None:
        nonlocal edit
        version = store.commit(new, message)
        edit = new
        result.steps.append(f"v{version}: {message}; now {format_time(edit.duration, fps)}")

    kept = words
    if retakes:
        takes = tr.find_takes(words)
        found = [(t.start, t.end) for t in takes if t.sure]
        for t in takes:
            if not t.sure:
                said = " ".join(w.text for w in words if t.start <= w.start < t.end)[:60]
                result.notes.append(f"possible {t.kind}, not cut, source {t.start:.1f}s to {t.end:.1f}s: "
                                    f"\"{said}\" ({t.why})")
        kept = [w for w in words if not any(a <= w.start < b for a, b in found)]
        ranges = _frames(edit, source, [(a, b - 0.12) for a, b in found if b - a > 0.12])  # leave air before the repeat
        if ranges:
            save(edit.remove_ranges(ranges), f"cut {len(found)} likely retakes")
            for a, b in found:
                said = " ".join(w.text for w in words if a <= w.start < b)[:60]
                result.notes.append(f"retake cut, source {a:.1f}s to {b:.1f}s: \"{said}\"")

    min_gap = rules.get("pause_min_gap")
    if chosen and "pause_min_gap" not in rules.load()["settings"]:
        min_gap = chosen["pause_min_gap"]
    if target and target.get("speech") and "pause_min_gap" not in rules.load()["settings"]:
        min_gap = round(min(max(target["speech"]["long_gap"] * 1.5, 0.35), 1.0), 2)   # his own rule beats the style
    ranges = _frames(edit, source, tr.tighten_ranges(kept, min_gap, rules.get("pause_air"), frames / fps))
    if ranges:
        save(edit.remove_ranges(ranges), f"tighten {len(ranges)} pauses of {min_gap:g}s or more")

    if lut:
        save(edit.set_look(lut), f"use the look {look_name!r}")

    on_tl = timeline_words(edit, source, words)
    srt = Path(".stylebrain") / "renders" / f"{name}.srt"
    srt.parent.mkdir(parents=True, exist_ok=True)
    srt.write_text(tr.to_srt(on_tl))
    result.notes.append(f"subtitles for the cut saved to {srt}")
    if captions:
        if chosen and not chosen["template"]:
            result.notes.append(f"the preset {preset!r} has no captions on screen; none placed")
        else:
            new = place_captions(edit, on_tl, width, height, render=render,
                                 template=chosen["template"] if chosen else "captions",
                                 extra=chosen["params"] if chosen else None)
            save(new, f"place captions in {len(new.overlays) - len(edit.overlays)} pieces"
                 + (f" ({preset})" if chosen else ""))

    if build:
        try:
            from .resolve_builder import build_timeline
            from .resolve_builder import connect as real_connect
            report = build_timeline((connect or real_connect)(), edit, f"{name} v{store.head()}")
            result.built = report.ok
            (result.steps if report.ok else result.notes).append(report.text())
        except EditError as e:
            result.notes.append(f"not built in Resolve: {e}. The edit is saved; run `stylebrain build` when Resolve is open.")

    if target:
        from .review import compare, profile_of_edit
        result.suggestions = compare(profile_of_edit(edit, on_tl), target)
    return result
