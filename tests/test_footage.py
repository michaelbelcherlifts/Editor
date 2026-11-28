import json
import os
import time
from datetime import datetime
from pathlib import Path

import pytest

from stylebrain import footage
from stylebrain.cli import main
from stylebrain.edl import EditError

OLD = time.time() - 3600


def drop(folder: Path, name: str, data: bytes = b"x" * 1000, mtime: float = OLD) -> Path:
    p = folder / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    os.utime(p, (mtime, mtime))
    return p


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    drive = tmp_path / "G" / "My Drive"
    drive.mkdir(parents=True)
    footage.setup(library=str(tmp_path / "ssd" / "Footage"), my_drive=drive)
    cfg = footage.load_config()
    return Path(cfg["inbox"]), Path(cfg["library"]), Path(cfg["finals"])


def tags_for(name):
    if name.startswith("IMG"):
        return {"com.apple.quicktime.make": "Apple", "com.apple.quicktime.model": "iPhone 16 Pro",
                "com.apple.quicktime.creationdate": "2026-11-28T09:15:00-0500"}
    if name.startswith("C0"):
        return {"creation_time": "2026-11-28T14:20:00.000000Z", "make": "Sony"}
    return {}


def fake_probe(path):
    return tags_for(path.name)


def test_finds_my_drive_on_windows_and_mac(tmp_path):
    g = tmp_path / "G"
    (g / "My Drive").mkdir(parents=True)
    assert footage.find_my_drive(home=tmp_path, platform="win32", roots=[tmp_path / "F", g]) == g / "My Drive"
    mac = tmp_path / "Library" / "CloudStorage" / "GoogleDrive-me@example.com" / "My Drive"
    mac.mkdir(parents=True)
    assert footage.find_my_drive(home=tmp_path, platform="darwin") == mac
    assert footage.find_my_drive(home=tmp_path / "nobody", platform="linux") is None


def test_setup_makes_the_drive_folders(setup):
    inbox, library, finals = setup
    assert inbox.parts[-3:] == ("My Drive", "Style Brain", "Inbox") and inbox.is_dir()
    assert finals.name == "Finals" and finals.is_dir() and library.is_dir()


def test_kind_from_tags_and_names():
    assert footage.kind_of(Path("a.mov"), {"com.apple.quicktime.make": "Apple"}) == "phone"
    assert footage.kind_of(Path("C0001.MP4"), {"make": "Sony"}) == "camera"
    assert footage.kind_of(Path("C0001.MP4")) == "camera"
    assert footage.kind_of(Path("DJI_0001.MP4")) == "drone"
    assert footage.kind_of(Path("GX010001.MP4")) == "action-cam"
    assert footage.kind_of(Path("PXL_20261128.mp4")) == "phone"
    assert footage.kind_of(Path("mic.WAV")) == "audio" and footage.kind_of(Path("IMG_1.HEIC")) == "photos"
    assert footage.kind_of(Path("clip.mp4")) == "other"
    for skip in ("desktop.ini", "C0001M01.XML", "IMG_1.MOV.tmp", "._IMG_1.MOV", "notes.txt"):
        assert footage.kind_of(Path(skip)) is None


def test_recorded_date_from_tags_else_file_time(tmp_path):
    f = drop(tmp_path, "x.mov")
    assert footage.recorded_at(f, {"creation_time": "2026-11-28T14:20:00Z"}).astimezone().year == 2026
    assert footage.recorded_at(f, {"creation_time": "1970-01-01T00:00:00Z"}) == datetime.fromtimestamp(OLD)
    assert footage.recorded_at(f, {}) == datetime.fromtimestamp(OLD)


def test_pull_sorts_by_day_and_device_checks_and_never_copies_twice(setup):
    inbox, library, _ = setup
    drop(inbox, "IMG_0001.MOV", b"phone" * 100)
    drop(inbox, "camera/C0001.MP4", b"sony" * 100)
    drop(inbox, "desktop.ini")
    drop(inbox, "IMG_0002.MOV", mtime=time.time())  # still uploading
    done = footage.pull(name="bench day", probe=fake_probe)
    assert sorted(r.kind for r in done) == ["camera", "phone"]
    for r in done:
        assert r.dest.read_bytes() == r.source.read_bytes()
        assert r.dest.parents[2].name.endswith(" bench day") and r.dest.parents[3].name == "2026"
    shoot = done[0].dest.parents[2]
    data = json.loads((shoot / "shoot.json").read_text())
    assert {f["file"] for f in data["files"]} >= {"raw/phone/IMG_0001.MOV"}
    assert any(f.get("device") == "Apple" for f in data["files"]) and all(len(f["sha256"]) == 64 for f in data["files"])
    assert footage.pull(probe=fake_probe) == []  # nothing new; the uploading one is still settling
    assert len(footage.pull(probe=fake_probe, now=time.time() + 120)) == 1


def test_same_name_from_two_phones_both_kept(setup):
    inbox, library, _ = setup
    drop(inbox, "a/IMG_0001.MOV", b"one")
    drop(inbox, "b/IMG_0001.MOV", b"two")
    done = footage.pull(probe=fake_probe)
    assert sorted(r.dest.name for r in done) == ["IMG_0001-2.MOV", "IMG_0001.MOV"]
    assert {r.dest.read_bytes() for r in done} == {b"one", b"two"}


def test_unnamed_day_takes_a_name_later(setup):
    inbox, library, _ = setup
    drop(inbox, "IMG_0001.MOV")
    first = footage.pull(probe=fake_probe)[0].dest
    assert first.parents[2].name == "2026-11-28"
    drop(inbox, "IMG_0003.MOV", b"more")
    footage.pull(name="squat", probe=fake_probe)
    shoot = library / "2026" / "2026-11-28 squat"
    assert (shoot / "raw" / "phone" / "IMG_0001.MOV").exists() and not first.exists()
    assert len(json.loads((shoot / "shoot.json").read_text())["files"]) == 2
    assert len(footage.clips("squat")) == 2
    safe, kept = footage.clear()
    assert len(safe) == 2 and kept == []


def test_clear_only_removes_what_is_safely_copied(setup):
    inbox, library, _ = setup
    a = drop(inbox, "IMG_0001.MOV")
    done = footage.pull(probe=fake_probe)
    b = drop(inbox, "IMG_0009.MOV")  # not pulled
    done[0].dest.write_bytes(b"short")  # library copy damaged
    safe, kept = footage.clear(yes=True)
    assert safe == [] and len(kept) == 1 and a.exists() and b.exists()
    done[0].dest.write_bytes(a.read_bytes())
    safe, _ = footage.clear(yes=True)
    assert safe == [a] and not a.exists() and b.exists()


def test_camera_card_pull_and_finals(setup, tmp_path):
    inbox, library, finals = setup
    card = tmp_path / "card" / "DCIM"
    drop(card, "C0002.MP4", b"card")
    done = footage.pull(source=str(card), probe=fake_probe)
    assert done[0].kind == "camera" and done[0].dest.exists()
    export = drop(tmp_path, "reel.mp4", b"final")
    assert footage.final(str(export)).read_bytes() == b"final"
    assert footage.final(str(export)).name == "reel-2.mp4"


def test_missing_ssd_says_so(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    footage.save_config({"inbox": str(tmp_path), "library": str(tmp_path / "E" / "gone")})
    with pytest.raises(EditError, match="SSD plugged in"):
        footage.pull()


def test_cli(setup, capsys, monkeypatch):
    inbox, library, _ = setup
    drop(inbox, "clip.mp4", b"z" * 10)
    monkeypatch.setattr(footage, "read_tags", lambda p: {})
    main(["footage-status"])
    assert "1 not pulled yet" in capsys.readouterr().out
    main(["footage-pull", "--dry-run"])
    assert "would copy 1 files" in capsys.readouterr().out
    main(["footage-pull", "--name", "test"])
    assert "copied and checked 1 files" in capsys.readouterr().out
    main(["footage-list"])
    assert "1 other" in capsys.readouterr().out
    main(["footage-clear"])
    assert "run again with --yes" in capsys.readouterr().out
