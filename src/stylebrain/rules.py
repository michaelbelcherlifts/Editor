"""House rules: Michael's standing corrections, applied to every first cut.

When he corrects a cut ("that's too tight", "always put captions on"), the fix
is saved here so the same mistake is not made twice. A rule is either a setting
the tools read (how long a pause must be before it is tightened, whether
captions go on) or a note in his words for Claude to read before editing.

Kept in `library/house-rules.json`, which is not committed: the notes are his.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .edl import EditError

# name: (kind, default, lowest, highest, what it does)
SETTINGS: dict[str, tuple] = {
    "pause_min_gap": (float, 0.6, 0.15, 3.0, "pauses at least this long (seconds) are tightened"),
    "pause_air": (float, 0.12, 0.0, 0.5, "seconds of air left each side of speech when tightening"),
    "cut_retakes": (bool, True, None, None, "the first cut removes failed attempts it is sure of"),
    "captions": (bool, False, None, None, "the first cut puts captions on"),
    "style": (str, "", None, None, "the saved style a first cut aims for"),
    "look": (str, "", None, None, "the saved colour look a first cut uses"),
    "caption_font": (str, "", None, None, "the font for captions on a first cut: a named choice or an installed font"),
    "frame": (str, "", None, None, "frame size for captions and exports, such as 1080x1920"),
    "sounds_per_minute": (float, 8.0, 0.0, 60.0, "most automatic sound effects a minute (0 for no limit)"),
    "sound_gain": (float, -14.0, -40.0, 0.0, "level of automatic sound effects in dB"),
}


def path(base: str | Path = ".") -> Path:
    return Path(base) / "library" / "house-rules.json"


def load(base: str | Path = ".") -> dict:
    """The saved rules: {"settings": {...only what he changed...}, "notes": [{"text", "added"}]}."""
    p = path(base)
    data = json.loads(p.read_text()) if p.exists() else {}
    return {"settings": dict(data.get("settings", {})), "notes": list(data.get("notes", []))}


def _save(data: dict, base: str | Path = ".") -> None:
    p = path(base)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) + "\n")


def get(name: str, base: str | Path = "."):
    """The value in force: his rule when he set one, otherwise the default."""
    if name not in SETTINGS:
        raise EditError(f"no setting named {name!r}; choose from {', '.join(SETTINGS)}")
    return load(base)["settings"].get(name, SETTINGS[name][1])


def pick(given, name: str, base: str | Path = "."):
    """What was asked for on the command line wins; otherwise the house rule."""
    return get(name, base) if given is None else given


def parse(name: str, text: str):
    if name not in SETTINGS:
        raise EditError(f"no setting named {name!r}; choose from {', '.join(SETTINGS)}")
    kind, _, lo, hi, _ = SETTINGS[name]
    if kind is bool:
        word = text.strip().lower()
        if word in ("on", "yes", "true", "1"):
            return True
        if word in ("off", "no", "false", "0"):
            return False
        raise EditError(f"{name} is on or off")
    if kind is float:
        try:
            value = float(text)
        except ValueError:
            raise EditError(f"{name} is a number") from None
        if not lo <= value <= hi:
            raise EditError(f"{name} runs from {lo:g} to {hi:g}")
        return value
    if name == "frame" and text:
        try:
            w, h = (int(x) for x in text.lower().split("x"))
            assert w > 0 and h > 0
        except (ValueError, AssertionError):
            raise EditError("frame looks like 1080x1920") from None
    return text.strip()


def set_rule(name: str, text: str, base: str | Path = "."):
    value = parse(name, text)
    data = load(base)
    data["settings"][name] = value
    _save(data, base)
    return value


def clear(name: str, base: str | Path = ".") -> None:
    data = load(base)
    if name not in SETTINGS:
        raise EditError(f"no setting named {name!r}")
    data["settings"].pop(name, None)
    _save(data, base)


def add_note(text: str, base: str | Path = ".") -> int:
    text = " ".join(text.split())
    if not text:
        raise EditError("the note is empty")
    data = load(base)
    data["notes"].append({"text": text, "added": date.today().isoformat()})
    _save(data, base)
    return len(data["notes"])


def remove_note(number: int, base: str | Path = ".") -> str:
    data = load(base)
    if not 1 <= number <= len(data["notes"]):
        raise EditError(f"there is no note {number}")
    gone = data["notes"].pop(number - 1)
    _save(data, base)
    return gone["text"]


def _show(value) -> str:
    return ("on" if value else "off") if isinstance(value, bool) else (f"{value:g}" if isinstance(value, float) else str(value) or "none")


def changed(base: str | Path = ".") -> list[str]:
    """One short line per setting he has changed from the default."""
    return [f"{k} {_show(v)}" for k, v in load(base)["settings"].items() if k in SETTINGS and v != SETTINGS[k][1]]


def text(base: str | Path = ".") -> str:
    data = load(base)
    lines = ["Settings (his where marked, otherwise the default):"]
    for name, (_, default, *_rest, what) in SETTINGS.items():
        mine = name in data["settings"]
        lines.append(f"  {name:<18} {_show(data['settings'].get(name, default)):<10} {'his ' if mine else '    '} {what}")
    lines.append("Notes in his words (read these before every edit):" if data["notes"] else "No notes yet.")
    lines += [f"  {n}. {note['text']}  ({note['added']})" for n, note in enumerate(data["notes"], 1)]
    return "\n".join(lines)
