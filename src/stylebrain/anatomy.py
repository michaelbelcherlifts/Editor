"""A simple stylized body figure, front and back, with each muscle group as its own shape.

Drawn from scratch as plain geometry, so there is no licensing to track. It is a
teaching diagram, not a medical illustration: shapes are approximate regions.
"""

from __future__ import annotations

from .edl import EditError

# The body silhouette, shared by both views. Coordinates are in a 400 x 800 box.
_BODY = (
    "<circle cx='200' cy='66' r='40'/>"
    "<rect x='183' y='100' width='34' height='34' rx='8'/>"
    "<path d='M112,132 Q200,112 288,132 Q306,150 300,200 L268,372 Q264,404 270,432 "
    "L130,432 Q136,404 132,372 L100,200 Q94,150 112,132 Z'/>"
    "<rect x='66' y='140' width='48' height='160' rx='24'/><rect x='286' y='140' width='48' height='160' rx='24'/>"
    "<rect x='62' y='286' width='42' height='140' rx='21'/><rect x='296' y='286' width='42' height='140' rx='21'/>"
    "<circle cx='82' cy='444' r='19'/><circle cx='318' cy='444' r='19'/>"
    "<rect x='132' y='408' width='66' height='220' rx='33'/><rect x='202' y='408' width='66' height='220' rx='33'/>"
    "<rect x='142' y='604' width='50' height='166' rx='25'/><rect x='208' y='604' width='50' height='166' rx='25'/>"
    "<rect x='134' y='756' width='60' height='28' rx='14'/><rect x='206' y='756' width='60' height='28' rx='14'/>"
)

# Each muscle: shapes for the figure's left half; they are mirrored to the right half.
# A shape ending in "!" sits on the centre line and is not mirrored.
_FRONT = {
    "traps": ["<path d='M184,112 L146,138 L184,142 Z'/>"],
    "shoulders": ["<ellipse cx='104' cy='160' rx='27' ry='31'/>"],
    "chest": ["<path d='M197,150 Q150,144 130,168 Q130,214 160,222 Q186,226 197,214 Z'/>"],
    "biceps": ["<ellipse cx='95' cy='232' rx='17' ry='44'/>"],
    "triceps": ["<path d='M72,196 Q62,236 72,282 L80,282 L80,196 Z'/>"],
    "forearms": ["<ellipse cx='83' cy='350' rx='17' ry='58'/>"],
    "abs": ["<rect x='170' y='234' width='60' height='150' rx='16'/>!"],
    "obliques": ["<path d='M163,236 Q142,300 150,384 L164,376 Z'/>"],
    "quads": ["<ellipse cx='166' cy='512' rx='27' ry='92'/>"],
    "calves": ["<ellipse cx='167' cy='682' rx='18' ry='60'/>"],
}
_BACK = {
    "traps": ["<path d='M200,108 L146,142 L200,262 L254,142 Z'/>!"],
    "rear_delts": ["<ellipse cx='104' cy='160' rx='27' ry='31'/>"],
    "lats": ["<path d='M134,188 Q126,290 176,352 L194,270 L150,180 Z'/>"],
    "triceps": ["<ellipse cx='91' cy='230' rx='20' ry='46'/>"],
    "forearms": ["<ellipse cx='83' cy='350' rx='17' ry='58'/>"],
    "lower_back": ["<rect x='176' y='300' width='48' height='86' rx='14'/>!"],
    "glutes": ["<ellipse cx='167' cy='440' rx='31' ry='32'/>"],
    "hamstrings": ["<ellipse cx='166' cy='546' rx='26' ry='70'/>"],
    "calves": ["<ellipse cx='167' cy='676' rx='20' ry='62'/>"],
}
VIEWS = {"front": _FRONT, "back": _BACK}

LABELS = {
    "traps": "Traps", "shoulders": "Front shoulders", "rear_delts": "Rear shoulders", "chest": "Chest",
    "biceps": "Biceps", "triceps": "Triceps", "forearms": "Forearms", "abs": "Abs", "obliques": "Obliques",
    "quads": "Quads", "calves": "Calves", "lats": "Lats", "lower_back": "Lower back", "glutes": "Glutes",
    "hamstrings": "Hamstrings",
}
ALIASES = {
    "pecs": "chest", "pectorals": "chest", "pec": "chest", "delts": "shoulders", "deltoids": "shoulders",
    "front delts": "shoulders", "anterior delts": "shoulders", "shoulder": "shoulders",
    "rear delts": "rear_delts", "posterior delts": "rear_delts", "bicep": "biceps", "tricep": "triceps",
    "forearm": "forearms", "core": "abs", "abdominals": "abs", "quadriceps": "quads", "quad": "quads",
    "calf": "calves", "lat": "lats", "back": "lats", "lower back": "lower_back", "erectors": "lower_back",
    "spinal erectors": "lower_back", "glute": "glutes", "hamstring": "hamstrings", "hams": "hamstrings",
    "trapezius": "traps", "upper back": "traps",
}


def resolve_muscles(names: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """Turn spoken muscle names into shape keys, and pick which views are needed.

    Returns (views, [(key, label), ...]) in the order given.
    """
    keys = []
    for name in names:
        k = name.strip().lower().replace("-", " ")
        k = ALIASES.get(k, k).replace(" ", "_")
        if k not in LABELS:
            raise EditError(f"no muscle called {name!r}; known: {', '.join(sorted(LABELS))}")
        keys.append(k)
    in_front = all(k in _FRONT for k in keys)
    in_back = all(k in _BACK for k in keys)
    views = ["front"] if in_front else ["back"] if in_back else ["front", "back"]
    return views, [(k, LABELS[k]) for k in keys]


def figure_svg(view: str) -> str:
    left, centre = [], []
    for key, shapes in VIEWS[view].items():
        for s in shapes:
            (centre if s.endswith("!") else left).append(s.rstrip("!").replace("/>", f" class='m m-{key}'/>"))
    return ("<svg viewBox='40 16 320 778' xmlns='http://www.w3.org/2000/svg'>"
            f"<g class='body'>{_BODY}</g><g>{''.join(left)}</g>"
            f"<g transform='translate(400,0) scale(-1,1)'>{''.join(left)}</g><g>{''.join(centre)}</g></svg>")
