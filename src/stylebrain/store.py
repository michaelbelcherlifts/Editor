"""Saved versions of an edit, so every change can be undone.

Each project is a folder of numbered versions plus a HEAD pointer:

    .stylebrain/<project>/v0001.json
    .stylebrain/<project>/HEAD

A version records the edit list, a one-line message, and its parent. Undo
moves HEAD to the parent; nothing is ever deleted.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .edl import EditError, EditList

ROOT = ".stylebrain"


class Store:
    def __init__(self, project: str, root: str | Path = ROOT) -> None:
        self.dir = Path(root) / project
        self.project = project

    def exists(self) -> bool:
        return (self.dir / "HEAD").exists()

    def head(self) -> int:
        if not self.exists():
            raise EditError(f"no project named {self.project!r}; start one with `stylebrain new`")
        return int((self.dir / "HEAD").read_text().strip())

    def _path(self, version: int) -> Path:
        return self.dir / f"v{version:04d}.json"

    def _read(self, version: int) -> dict:
        return json.loads(self._path(version).read_text())

    def load(self, version: int | None = None) -> EditList:
        return EditList.from_dict(self._read(self.head() if version is None else version)["edit"])

    def commit(self, edit: EditList, message: str) -> int:
        self.dir.mkdir(parents=True, exist_ok=True)
        parent = self.head() if self.exists() else 0
        version = max([int(p.stem[1:]) for p in self.dir.glob("v*.json")], default=0) + 1
        record = {
            "version": version,
            "parent": parent,
            "message": message,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "edit": edit.to_dict(),
        }
        self._path(version).write_text(json.dumps(record, indent=2))
        (self.dir / "HEAD").write_text(str(version))
        return version

    def undo(self) -> int:
        parent = self._read(self.head())["parent"]
        if not parent:
            raise EditError("nothing to undo: this is the first version")
        (self.dir / "HEAD").write_text(str(parent))
        return parent

    def goto(self, version: int) -> int:
        if not self._path(version).exists():
            raise EditError(f"there is no version {version}")
        (self.dir / "HEAD").write_text(str(version))
        return version

    def log(self) -> list[dict]:
        head = self.head()
        out = []
        for p in sorted(self.dir.glob("v*.json")):
            r = json.loads(p.read_text())
            out.append({k: r[k] for k in ("version", "parent", "message", "time")} | {"head": r["version"] == head})
        return out


def current_project(root: str | Path = ROOT) -> str | None:
    p = Path(root) / "CURRENT"
    return p.read_text().strip() if p.exists() else None


def set_current_project(project: str, root: str | Path = ROOT) -> None:
    Path(root).mkdir(parents=True, exist_ok=True)
    (Path(root) / "CURRENT").write_text(project)
