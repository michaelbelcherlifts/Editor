"""Sound effects: a tagged local library, automatic placement, and the mix.

The library is a folder of sound files (`library/sfx/`) with an index that
records each sound's tags, licence and where it came from. Sounds are placed
on the edit list like overlays, so they follow cuts and can be undone. At
build time every placed sound is mixed into one audio file the length of the
timeline, with each sound's level set and lowered under speech, and that one
file goes on an audio track in Resolve.

Any sound can go in the library. Its licence is always recorded and shown,
never enforced: what to use where is Michael's decision. For paid ads, pass
`safe_only=True` (the `--ad` option) to use only his own recordings, sounds
made here, and CC0 or public-domain sounds.
"""

from __future__ import annotations

import json
import re
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

from .edl import EditError, EditList, Sound
from .media import run
from .transcript import Word

# Licences that need no credit and allow any use, for the ad-safe filter.
SAFE = {"cc0", "pdm", "public-domain", "own", "made-here"}
OPENVERSE = "https://api.openverse.org/v1/audio/"


def root(base: str | Path = ".") -> Path:
    return Path(base) / "library" / "sfx"


def _index(base: str | Path = ".") -> Path:
    return root(base) / "index.json"


def load(base: str | Path = ".") -> list[dict]:
    path = _index(base)
    return json.loads(path.read_text()) if path.exists() else []


def _save(items: list[dict], base: str | Path = ".") -> None:
    root(base).mkdir(parents=True, exist_ok=True)
    _index(base).write_text(json.dumps(sorted(items, key=lambda i: i["file"]), indent=2) + "\n")


def _seconds(path: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], text=True).stdout
    try:
        return round(float(out.strip()), 3)
    except ValueError:
        raise EditError(f"{path} is not a sound file ffmpeg can read") from None


def add(file: str | Path, tags: list[str], licence: str, source: str = "", credit: str = "",
        base: str | Path = ".") -> dict:
    """Copy a sound into the library as a 48 kHz wav and record its tags and licence (any licence)."""
    key = licence.strip().lower()
    if not key:
        raise EditError("say what the licence is, or 'unknown', so it is on record")
    tags = sorted({t.strip().lower() for t in tags if t.strip()})
    if not tags:
        raise EditError("give at least one tag, such as whoosh, pop, hit or riser")
    src = Path(file)
    if not src.exists():
        raise EditError(f"{src} does not exist")
    name = re.sub(r"[^a-z0-9]+", "-", src.stem.lower()).strip("-") or "sound"
    dest = root(base) / f"{name}.wav"
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vn", "-ar", "48000", "-ac", "2", str(dest)])
    item = {"file": dest.name, "tags": tags, "licence": key, "source": source, "credit": credit,
            "seconds": _seconds(dest)}
    _save([i for i in load(base) if i["file"] != dest.name] + [item], base)
    return item


def find(tag: str, base: str | Path = ".", turn: int = 0, safe_only: bool = False) -> dict:
    """A sound with this tag. `turn` rotates through the matches so repeats vary.

    safe_only keeps to sounds whose licence needs no credit and allows any use.
    """
    matches = [i for i in load(base) if tag.lower() in i["tags"] and (not safe_only or i["licence"] in SAFE)]
    if not matches:
        have = sorted({t for i in load(base) for t in i["tags"]})
        raise EditError(f"no sound tagged {tag!r} in the library (tags there: {', '.join(have) or 'none'}); "
                        "run `stylebrain sfx-basics` for a starter set")
    return matches[turn % len(matches)]


BASICS = {
    "pop": ("sine=frequency=880:duration=0.09", "afade=t=out:st=0.01:d=0.08,volume=0.8", ["pop", "caption"]),
    "click": ("anoisesrc=color=white:duration=0.03", "highpass=f=2000,afade=t=out:st=0:d=0.03,volume=0.6", ["click", "tick"]),
    "whoosh": ("anoisesrc=color=pink:duration=0.45", "bandpass=f=1200:width_type=o:w=2,afade=t=in:st=0:d=0.25,afade=t=out:st=0.25:d=0.2,volume=1.5", ["whoosh", "cut", "zoom"]),
    "thud": ("sine=frequency=58:duration=0.3", "afade=t=out:st=0.02:d=0.28,volume=1.2", ["thud", "hit", "impact"]),
    "riser": ("anoisesrc=color=white:duration=1.2", "highpass=f=800,afade=t=in:st=0:d=1.15,afade=t=out:st=1.15:d=0.05,volume=0.7", ["riser", "build"]),
}


def make_basics(base: str | Path = ".") -> list[dict]:
    """Make a small starter set of sounds with ffmpeg, so nothing has to be downloaded to begin."""
    tmp = root(base) / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    out = []
    try:
        for name, (src, chain, tags) in BASICS.items():
            path = tmp / f"basic-{name}.wav"
            run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", src, "-af", chain, str(path)])
            out.append(add(path, tags, "made-here", "ffmpeg", base=base))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "stylebrain-sfx/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "stylebrain-sfx/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def fetch(query: str, tags: list[str], count: int = 5, max_seconds: float = 4.0, base: str | Path = ".",
          licence: str = "cc0", get_json=_get_json, download=_download) -> tuple[list[dict], list[str]]:
    """Search Openverse and download sounds. Returns (added, skipped reasons).

    licence: "cc0" by default (free for any use, no credit); a comma list of
    Openverse licence codes such as "cc0,by"; or "any". Each sound's actual
    licence and creator are recorded either way.
    """
    wanted = None if licence.strip().lower() == "any" else {x.strip().lower() for x in licence.split(",") if x.strip()}
    params = {"q": query, "page_size": max(count * 4, 20)}
    if wanted:
        params["license"] = ",".join(sorted(wanted))
    url = OPENVERSE + "?" + urllib.parse.urlencode(params)
    try:
        results = get_json(url).get("results", [])
    except OSError as e:
        raise EditError(f"could not reach Openverse: {e}") from None
    added, skipped = [], []
    tmp = root(base) / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        for r in results:
            if len(added) >= count:
                break
            title = str(r.get("title") or r.get("id") or "sound")
            got = str(r.get("license") or "unknown").lower()
            if wanted and got not in wanted:
                skipped.append(f"{title}: licence is {got!r}, not {' or '.join(sorted(wanted))}")
                continue
            seconds = (r.get("duration") or 0) / 1000
            if seconds and seconds > max_seconds:
                skipped.append(f"{title}: {seconds:.1f}s is longer than {max_seconds:g}s")
                continue
            if not r.get("url"):
                skipped.append(f"{title}: no file link")
                continue
            ext = re.sub(r"[^a-z0-9]", "", str(r.get("filetype") or "mp3").lower()) or "mp3"
            path = tmp / (re.sub(r"[^a-z0-9]+", "-", f"{query}-{title}".lower()).strip("-")[:60] + "." + ext)
            try:
                download(r["url"], path)
                item = add(path, tags, got, r.get("foreign_landing_url") or r["url"], str(r.get("creator") or ""), base)
            except (OSError, EditError) as e:
                skipped.append(f"{title}: {e}")
                continue
            if item["seconds"] > max_seconds:
                (root(base) / item["file"]).unlink()
                _save([i for i in load(base) if i["file"] != item["file"]], base)
                skipped.append(f"{title}: {item['seconds']:.1f}s is longer than {max_seconds:g}s")
                continue
            added.append(item)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return added, skipped


# ---------------------------------------------------------------- placement

def sound_for(edit: EditList, tag: str, at: int, name: str, gain_db: float, base: str | Path = ".",
              turn: int = 0, safe_only: bool = False) -> Sound:
    item = find(tag, base, turn, safe_only)
    frames = max(1, round(item["seconds"] * edit.fps))
    return Sound(name, str((root(base) / item["file"]).resolve()), at, min(frames, edit.duration - at), gain_db, tag)


def auto_place(edit: EditList, words: list[Word] | None = None, on: tuple[str, ...] = ("cuts", "overlays", "zooms"),
               gain_db: float = -14.0, duck_db: float = 6.0, min_cut_gap: float = 2.5, min_gap: float = 0.35,
               base: str | Path = ".", safe_only: bool = False) -> tuple[EditList, list[str]]:
    """Place sounds on cuts, overlay starts and zooms. Returns the new edit and a line per sound.

    cuts: a whoosh where the picture cuts, but only cuts at least `min_cut_gap`
      seconds apart, so a run of tightened pauses is left alone.
    overlays: a pop where a graphic or caption effect appears (running
      caption tracks are skipped).
    zooms: a whoosh where a clip marked as a zoom starts.
    Sounds that land on speech (from `words`, timeline times) are lowered by `duck_db`.
    Earlier automatic sounds are replaced; sounds placed by hand are kept.
    """
    fps = edit.fps
    if any(x.name.startswith("auto:") for x in edit.sounds):
        edit = edit.remove_sounds("auto:")
    wanted: list[tuple[int, str, str]] = []
    pieces = edit.pieces()
    # A zoom is a clip baked as one, or a clip punched in further than the clip before it.
    zooms = {start for n, (start, seg) in enumerate(pieces)
             if seg.note.startswith("zoom") or (n and seg.zoom > pieces[n - 1][1].zoom + 0.02)}
    if "zooms" in on:
        wanted += [(start, "zoom", "whoosh") for start in sorted(zooms)]
    if "overlays" in on:
        wanted += [(o.at, "overlay", "pop") for o in edit.overlays if not o.name.startswith("captions ")]
    if "cuts" in on:
        last = -10 ** 9
        for start, seg in pieces[1:]:
            if start in zooms:
                continue
            if (start - last) / fps >= min_cut_gap:
                wanted.append((start, "cut", "whoosh"))
                last = start
    unknown = set(on) - {"cuts", "overlays", "zooms"}
    if unknown:
        raise EditError(f"unknown place {sorted(unknown)[0]!r}; choose from cuts, overlays, zooms")
    taken = sorted(x.at for x in edit.sounds)
    lines, turn = [], {}
    order = {"zoom": 0, "overlay": 1, "cut": 2}
    for at, why, tag in sorted(wanted, key=lambda w: (w[0], order[w[1]])):
        if at >= edit.duration or any(abs(at - t) / fps < min_gap for t in taken):
            continue
        n = turn.get(tag, 0)
        turn[tag] = n + 1
        sound = sound_for(edit, tag, at, f"auto:{why}@{at}", gain_db, base, n, safe_only)
        t0, t1 = at / fps, (at + sound.duration) / fps
        spoken = bool(words) and any(w.start < t1 and w.end > t0 for w in words)
        if spoken:
            sound = Sound(sound.name, sound.source, sound.at, sound.duration, gain_db - duck_db, tag)
        edit = edit.add_sound(sound)
        taken.append(at)
        lines.append(f"{at / fps:7.2f}s  {tag:<7} on {why}" + ("  (lowered under speech)" if spoken else ""))
    return edit, lines


def mix(edit: EditList, out: str | Path, batch: int = 60) -> Path | None:
    """Mix every placed sound into one stereo wav the length of the timeline. None when there are no sounds."""
    if not edit.sounds:
        return None
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    total = edit.duration / edit.fps
    sounds = sorted(edit.sounds, key=lambda x: x.at)
    parts = []
    for b in range(0, len(sounds), batch):
        group = sounds[b:b + batch]
        cmd, chains = ["ffmpeg", "-v", "error", "-y"], []
        for n, x in enumerate(group):
            cmd += ["-t", f"{x.duration / edit.fps:.4f}", "-i", x.source]
            ms = round(x.at / edit.fps * 1000)
            chains.append(f"[{n}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={x.gain_db:.1f}dB,"
                          f"adelay={ms}:all=1[s{n}]")
        mixed = "".join(f"[s{n}]" for n in range(len(group)))
        chains.append(f"{mixed}amix=inputs={len(group)}:normalize=0:duration=longest,apad=whole_dur={total:.4f}[m]")
        part = out if len(sounds) <= batch else out.with_name(f"{out.stem}.part{b // batch}.wav")
        run(cmd + ["-filter_complex", ";".join(chains), "-map", "[m]", "-t", f"{total:.4f}", "-ar", "48000", str(part)])
        parts.append(part)
    if len(parts) > 1:
        cmd = ["ffmpeg", "-v", "error", "-y"]
        for part in parts:
            cmd += ["-i", str(part)]
        run(cmd + ["-filter_complex", f"amix=inputs={len(parts)}:normalize=0", "-t", f"{total:.4f}", str(out)])
        for part in parts:
            part.unlink()
    return out
