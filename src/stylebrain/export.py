"""Render the edit list to a file ready to post, and check a finished file.

`render` needs only ffmpeg, not Resolve: it plays the main track, lays the
overlays on top, bakes the look in, mixes the sound effects under the voice and
sets the loudness. It is the quick way to a postable file and to something to
watch on a phone. A cut that was polished by hand in Resolve is exported from
Resolve instead; `check` then looks over that file the same way.

`check` reads the file like a platform would: frame shape, length, loudness and
peaks, black or frozen stretches, silence at the start. It also saves a sheet of
frames so the render can be looked at, not only measured.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .edl import EditError, EditList
from .media import has_audio, info, run

LUFS = -14.0          # what Instagram, TikTok and YouTube all play back at, near enough
PEAK = -1.0           # true-peak ceiling in dBTP
BATCH = 24            # main-track clips rendered per ffmpeg run


def _fit(width: int, height: int, fit: str) -> str:
    if fit == "fill":
        return f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1"
    if fit == "fit":
        return (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1")
    raise EditError("fit is 'fill' (crop to cover the frame) or 'fit' (whole picture with bars)")


def _seek(frame: int, fps: float) -> str:
    # A quarter frame early, so rounding can never skip the frame that was asked for.
    return f"{max(frame - 0.25, 0) / fps:.6f}"


def _main_track(edit: EditList, work: Path, width: int, height: int, fit: str) -> list[Path]:
    """The main track as a few high-quality parts, look baked in, sound kept."""
    from .look import _lut_filter
    from .reframe import crop_filter

    look = f",{_lut_filter(edit.look)}" if edit.look else ""
    audio = {s: has_audio(s) for s in edit.sources()}
    parts = []
    for b in range(0, len(edit.segments), BATCH):
        group = edit.segments[b:b + BATCH]
        cmd, chains = ["ffmpeg", "-v", "error", "-y"], []
        for n, seg in enumerate(group):
            secs = seg.duration / edit.fps
            cmd += ["-ss", _seek(seg.src_in, edit.fps), "-t", f"{secs + 1:.4f}", "-i", seg.source]
            chains.append(f"[{n}:v]fps={edit.fps:g},trim=end_frame={seg.duration},setpts=PTS-STARTPTS,"
                          f"{crop_filter(width, height, *seg.framing) if fit == 'fill' else _fit(width, height, fit)}"
                          f"{look},format=yuv420p[v{n}]")
            sound = f"[{n}:a]aresample=48000," if audio[seg.source] else "anullsrc=r=48000:cl=stereo,"
            chains.append(f"{sound}aformat=sample_fmts=fltp:channel_layouts=stereo,apad,"
                          f"atrim=duration={secs:.6f},asetpts=PTS-STARTPTS[a{n}]")
        pairs = "".join(f"[v{n}][a{n}]" for n in range(len(group)))
        chains.append(f"{pairs}concat=n={len(group)}:v=1:a=1[v][a]")
        part = work / f"main{b // BATCH:03d}.mkv"
        run(cmd + ["-filter_complex", ";".join(chains), "-map", "[v]", "-map", "[a]",
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-c:a", "pcm_s16le", str(part)])
        parts.append(part)
    return parts


def _loudness(path: str | Path) -> dict:
    err = run(["ffmpeg", "-v", "info", "-nostats", "-i", str(path), "-vn",
               "-af", "ebur128=peak=true", "-f", "null", "-"], text=True).stderr
    tail = err[err.rfind("Summary:"):] if "Summary:" in err else ""
    loud = re.search(r"I:\s+(-?[0-9.]+) LUFS", tail)
    peak = re.search(r"Peak:\s+(-?[0-9.]+|-inf) dBFS", tail)
    return {"lufs": float(loud.group(1)) if loud else None,
            "peak": float(peak.group(1)) if peak and peak.group(1) != "-inf" else None}


def render(edit: EditList, out: str | Path, width: int = 1080, height: int = 1920, fit: str = "fill",
           lufs: float = LUFS, sounds: bool = True) -> Path:
    """Render the whole edit to one mp4."""
    from . import sfx

    if not edit.segments:
        raise EditError("the edit is empty")
    _fit(width, height, fit)
    for src in {*edit.sources(), *(o.source for o in edit.overlays)}:
        if not Path(src).exists():
            raise EditError(f"cannot find {src}")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    total = edit.duration / edit.fps
    work = Path(tempfile.mkdtemp(prefix="stylebrain-export-"))
    try:
        parts = _main_track(edit, work, width, height, fit)
        listing = work / "parts.txt"
        listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing)]
        chains, last, n = [], "[0:v]", 1
        for o in sorted(edit.overlays, key=lambda o: (o.track, o.at)):
            at, secs = o.at / edit.fps, o.duration / edit.fps
            cmd += ["-ss", _seek(o.src_in, edit.fps), "-t", f"{secs + 1:.4f}", "-i", o.source]
            alpha = info(o.source).has_alpha
            chains.append(f"[{n}:v]fps={edit.fps:g},trim=end_frame={o.duration},{_fit(width, height, 'fill')},"
                          f"format={'yuva420p' if alpha else 'yuv420p'},setpts=PTS-STARTPTS+{at:.6f}/TB[o{n}]")
            chains.append(f"{last}[o{n}]overlay=eof_action=pass:enable='between(t,{at:.6f},{at + secs:.6f})'[x{n}]")
            last, n = f"[x{n}]", n + 1
        chains.append(f"{last}format=yuv420p[v]")

        # First the sound alone, to learn how loud the mix is; then one gain to reach the target.
        mixed = sfx.mix(edit, work / "sfx.wav") if sounds else None
        mix_cmd = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing)]
        graph = "[0:a]anull[m]"
        if mixed:
            mix_cmd += ["-i", str(mixed)]
            graph = "[0:a][1:a]amix=inputs=2:normalize=0:duration=first[m]"
        full = work / "sound.wav"
        run(mix_cmd + ["-filter_complex", graph, "-map", "[m]", "-t", f"{total:.4f}", "-ar", "48000", str(full)])
        measured = _loudness(full)["lufs"]
        gain = 0.0 if measured is None or measured < -60 else lufs - measured
        cmd += ["-i", str(full)]
        limit = 10 ** (PEAK / 20)
        chains.append(f"[{n}:a]volume={gain:.2f}dB,alimiter=limit={limit:.4f}:level=disabled,"
                      f"aresample=48000[a]")
        run(cmd + ["-filter_complex", ";".join(chains), "-map", "[v]", "-map", "[a]", "-t", f"{total:.4f}",
                   "-r", f"{edit.fps:g}", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                   "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                   "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)])
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return out


# ------------------------------------------------------------------ checking

@dataclass
class Check:
    file: str
    facts: dict
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sheet: str = ""

    @property
    def ok(self) -> bool:
        return not self.problems

    def text(self) -> str:
        f = self.facts
        sound = "no sound" if f["lufs"] is None else f"{f['lufs']:g} LUFS, peak {f['peak']:g} dB"
        lines = [f"{Path(self.file).name}: {f['width']}x{f['height']}, {f['fps']:g} fps, {f['seconds']:.1f}s, {sound}"]
        lines += [f"  problem: {p}" for p in self.problems]
        lines += [f"  note: {n}" for n in self.notes]
        if self.sheet:
            lines.append(f"  frames to look at: {self.sheet}")
        lines.append("ready to post" if self.ok else f"{len(self.problems)} thing(s) to fix before posting")
        return "\n".join(lines)


def _spans(err: str, start: str, end: str) -> list[tuple[float, float]]:
    a = [float(x) for x in re.findall(start + r":\s*(-?[0-9.]+)", err)]
    b = [float(x) for x in re.findall(end + r":\s*(-?[0-9.]+)", err)]
    return list(zip(a, b + [float("inf")] * (len(a) - len(b))))


def check(file: str | Path, expect_seconds: float | None = None, width: int = 1080, height: int = 1920,
          lufs: float = LUFS, sheet: str | Path | None = None) -> Check:
    """Look over a rendered file the way a platform, and then a viewer, would."""
    file = str(file)
    i = info(file)
    secs = i.duration
    loud = _loudness(file) if has_audio(file) else {"lufs": None, "peak": None}
    c = Check(file, {"width": i.width, "height": i.height, "fps": round(i.fps, 3), "seconds": round(secs, 2), **loud})

    if (i.width, i.height) != (width, height):
        same_shape = abs(i.width / i.height - width / height) < 0.01
        (c.notes if same_shape and i.width >= width else c.problems).append(
            f"the frame is {i.width}x{i.height}, not {width}x{height}")
    if expect_seconds is not None and abs(secs - expect_seconds) > 2 / i.fps:
        c.problems.append(f"it is {secs:.2f}s long but the edit is {expect_seconds:.2f}s")
    if secs > 180:
        c.notes.append(f"{secs:.0f}s is over the 3 minute limit for Reels and Shorts")
    if not 23.9 <= i.fps <= 60.1:
        c.notes.append(f"{i.fps:g} fps is unusual for a phone feed")

    if loud["lufs"] is None:
        c.problems.append("there is no sound")
    else:
        if abs(loud["lufs"] - lufs) > 1.5:
            way = "quiet" if loud["lufs"] < lufs else "loud"
            c.problems.append(f"too {way}: {loud['lufs']:g} LUFS, aim for {lufs:g}")
        if loud["peak"] is not None and loud["peak"] > PEAK + 0.5:
            c.problems.append(f"peaks reach {loud['peak']:g} dB and may distort after upload (keep under {PEAK:g})")

    filters = "blackdetect=d=0.1:pix_th=0.04,freezedetect=n=0.003:d=2"
    cmd = ["ffmpeg", "-v", "info", "-nostats", "-i", file, "-vf", filters]
    if loud["lufs"] is not None:
        cmd += ["-af", "silencedetect=noise=-45dB:d=0.5"]
    err = run(cmd + ["-f", "null", "-"], text=True).stderr
    for a, b in _spans(err, "black_start", "black_end"):
        b = min(b, secs)
        if a < 0.05:
            c.problems.append(f"it opens on black for {b - a:.2f}s; the first frame is the cover and the hook")
        elif b - a >= 0.2:
            c.problems.append(f"black frames from {a:.2f}s to {b:.2f}s")
    for a, b in _spans(err, "freeze_start", "freeze_end"):
        c.notes.append(f"the picture does not move from {a:.1f}s to {min(b, secs):.1f}s")
    for a, b in _spans(err, "silence_start", "silence_end"):
        if a < 0.05 and min(b, secs) - a >= 0.5:
            c.notes.append(f"silent for the first {min(b, secs) - a:.1f}s")

    if sheet:
        from .reference import contact_sheet
        contact_sheet(file, 0.0, secs, sheet, count=min(24, max(6, int(secs * 2))), columns=6, width=270)
        c.sheet = str(sheet)
    return c
