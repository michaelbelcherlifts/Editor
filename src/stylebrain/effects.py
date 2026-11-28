"""The effect library: named, reusable animation recipes.

A recipe is a template plus the settings that make it yours, saved as JSON in
`library/effects/`. "Use the caption pop here" means: load the recipe, change
the text, render it, and place it on the timeline.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .edl import EditError
from .render import Rendered, render_html
from .templates import TEMPLATES, build

LIBRARY = Path("library/effects")
RENDERS = Path(".stylebrain/renders")


def save(name: str, template: str, params: dict, about: str = "", reference: str = "",
         library: Path = LIBRARY) -> Path:
    if template not in TEMPLATES:
        raise EditError(f"no template named {template!r}; there are: {', '.join(sorted(TEMPLATES))}")
    if not name.replace("-", "").replace("_", "").isalnum():
        raise EditError("effect names use letters, numbers, hyphens and underscores")
    library.mkdir(parents=True, exist_ok=True)
    path = library / f"{name}.json"
    path.write_text(json.dumps({"name": name, "template": template, "params": params,
                                "about": about, "reference": reference}, indent=2))
    return path


def load(name: str, library: Path = LIBRARY) -> dict:
    path = library / f"{name}.json"
    if not path.exists():
        from . import arsenal
        if library == LIBRARY and any(e["id"] == name for e in arsenal.load()):
            return arsenal.as_recipe(arsenal.get(name))   # an arsenal entry places like a saved effect
        have = ", ".join(e["name"] for e in list_effects(library)) or "none yet"
        raise EditError(f"no saved effect named {name!r} (saved: {have})")
    return json.loads(path.read_text())


def list_effects(library: Path = LIBRARY) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(library.glob("*.json"))]


def render_effect(name: str, overrides: dict | None = None, out: str | Path | None = None,
                  fps: float = 30.0, width: int = 1920, height: int = 1080,
                  library: Path = LIBRARY) -> Rendered:
    """Render a saved effect, with any settings overridden for this use."""
    recipe = load(name, library)
    params = {**recipe["params"], **(overrides or {})}
    return render_template(recipe["template"], params, out, fps, width, height, label=name)


def render_template(template: str, params: dict, out: str | Path | None = None, fps: float = 30.0,
                    width: int = 1920, height: int = 1080, label: str | None = None) -> Rendered:
    if template != "html":
        params = {**params, "width": width, "height": height}
    html, duration = build(template, params)
    if out is None:
        key = hashlib.sha1(json.dumps([template, params, fps], sort_keys=True).encode()).hexdigest()[:10]
        out = RENDERS / f"{label or template}-{key}.mov"
    return render_html(html, out, duration, fps=fps, width=width, height=height)
