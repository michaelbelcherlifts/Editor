"""Shared page setup for animation templates: the design stage and the caption safe zone."""

from __future__ import annotations

from .edl import EditError

FONT = "'Inter','SF Pro Display','Helvetica Neue','Segoe UI',Arial,sans-serif"
HEAVY = "'Inter Display','Inter','Arial Black','Segoe UI Black','Helvetica Neue',Arial,sans-serif"

# Named font choices, each a stack of fonts that ship with macOS or Windows so one of them is there.
FONTS = {
    "inter": FONT,
    "helvetica": "'Helvetica Neue',Helvetica,Arial,sans-serif",
    "impact": "Impact,Haettenschweiler,'Arial Narrow Bold','Arial Black',sans-serif",
    "condensed": "'Avenir Next Condensed','Bahnschrift Condensed','Arial Narrow','Helvetica Neue',sans-serif",
    "rounded": "'SF Pro Rounded','Arial Rounded MT Bold','Nunito','Segoe UI',sans-serif",
    "serif": "Georgia,'Times New Roman',Times,serif",
    "mono": "'JetBrains Mono','SF Mono',Menlo,Consolas,'Courier New',monospace",
}


# Fonts that ship inside the editor (SIL Open Font License, see fonts/OFL-*.txt), so a page looks the same
# on any computer. Inter is named by many templates but is rarely installed; without it pages fell back to
# Arial Black, which is much of what made captions look auto-generated.
EMBEDDED = {"montserrat": ("Montserrat", "Montserrat.ttf"), "anton": ("Anton", "Anton.ttf"), "inter": ("Inter", "Inter.ttf")}


def font_faces(*names: str) -> str:
    """@font-face rules (the font file inlined) for embedded fonts, by key: montserrat, anton, inter."""
    import base64
    from pathlib import Path
    out = []
    for key in names:
        family, file = EMBEDDED[key]
        data = base64.b64encode((Path(__file__).parent / "fonts" / file).read_bytes()).decode()
        out.append(f"@font-face{{font-family:'{family}';src:url(data:font/ttf;base64,{data}) format('truetype');"
                   "font-weight:100 900;font-style:normal}")
    return "".join(out)


def font_stack(name: str) -> str:
    """The CSS font list for a named choice, or for any font installed on this computer by its exact name."""
    import re
    key = name.strip().lower()
    if key in EMBEDDED and key != "inter":
        return f"'{EMBEDDED[key][0]}',{FONT}"
    if key in FONTS:
        return FONTS[key]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 \-]{0,60}", name.strip()):
        raise EditError(f"font names use letters, numbers, spaces and hyphens; the named choices are {', '.join(FONTS)}")
    return f"'{name.strip()}',{FONT}"


def with_font(html: str, name: str | None) -> str:
    """The same page with every piece of text set in the chosen font."""
    if not name:
        return html
    key = name.strip().lower()
    faces = font_faces(key) if key in EMBEDDED else ""
    return html.replace("</style>", f"{faces}#stage,#stage *{{font-family:{font_stack(name)} !important}}</style>", 1)


# Running captions sit in this band of the frame (fractions of its height). Cards and
# panels keep out of it so they never cover the words being spoken.
CAPTION_BAND = (0.70, 0.92)


def _stage(width: int, height: int) -> tuple[float, float, float]:
    """Templates are designed for a frame whose short side is 1080. Returns the
    design-space width and height, and the scale that maps it onto the real frame."""
    scale = min(width, height) / 1080
    return width / scale, height / scale, scale


def _page(body: str, css: str, width: int = 1920, height: int = 1080, script: str = "") -> str:
    sw, sh, scale = _stage(width, height)
    js = f"<script>{script}</script>" if script else ""
    return (f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
            f"html,body{{margin:0;background:transparent;overflow:hidden}}"
            f"#stage{{width:{sw:.2f}px;height:{sh:.2f}px;zoom:{scale:.5f};position:relative;"
            f"overflow:hidden;font-family:{FONT}}}"
            f"{css}</style></head><body><div id='stage'>{body}</div>{js}</body></html>")


def keep_clear_box(height_px: float, want: float, keep_clear, margin: float = 0.04) -> tuple[float, float]:
    """Top and height (design pixels) for a centred card that stays above `keep_clear`.

    keep_clear is a [top, bottom] band as fractions of the frame height (the caption
    zone by default), or None to centre the card with no limit. The card shrinks to fit.
    """
    if keep_clear is None:
        h = min(want, height_px * (1 - 2 * margin))
        return (height_px - h) / 2, h
    if len(keep_clear) != 2 or not 0 <= keep_clear[0] < keep_clear[1] <= 1:
        raise EditError("keep_clear is [top, bottom] as fractions of the frame height")
    top_room = keep_clear[0] - 0.02 - margin
    bottom_room = 1 - keep_clear[1] - 0.02 - margin
    if top_room >= bottom_room:   # card goes above the band
        space_top, space = margin * height_px, top_room * height_px
    else:                         # band is high on the frame: card goes below it
        space_top, space = (keep_clear[1] + 0.02) * height_px, bottom_room * height_px
    h = min(want, space)
    return space_top + (space - h) / 2, h
