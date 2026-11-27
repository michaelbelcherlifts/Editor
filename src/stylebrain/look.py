"""Turn the colour of a reference video into a LUT for Michael's footage.

The scripting API cannot touch Resolve's colour wheels or curves, but it can
put a LUT on a clip. So a look is made here: frames of the reference and of
his footage are compared, and a .cube file is written that moves his tones and
colour balance toward the reference. Looks are saved in `library/looks/`.

This matches overall tone and balance. It does not copy local work such as
skin isolation, vignettes or film grain.
"""

from __future__ import annotations

import re
from pathlib import Path

from .edl import EditError
from .media import info, read_frames, run

SIZE = 33


def root(base: str | Path = ".") -> Path:
    return Path(base) / "library" / "looks"


def path_for(name: str, base: str | Path = ".") -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        raise EditError("look names use letters, numbers, - and _ only")
    return root(base) / f"{name}.cube"


def list_looks(base: str | Path = ".") -> list[str]:
    return sorted(p.stem for p in root(base).glob("*.cube"))


def find(name: str, base: str | Path = ".") -> Path:
    path = path_for(name, base)
    if not path.exists():
        raise EditError(f"no look named {name!r} ({', '.join(list_looks(base)) or 'none saved yet'})")
    return path


def _pixels(video: str, samples: int):
    d = info(video).duration
    frames = read_frames(video, d * 0.02, d * 0.98, fps=max(samples / (d * 0.96), 0.01), width=160)
    return frames.reshape(-1, 3)


def curves(mine, reference, strength: float = 1.0):
    """Three 256-step curves that move `mine` pixels toward `reference` pixels.

    Each colour channel's spread of values is matched to the reference's, then
    smoothed and blended with "no change" by `strength` (0 to 1).
    """
    import numpy as np

    if not 0 <= strength <= 1:
        raise EditError("strength is between 0 and 1")
    levels = np.arange(256, dtype=np.float64)
    out = []
    for ch in range(3):
        ha = np.bincount(mine[:, ch], minlength=256) / len(mine)
        hb = np.bincount(reference[:, ch], minlength=256) / len(reference)
        # Rank at the middle of each level, so a pile of pixels at one value maps to the middle of its match.
        a, b = ha.cumsum() - ha / 2, hb.cumsum() - hb / 2
        m = np.interp(a, b, levels)
        # Outside the range his footage actually uses there is nothing to match: carry on in parallel.
        used = np.nonzero(np.bincount(mine[:, ch], minlength=256))[0]
        lo, hi = used[0], used[-1]
        m[:lo] = m[lo] - (lo - levels[:lo])
        m[hi + 1:] = m[hi] + (levels[hi + 1:] - hi)
        pad = np.pad(m, 6, mode="edge")
        m = np.convolve(pad, np.ones(13) / 13, mode="valid")
        m = np.maximum.accumulate(np.clip(m, 0, 255))
        out.append((levels + (m - levels) * strength) / 255.0)
    return np.stack(out)


def write_cube(path: str | Path, curve, title: str = "look", size: int = SIZE) -> Path:
    """Write per-channel curves as a 3D .cube file (red changes fastest)."""
    import numpy as np

    grid = np.linspace(0, 255, size)
    r, g, b = (np.interp(grid, np.arange(256), curve[ch]) for ch in range(3))
    lines = [f'TITLE "{title}"', f"LUT_3D_SIZE {size}", "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0", ""]
    for bi in range(size):
        for gi in range(size):
            for ri in range(size):
                lines.append(f"{r[ri]:.6f} {g[gi]:.6f} {b[bi]:.6f}")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path


def make(name: str, reference: str, mine: str, strength: float = 1.0, samples: int = 24,
         base: str | Path = ".") -> Path:
    """Make and save a look that moves `mine` toward `reference`."""
    out = path_for(name, base)
    c = curves(_pixels(mine, samples), _pixels(reference, samples), strength)
    return write_cube(out, c, title=name)


def _lut_filter(lut: str | Path) -> str:
    escaped = str(Path(lut).resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    return f"lut3d=file='{escaped}'"


def apply_to_file(video: str, lut: str | Path, out: str | Path) -> Path:
    """Bake a look into a copy of a video (for checking, or when Resolve will not take the LUT)."""
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", _lut_filter(lut),
         "-c:a", "copy", "-pix_fmt", "yuv420p", str(out)])
    return Path(out)


def preview(video: str, lut: str | Path, t: float, out: str | Path, reference: str | None = None,
            ref_t: float = 0.0, width: int = 640) -> Path:
    """One image: before, after, and (when given) a reference frame, left to right."""
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video)]
    graph = (f"[0:v]scale={width}:-2,split[a][b];[b]{_lut_filter(lut)}[c];")
    if reference:
        cmd += ["-ss", f"{ref_t:.3f}", "-i", str(reference)]
        graph += f"[1:v]scale={width}:-2[r];[a][c][r]xstack=inputs=3:layout=0_0|w0_0|w0+w1_0:fill=black[o]"
    else:
        graph += "[a][c]hstack[o]"
    run(cmd + ["-filter_complex", graph, "-map", "[o]", "-frames:v", "1", str(out)])
    return Path(out)


# A typical phone clip shot in a gym, used when no footage of his is given to measure.
PHONE_BASELINE = {"brightness": 0.40, "black_point": 0.03, "white_point": 0.92, "saturation": 0.28,
                  "warmth": 0.03, "green_magenta": 0.0}


def _profile_colour(profile: dict) -> dict:
    """The colour block of a style profile, whichever way it was measured."""
    c = profile.get("colour", profile)
    need = ("brightness", "black_point", "white_point", "saturation", "warmth")
    missing = [k for k in need if k not in c]
    if missing:
        raise EditError(f"the style has no colour measurements ({', '.join(missing)} missing)")
    c = dict(c)
    # Browser-sampled profiles give shadow/highlight colours as RGB; measured ones give tints.
    for name in ("shadow", "highlight"):
        if f"{name}_tint" not in c and f"{name}_rgb" in c:
            rgb = [v / 255 for v in c[f"{name}_rgb"]]
            m = sum(rgb) / 3
            c[f"{name}_tint"] = [v - m for v in rgb]
    c.setdefault("green_magenta", 0.0)
    return c


def lut_from_profile(target: dict, baseline: dict | None = None, strength: float = 0.8, size: int = 17):
    """A 3D LUT (size^3 x 3, red fastest) that moves footage like `baseline` toward `target`.

    Both are colour measurements from style.colour() or a creator profile. Done in steps:
    levels (black and white points), a gamma for overall brightness, saturation around
    luma, white balance (warmth, green-magenta), and a gentle split tone from the shadow
    and highlight tints. strength blends with "no change".
    """
    import numpy as np

    if not 0 <= strength <= 1:
        raise EditError("strength is between 0 and 1")
    t, b = _profile_colour(target), _profile_colour(baseline or PHONE_BASELINE)
    g = np.linspace(0.0, 1.0, size)
    bb, gg, rr = np.meshgrid(g, g, g, indexing="ij")
    rgb = np.stack([rr, gg, bb], axis=-1).reshape(-1, 3)
    w = np.array([0.2126, 0.7152, 0.0722])

    # Levels: baseline black/white map to the target's.
    bi, wi = b["black_point"], max(b["white_point"], b["black_point"] + 0.1)
    bo, wo = t["black_point"], max(t["white_point"], t["black_point"] + 0.1)
    x = np.clip((rgb - bi) / (wi - bi), 0, 1)
    # Gamma that puts the baseline's average brightness where the target's sits.
    mb = np.clip((b["brightness"] - bi) / (wi - bi), 0.05, 0.95)
    mt = np.clip((t["brightness"] - bo) / (wo - bo), 0.05, 0.95)
    gamma = float(np.clip(np.log(mt) / np.log(mb), 0.45, 2.2))
    x = bo + (wo - bo) * x ** gamma
    # Saturation around luma.
    sat = float(np.clip(t["saturation"] / max(b["saturation"], 0.02), 0.2, 1.8))
    luma = (x @ w)[:, None]
    x = luma + (x - luma) * sat
    # White balance, at half the measured difference (part of a scene's warmth is its
    # content: skin, wood, lights) and mostly in the midtones so whites stay clean.
    dw = 0.5 * (t["warmth"] - b["warmth"])
    dgm = 0.5 * (t["green_magenta"] - b["green_magenta"])
    luma = np.clip(x @ w, 0, 1)[:, None]
    x = x + (0.3 + 0.7 * 4 * luma * (1 - luma)) * np.array([dw / 2, dgm, -dw / 2])
    # Split tone: shadow tint in the darks, highlight tint in the brights, gently.
    luma = np.clip(x @ w, 0, 1)[:, None]
    for name, weight in (("shadow", (1 - luma) ** 2), ("highlight", luma ** 2)):
        tint = t.get(f"{name}_tint")
        if tint:
            tint = np.array(tint, dtype=float)
            x = x + 0.35 * weight * (tint - tint.mean())
    x = np.clip(x, 0, 1)
    return rgb + (x - rgb) * strength


def write_cube3d(path: str | Path, table, title: str, size: int) -> Path:
    lines = [f'TITLE "{title}"', f"LUT_3D_SIZE {size}", "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0", ""]
    lines += [f"{r:.5f} {g:.5f} {b:.5f}" for r, g, b in table]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path


def from_profile(name: str, profile: dict, footage: str | None = None, strength: float = 0.8,
                 size: int = 17, base: str | Path = ".") -> Path:
    """Save a look made from a measured style (no reference video needed).

    Without footage it assumes a typical phone clip; with footage it measures his clip first,
    which is more accurate.
    """
    baseline = None
    if footage:
        from .style import colour
        baseline = colour(footage)
    out = path_for(name, base)
    return write_cube3d(out, lut_from_profile(profile, baseline, strength, size), name, size)
