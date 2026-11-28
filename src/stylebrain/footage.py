"""Michael's own footage: from the Google Drive inbox (or a camera card) into the footage library.

The phone uploads to a Drive folder, `Style Brain/Inbox`. Google Drive for desktop shows that
folder as an ordinary folder on the editing computer. `pull` copies every new file from there
into the footage library (a folder on the PC for now, the SSD later), sorted into one folder
per shoot day and per device, checks each copy byte for byte, and records it. Nothing in the
inbox is deleted unless Michael asks (`clear`), because the free Drive plan holds only 15 GB.

Library layout:

    <library>/
      2026/
        2026-11-28 bench day/
          raw/phone/IMG_1234.MOV
          raw/camera/C0001.MP4
          raw/audio/mic.wav
          raw/photos/IMG_1235.HEIC
          shoot.json           what came in, from where, its checksum and when it was recorded
      pulled.json              every inbox file already copied, so a pull never copies twice

The paths live in `library/footage.json` (not committed: they differ per computer).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import string
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .edl import EditError

VIDEO = {".mov", ".mp4", ".m4v", ".mts", ".m2ts", ".mxf", ".avi", ".mkv", ".insv", ".lrv"}
AUDIO = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".aif", ".aiff"}
PHOTO = {".jpg", ".jpeg", ".heic", ".heif", ".png", ".dng", ".arw", ".cr2", ".cr3", ".nef", ".raf"}
SKIP = {".tmp", ".part", ".crdownload", ".ini", ".ds_store", ".thm", ".xml", ".lrf"}
DRIVE_FOLDER = "Style Brain"
FREE_DRIVE_GB = 15.0
SETTLE_SECONDS = 60  # a file changed more recently than this may still be arriving

# Filename starts that say which device made a clip.
DEVICE_NAMES = [
    (r"^(IMG|VID|PXL|MOV)_|^\d{8}_\d{6}|^Screen ?Recording", "phone"),
    (r"^DJI_|^DJI\d", "drone"),
    (r"^(GX|GH|GOPR|GP)\d", "action-cam"),
    (r"^(C\d{4}|DSC|MVI_|P\d{7}|_DSC|A\d{3}C\d{3})", "camera"),
]
PHONE_MAKES = ("apple", "samsung", "google", "oneplus", "motorola", "xiaomi", "pixel", "iphone")


def config_path(base: str | Path = ".") -> Path:
    return Path(base) / "library" / "footage.json"


def load_config(base: str | Path = ".") -> dict:
    p = config_path(base)
    return json.loads(p.read_text()) if p.exists() else {}


def save_config(cfg: dict, base: str | Path = ".") -> Path:
    p = config_path(base)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2) + "\n")
    return p


def find_my_drive(home: Path | None = None, platform: str | None = None,
                  roots: list[Path] | None = None) -> Path | None:
    """The "My Drive" folder that Google Drive for desktop shows on this computer, if it is there."""
    platform = platform or sys.platform
    home = home or Path.home()
    if roots is None:
        if platform.startswith("win"):
            roots = [Path(f"{letter}:\\") for letter in string.ascii_uppercase[3:]]
        elif platform == "darwin":
            cloud = home / "Library" / "CloudStorage"
            roots = sorted(cloud.glob("GoogleDrive-*")) if cloud.exists() else []
            roots += [Path("/Volumes/GoogleDrive")]
        else:
            roots = []
        roots.append(home / "Google Drive")  # older Drive versions and mirror mode
    for root in roots:
        for name in ("My Drive", "Mi unidad", "Meine Ablage"):
            if (root / name).is_dir():
                return root / name
        if root.name == "Google Drive" and root.is_dir() and not (root / "My Drive").exists():
            return root
    return None


def default_library(home: Path | None = None) -> Path:
    home = home or Path.home()
    return home / "Videos" / "Style Brain Footage"


def setup(inbox: str | None = None, library: str | None = None, finals: str | None = None,
          base: str | Path = ".", my_drive: Path | None = None) -> dict:
    """Find or take the folders, create them, and save them for this computer."""
    cfg = load_config(base)
    drive = my_drive if my_drive is not None else find_my_drive()
    if inbox:
        cfg["inbox"] = str(Path(inbox).expanduser())
    elif "inbox" not in cfg and drive:
        cfg["inbox"] = str(drive / DRIVE_FOLDER / "Inbox")
    if finals:
        cfg["finals"] = str(Path(finals).expanduser())
    elif "finals" not in cfg and drive:
        cfg["finals"] = str(drive / DRIVE_FOLDER / "Finals")
    if library:
        cfg["library"] = str(Path(library).expanduser())
    elif "library" not in cfg:
        cfg["library"] = str(default_library())
    for key in ("inbox", "finals", "library"):
        if cfg.get(key):
            Path(cfg[key]).mkdir(parents=True, exist_ok=True)
    save_config(cfg, base)
    return cfg


def _need(cfg: dict, key: str) -> Path:
    if not cfg.get(key):
        hint = ("install Google Drive for desktop and run `stylebrain footage-setup`, or pass --inbox"
                if key in ("inbox", "finals") else "run `stylebrain footage-setup --library PATH`")
        raise EditError(f"no {key} folder set: {hint}")
    p = Path(cfg[key])
    if not p.is_dir():
        what = "Is the SSD plugged in?" if key == "library" else "Is Google Drive for desktop running?"
        raise EditError(f"the {key} folder {p} is not there. {what}")
    return p


def kind_of(path: Path, tags: dict | None = None) -> str | None:
    """Which raw folder a file goes in: phone, camera, drone, action-cam, audio, photos or other.
    None for files that are not footage (sidecars, partial downloads)."""
    ext = path.suffix.lower()
    if ext in SKIP or path.name.startswith(("._", "~$", ".")):
        return None
    if ext in AUDIO:
        return "audio"
    if ext in PHOTO:
        return "photos"
    if ext not in VIDEO:
        return None
    tags = {k.lower(): str(v).lower() for k, v in (tags or {}).items()}
    make = " ".join(v for k, v in tags.items() if k.endswith(("make", "model")))
    if any(m in make for m in PHONE_MAKES):
        return "phone"
    if "dji" in make:
        return "drone"
    if "gopro" in make:
        return "action-cam"
    if make:
        return "camera"
    for pattern, kind in DEVICE_NAMES:
        if re.search(pattern, path.name, re.IGNORECASE):
            return kind
    return "other"


def read_tags(path: Path) -> dict:
    """Container tags from ffprobe (creation time, make, model). Empty if ffprobe is missing."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags", "-of", "json", str(path)],
                             capture_output=True, text=True, timeout=60)
        return (json.loads(out.stdout or "{}").get("format") or {}).get("tags") or {}
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return {}


def recorded_at(path: Path, tags: dict | None = None) -> datetime:
    """When the clip was recorded, in this computer's time: the camera's own date if the file has
    one, else when the file was last changed."""
    for key in ("com.apple.quicktime.creationdate", "creation_time", "date"):
        value = (tags or {}).get(key)
        if not value:
            continue
        try:
            when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            continue
        if when.year < 2001:  # cameras with an unset clock write 1904 or 1970
            continue
        return when.astimezone() if when.tzinfo else when
    return datetime.fromtimestamp(path.stat().st_mtime)


def _slug(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r'[<>:"/\\|?*]', "", name)).strip()


def shoot_folder(library: Path, day: datetime, name: str | None = None, rename: bool = False) -> Path:
    """The folder for a shoot day. Without a name: the day's existing folder, else a new one named by
    the date. With a name: "DATE NAME"; an unnamed folder for that day takes the name (when rename)."""
    date = day.strftime("%Y-%m-%d")
    year = library / day.strftime("%Y")
    same_day = sorted(year.glob(f"{date}*")) if year.exists() else []
    if not name:
        return same_day[0] if same_day else year / date
    wanted = year / f"{date} {_slug(name)}"
    bare = year / date
    if rename and not wanted.exists() and bare.is_dir():
        bare.rename(wanted)
        _moved(library, bare, wanted)
    return wanted


def _moved(library: Path, old: Path, new: Path) -> None:
    pulled = load_pulled(library)
    a, b = old.relative_to(library).as_posix() + "/", new.relative_to(library).as_posix() + "/"
    for v in pulled.values():
        if v["dest"].startswith(a):
            v["dest"] = b + v["dest"][len(a):]
    if pulled:
        _pulled_path(library).write_text(json.dumps(pulled, indent=1) + "\n")
    manifest = new / "shoot.json"
    if manifest.exists():
        data = json.loads(manifest.read_text())
        data["shoot"] = new.name
        manifest.write_text(json.dumps(data, indent=1) + "\n")


def sha256(path: Path, chunk: int = 8 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def _copy_checked(src: Path, dst: Path) -> str:
    """Copy src to dst, reading the source once, then read the copy back and compare checksums."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(dst.name + ".part")
    h = hashlib.sha256()
    with open(src, "rb") as fin, open(part, "wb") as fout:
        while block := fin.read(8 << 20):
            h.update(block)
            fout.write(block)
    digest = h.hexdigest()
    if sha256(part) != digest:
        part.unlink(missing_ok=True)
        raise EditError(f"the copy of {src.name} did not match the original; nothing was kept")
    os.replace(part, dst)
    st = src.stat()
    os.utime(dst, (st.st_atime, st.st_mtime))
    return digest


def _free_name(dst: Path) -> Path:
    """A name in the destination folder that is not taken (two phones both make IMG_0001.MOV)."""
    if not dst.exists():
        return dst
    n = 2
    while (cand := dst.with_name(f"{dst.stem}-{n}{dst.suffix}")).exists():
        n += 1
    return cand


def _pulled_path(library: Path) -> Path:
    return library / "pulled.json"


def load_pulled(library: Path) -> dict:
    p = _pulled_path(library)
    return json.loads(p.read_text()) if p.exists() else {}


def _key(src: Path, root: Path, size: int) -> str:
    return f"{src.relative_to(root).as_posix()}|{size}"


@dataclass
class Pulled:
    source: Path
    dest: Path | None
    kind: str
    size: int
    note: str = ""


def waiting(inbox: Path, library: Path | None = None, now: float | None = None) -> list[tuple[Path, str]]:
    """Footage in the inbox not yet in the library, with its kind, oldest first. Files still
    arriving (changed in the last minute) are left for the next pull."""
    now = now or time.time()
    pulled = load_pulled(library) if library and library.is_dir() else {}
    out = []
    for f in sorted(p for p in inbox.rglob("*") if p.is_file()):
        kind = kind_of(f)
        if kind is None:
            continue
        st = f.stat()
        if _key(f, inbox, st.st_size) in pulled or st.st_size == 0 or now - st.st_mtime < SETTLE_SECONDS:
            continue
        out.append((f, kind))
    return out


def pull(base: str | Path = ".", source: str | None = None, name: str | None = None,
         dry_run: bool = False, now: float | None = None, probe=None) -> list[Pulled]:
    """Copy new footage from the inbox (or SOURCE, such as a camera card) into the library."""
    probe = probe or read_tags
    cfg = load_config(base)
    library = _need(cfg, "library")
    inbox = Path(source).expanduser() if source else _need(cfg, "inbox")
    if not inbox.is_dir():
        raise EditError(f"{inbox} is not a folder")
    pulled = load_pulled(library)
    results: list[Pulled] = []
    shoots: dict[Path, list[dict]] = {}
    for f, _ in waiting(inbox, library, now):
        tags = probe(f) if f.suffix.lower() in VIDEO else {}
        kind = kind_of(f, tags) or "other"
        when = recorded_at(f, tags)
        folder = shoot_folder(library, when, name, rename=not dry_run)
        size = f.stat().st_size
        if dry_run:
            results.append(Pulled(f, folder / "raw" / kind / f.name, kind, size, when.strftime("%Y-%m-%d %H:%M")))
            continue
        dst = _free_name(folder / "raw" / kind / f.name)
        digest = _copy_checked(f, dst)
        pulled = load_pulled(library)  # a folder rename above may have changed the records
        results.append(Pulled(f, dst, kind, size))
        entry = {"file": dst.relative_to(folder).as_posix(), "from": str(f), "size": size, "sha256": digest,
                 "kind": kind, "recorded": when.isoformat(timespec="seconds"),
                 "pulled": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        for k in ("com.apple.quicktime.make", "com.apple.quicktime.model", "make", "model"):
            if tags.get(k):
                entry.setdefault("device", str(tags[k]))
        shoots.setdefault(folder, []).append(entry)
        pulled[_key(f, inbox, size)] = {"dest": str(dst.relative_to(library).as_posix()), "sha256": digest,
                                        "from": str(inbox)}
        _pulled_path(library).write_text(json.dumps(pulled, indent=1) + "\n")
    for folder, entries in shoots.items():
        manifest = folder / "shoot.json"
        data = json.loads(manifest.read_text()) if manifest.exists() else {"shoot": folder.name, "files": []}
        data["files"].extend(entries)
        manifest.write_text(json.dumps(data, indent=1) + "\n")
    return results


def clear(base: str | Path = ".", yes: bool = False) -> tuple[list[Path], list[str]]:
    """Inbox files that are safely in the library (copy there, same size, checksum recorded).
    With yes=True they are deleted from the inbox, which puts them in the Drive trash."""
    cfg = load_config(base)
    library, inbox = _need(cfg, "library"), _need(cfg, "inbox")
    pulled = load_pulled(library)
    safe, kept = [], []
    for key, v in pulled.items():
        rel, size = key.rsplit("|", 1)
        if v.get("from") != str(inbox):
            continue
        src, dst = inbox / rel, library / v["dest"]
        if not src.exists():
            continue
        if not dst.exists() or dst.stat().st_size != int(size) or src.stat().st_size != int(size):
            kept.append(f"{rel}: the library copy is missing or a different size, so it stays")
            continue
        safe.append(src)
    if yes:
        for src in safe:
            src.unlink()
    return safe, kept


def shoots(base: str | Path = ".") -> list[dict]:
    cfg = load_config(base)
    library = _need(cfg, "library")
    out = []
    for manifest in sorted(library.glob("*/*/shoot.json")):
        data = json.loads(manifest.read_text())
        kinds: dict[str, int] = {}
        for f in data.get("files", []):
            kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
        out.append({"shoot": manifest.parent.name, "path": str(manifest.parent), "files": len(data.get("files", [])),
                    "bytes": sum(f["size"] for f in data.get("files", [])), "kinds": kinds})
    return out


def clips(shoot: str, base: str | Path = ".", kind: str | None = None) -> list[Path]:
    """Full paths of a shoot's clips, for `new --source` and `add-source`."""
    cfg = load_config(base)
    library = _need(cfg, "library")
    matches = [m.parent for m in library.glob("*/*/shoot.json") if shoot.lower() in m.parent.name.lower()]
    if not matches:
        raise EditError(f"no shoot matching {shoot!r}; `stylebrain footage-list` shows them")
    if len(matches) > 1:
        raise EditError(f"{shoot!r} matches {len(matches)} shoots: " + ", ".join(m.name for m in matches))
    data = json.loads((matches[0] / "shoot.json").read_text())
    return [matches[0] / f["file"] for f in data["files"] if kind in (None, f["kind"])]


def final(file: str, base: str | Path = ".") -> Path:
    """Copy a finished export to Drive `Style Brain/Finals`, so it is on his phone to post."""
    src = Path(file)
    if not src.is_file():
        raise EditError(f"{file} is not a file")
    finals = _need(load_config(base), "finals")
    dst = _free_name(finals / src.name)
    _copy_checked(src, dst)
    return dst


def status(base: str | Path = ".", now: float | None = None) -> list[str]:
    cfg = load_config(base)
    if not cfg:
        return ["not set up: run `stylebrain footage-setup`"]
    lines = []
    for key, what in (("inbox", "Drive inbox"), ("finals", "Drive finals"), ("library", "footage library")):
        p = cfg.get(key)
        there = p and Path(p).is_dir()
        lines.append(f"{what}: {p or 'not set'}" + ("" if there or not p else "  (not reachable)"))
    lib = Path(cfg["library"]) if cfg.get("library") else None
    if lib and lib.is_dir():
        free = shutil.disk_usage(lib).free / 1e9
        lines.append(f"library drive: {free:.0f} GB free")
    if cfg.get("inbox") and Path(cfg["inbox"]).is_dir():
        inbox = Path(cfg["inbox"])
        files = [p for p in inbox.rglob("*") if p.is_file()]
        size = sum(p.stat().st_size for p in files) / 1e9
        new = waiting(inbox, lib if lib and lib.is_dir() else None, now)
        lines.append(f"inbox: {len(files)} files, {size:.1f} GB; {len(new)} not pulled yet")
        if size > 0.7 * FREE_DRIVE_GB:
            lines.append(f"  the inbox is using {size:.1f} of the free {FREE_DRIVE_GB:g} GB: "
                         "pull, then `footage-clear --yes` and empty the Drive trash")
    return lines
