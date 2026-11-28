"""Trial reels: one finished reel made into five versions, each changing one thing, for Instagram Trial Reels.

A trial reel is shown to non-followers first; followers do not see it unless it is shared to everyone
(by hand, or automatically if it does well in its first 72 hours). That makes it the place to test a
reel before it reaches the main feed: post several versions as trials, read their results side by side,
and share only the winner. Each version is a hypothesis ("the stakes line beats the number as a hook")
and its results score it, the same way `bets` scores the calendar.

What the research said (Nov 2026, see docs/trial-reels.md for sources):
- Change one thing per version and keep the rest identical (caption, hashtags, posting hour), so a
  difference in results points at that one change.
- Instagram's help page warns a trial "may get limited reach if Instagram detects that you've previously
  shared the same content". Creators report text-only and music-only changes are flagged most; a new
  opening shot or spoken line least. So a caption-only version is allowed but warned about, and
  `trial-learn` checks whether later versions of a reel do worse than earlier ones (a duplicate penalty).
- Insights arrive about 24 hours after posting. Compare versions at the same age, trials with trials
  (Mosseri: trials "get less reach, almost always" than normal reels).
- No published cap on trials; creators report about 5 a day is safe. `trial-schedule` warns past that.
- Auto-share is a sticky setting: leave it off (manual), so two strong versions never both reach followers.

The pieces:
- `suggest`: a draft spec for a finished reel (control, hook text, opening, length, pace).
- `make`: renders each version with ffmpeg, labels it, and writes `trial.json`, a sheet of first frames
  and a posting sheet. Nothing is posted.
- `schedule`, `record`, `score`, `promote`, `learn`: when to post each, their results, the winner, and what
  wins across reels.
Versions are posted by Michael in the app, or by `stylebrain trial-publish` (Instagram's API, posted as a
trial with manual graduation) only when he asks.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import re
import shutil
import statistics
import tempfile
from pathlib import Path

from .edl import EditError
from .media import has_audio, info, run

COUNT = 5                     # versions per reel, the control included
DAILY_CAP = 5                 # trials a day before the anecdotal lock-out risk
MIN_VIEWS = 300               # below this a trial's rates are mostly noise
SAME_AGE_HOURS = 12           # versions read further apart in age than this are not compared

KINDS = {
    "control": "the reel as it is",
    "hook_text": "a different on-screen hook over the opening seconds",
    "opening": "starts on a different moment (later start, or a stretch moved to the front)",
    "length": "stretches cut out, so it is shorter",
    "pace": "played faster or slower",
    "audio": "a different sound under it",
    "caption": "only the post caption changes (same video: the most likely to be flagged as a duplicate)",
}
# Each kind's one setting that must be given, and the ones allowed with it.
NEEDS = {"control": (), "hook_text": ("text",), "opening": (), "length": ("cut",), "pace": ("speed",),
         "audio": (), "caption": ("caption",)}
ALLOWED = {"hook_text": {"text", "accent", "seconds", "cover", "y", "size"},
           "opening": {"start", "front", "keep"}, "length": {"cut"}, "pace": {"speed"},
           "audio": {"audio", "song", "voice", "song_start", "song_db"}, "caption": {"caption"}, "control": set()}
COMMON = {"kind", "hypothesis", "tags", "label"}

# What a version is judged on, by the reel's goal. Positive weight: higher is better.
WEIGHTS = {
    "reach": {"skip": -0.3, "watch": 0.3, "shares_k": 0.3, "saves_k": 0.05, "likes_k": 0.05},
    "follows": {"follows_k": 0.35, "saves_k": 0.2, "skip": -0.15, "watch": 0.15, "shares_k": 0.15},
}
MAIN = {"reach": "shares", "follows": "follows"}
NUMBERS = ("views", "reach", "likes", "comments", "shares", "saves", "follows", "skip_rate", "avg_watch", "hours")


class TrialError(EditError):
    pass


def root(base: str | Path = ".") -> Path:
    return Path(base) / "library" / "trials"


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    if not s:
        raise TrialError("give the reel a name with letters or numbers")
    return s[:48]


def _ranges(value) -> list[tuple[float, float]]:
    """[[a, b], ...] or "a-b,c-d" into sorted (a, b) pairs in seconds."""
    if isinstance(value, str):
        value = [part.split("-") for part in value.split(",") if part.strip()]
    if value and not isinstance(value[0], (list, tuple)):
        value = [value]
    out = []
    for pair in value or []:
        if len(pair) != 2:
            raise TrialError(f"a range is two times, start and end: {pair}")
        a, b = float(pair[0]), float(pair[1])
        if b <= a or a < 0:
            raise TrialError(f"the range {a}-{b} is empty or before the start")
        out.append((a, b))
    return sorted(out)


# ---------------------------------------------------------------- the spec

def check_spec(spec: dict, duration: float | None = None) -> list[str]:
    """Problems that stop a render. One change per version, one control, every needed setting."""
    problems = []
    vs = spec.get("variants") or []
    if not spec.get("reel"):
        problems.append("the spec has no reel name")
    if not vs:
        problems.append("the spec has no versions")
    kinds = [v.get("kind") for v in vs]
    if kinds.count("control") != 1:
        problems.append("there must be exactly one control (the reel unchanged) to compare against")
    for n, v in enumerate(vs, 1):
        k = v.get("kind")
        if k not in KINDS:
            problems.append(f"version {n}: unknown kind {k!r}; the kinds are {', '.join(KINDS)}")
            continue
        extra = set(v) - COMMON - ALLOWED[k]
        if extra:
            problems.append(f"version {n} ({k}) changes more than one thing: {', '.join(sorted(extra))} "
                            "belong to another kind; make it its own version")
        for need in NEEDS[k]:
            if v.get(need) in (None, "", []):
                problems.append(f"version {n} ({k}) needs {need}")
        text = " ".join(str(v.get(x, "")) for x in ("text", "caption"))
        if re.search(r"\[[^\]]+\]", text):
            problems.append(f"version {n} ({k}) still has a [placeholder]: fill it in")
        if k == "opening" and not (v.get("start") or v.get("front")):
            problems.append(f"version {n} (opening) needs start (seconds to drop) or front (a stretch to open on)")
        if k == "audio" and not (v.get("audio") or v.get("song")):
            problems.append(f"version {n} (audio) needs audio (a whole new soundtrack) or song (with voice, the "
                            "voice-only stem of the cut)")
        if k == "pace" and v.get("speed") and not 0.5 <= float(v["speed"]) <= 2.0:
            problems.append(f"version {n} (pace): speed {v['speed']} is outside 0.5 to 2")
        if duration and k == "length":
            for a, b in _ranges(v.get("cut")):
                if b > duration + 0.05:
                    problems.append(f"version {n} (length): {a}-{b} runs past the end ({duration:.2f}s)")
        if duration and k == "opening" and v.get("start") and float(v["start"]) >= duration - 1:
            problems.append(f"version {n} (opening): starting at {v['start']}s leaves almost nothing")
    if len(vs) == 1:
        problems.append("one version is not a test: add at least one change next to the control")
    return problems


def suggest(video: str | Path, reel: str, hooks: list[str] | None = None, goal: str = "reach",
            caption: str = "", post: str | None = None, cuts: list[float] | None = None) -> dict:
    """A draft spec: the control, a hook-text version per hook given, then opening, length and pace,
    to five. Read and change it before `make`: the hooks are Michael's call."""
    if goal not in WEIGHTS:
        raise TrialError(f"goal is one of {', '.join(WEIGHTS)}")
    i = info(str(video))
    secs = i.duration
    cuts = shot_changes(video) if cuts is None else cuts
    vs: list[dict] = [{"kind": "control", "hypothesis": "the reel as made: the baseline every other version is read against"}]
    for h in (hooks or [])[:2]:
        vs.append({"kind": "hook_text", "text": h, "seconds": 3.0,
                   "hypothesis": f"\"{h}\" stops more scrollers than the current opening text"})
    first = next((c for c in cuts if 1.0 <= c <= 6.0), None)
    if first:
        first = sharp_start(video, first)
        vs.append({"kind": "opening", "start": round(first, 2),
                   "hypothesis": f"starting on the second shot ({first:.1f}s, story first) beats opening on the first"})
    shots = list(zip([0.0] + cuts, cuts + [secs]))
    longest = max(shots, key=lambda s: s[1] - s[0]) if shots else (0.0, secs)
    span = longest[1] - longest[0]
    if span >= 4.0:
        a, b = longest[0] + span * 0.3, longest[0] + span * 0.65
        vs.append({"kind": "length", "cut": [[round(a, 2), round(b, 2)]],
                   "hypothesis": f"cutting {b - a:.1f}s from the longest shot ({longest[0]:.1f}-{longest[1]:.1f}s) "
                                 "keeps more people to the payoff"})
    vs.append({"kind": "pace", "speed": 1.1, "hypothesis": "10% faster holds attention better (the one pacing hint "
                                                         "the creator study found)"})
    if len(vs) < COUNT:
        vs.append({"kind": "hook_text", "text": "[a second hook line]", "seconds": 3.0, "hypothesis": "[why]"})
    return {"reel": slug(reel), "video": str(video), "goal": goal, "post": post, "caption": caption,
            "variants": vs[:COUNT]}


def sharp_start(video: str | Path, t: float, window: float = 0.8) -> float:
    """The first sharp frame at or after `t`: a cut often lands inside a blurred transition, and a
    blurred first frame is the worst opening there is."""
    try:
        r = run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-t", f"{window:.3f}", "-i", str(video), "-an", "-vf",
                 "scale=270:-2,blurdetect,metadata=print:file=-", "-f", "null", "-"], text=True)
    except EditError:
        return t
    times = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", r.stdout)]
    blur = [float(x) for x in re.findall(r"lavfi\.blur=([0-9.]+)", r.stdout)]
    if len(blur) < 4 or len(times) != len(blur):
        return t
    limit = statistics.median(blur) * 1.2
    early = [n for n, b in enumerate(blur) if b > limit and times[n] < window * 0.75]
    if not early:
        return round(t, 2)
    n = min(early[-1] + 1, len(times) - 1)
    return round(t + times[n] + 0.03, 2)


def shot_changes(video: str | Path, threshold: float = 0.3) -> list[float]:
    """Times of hard cuts, from ffmpeg's scene score on a small copy."""
    try:
        r = run(["ffmpeg", "-v", "error", "-i", str(video), "-an", "-vf",
                 f"scale=160:-2,select='gt(scene,{threshold})',metadata=print:file=-", "-f", "null", "-"],
                text=True)
    except EditError:
        return []
    times = [float(m) for m in re.findall(r"pts_time:([0-9.]+)", r.stdout)]
    out: list[float] = []
    for t in times:
        if not out or t - out[-1] > 0.5:
            out.append(round(t, 2))
    return out


# ---------------------------------------------------------------- rendering

ENCODE = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]


def _hook_card(v: dict, seconds: float, width: int, height: int, fps: float, out: Path) -> Path:
    """The house hook text as a transparent clip (swapped out in tests)."""
    from .looks import house_hook
    from .render import render_html

    lines = [x.strip() for x in str(v["text"]).split("|") if x.strip()]
    kw = {k: v[k] for k in ("y", "size") if k in v}
    html, _ = house_hook(lines, seconds, accent_words=(v.get("accent") or "").split() or None,
                         width=width, height=height, **kw)
    return Path(render_html(html, out, seconds, fps=fps, width=width, height=height).path)


def _keep_complement(cuts: list[tuple[float, float]], end: float) -> list[tuple[float, float]]:
    keep, t = [], 0.0
    for a, b in cuts:
        if a > t:
            keep.append((t, min(a, end)))
        t = max(t, b)
    if t < end:
        keep.append((t, end))
    return [(a, b) for a, b in keep if b - a > 0.04]


def _splice(src: str, keep: list[tuple[float, float]], sound: bool) -> tuple[list[str], str]:
    """Filter graph playing the kept stretches in order, with 20 ms sound fades at every join."""
    parts, labels = [], ""
    for n, (a, b) in enumerate(keep):
        parts.append(f"[0:v]trim=start={a:.4f}:end={b:.4f},setpts=PTS-STARTPTS[v{n}]")
        if sound:
            d = b - a
            parts.append(f"[0:a]atrim=start={a:.4f}:end={b:.4f},asetpts=PTS-STARTPTS,"
                         f"afade=t=in:d=0.02,afade=t=out:st={max(d - 0.02, 0):.4f}:d=0.02[a{n}]")
            labels += f"[v{n}][a{n}]"
        else:
            labels += f"[v{n}]"
    parts.append(f"{labels}concat=n={len(keep)}:v=1:a={1 if sound else 0}[v]" + ("[a]" if sound else ""))
    return parts, "[a]" if sound else ""


def render_version(src: str, v: dict, out: Path, meta: str, work: Path) -> Path:
    i = info(src)
    secs, sound = i.duration, has_audio(src)
    k = v["kind"]
    tag = ["-metadata", f"comment={meta}", "-metadata", f"title={meta}"]
    out.parent.mkdir(parents=True, exist_ok=True)
    if k in ("control", "caption"):
        run(["ffmpeg", "-v", "error", "-y", "-i", src, "-map", "0", "-c", "copy", *tag, str(out)])
        return out
    if k == "hook_text":
        shown = min(float(v.get("seconds", 3.0)), secs)
        card = _hook_card(v, shown, i.width, i.height, i.fps, work / f"{out.stem}.card.mov")
        graph, base = [], "[0:v]"
        if v.get("cover"):
            x, y, w, h = (int(c) for c in v["cover"])
            graph += [f"[0:v]split[m][c]", f"[c]crop={w}:{h}:{x}:{y},gblur=sigma={max(4, min(w, h) // 5)}:steps=4[b]",
                      f"[m][b]overlay={x}:{y}:enable='lt(t,{shown:.3f})'[cv]"]
            base = "[cv]"
        graph.append(f"{base}[1:v]overlay=0:0:eof_action=pass:enable='lt(t,{shown:.3f})',format=yuv420p[v]")
        run(["ffmpeg", "-v", "error", "-y", "-i", src, "-i", str(card), "-filter_complex", ";".join(graph),
             "-map", "[v]", *(["-map", "0:a", "-c:a", "copy"] if sound else []), *ENCODE[:8], *ENCODE[10:],
             *tag, str(out)])
        return out
    if k in ("opening", "length"):
        if k == "length":
            keep = _keep_complement(_ranges(v["cut"]), secs)
        elif v.get("front"):
            (a, b), = _ranges(v["front"])
            keep = [(a, min(b, secs))] + ([(0.0, secs)] if v.get("keep") else _keep_complement([(a, b)], secs))
        else:
            keep = [(float(v["start"]), secs)]
        graph, alabel = _splice(src, keep, sound)
        run(["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex", ";".join(graph), "-map", "[v]",
             *(["-map", alabel] if sound else []), *ENCODE, *tag, str(out)])
        return out
    if k == "pace":
        s = float(v["speed"])
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", src, "-filter:v", f"setpts=PTS/{s}"]
        if sound:
            cmd += ["-filter:a", f"atempo={s}"]
        run(cmd + ["-r", f"{i.fps:g}", *ENCODE, *tag, str(out)])
        return out
    if k == "audio":
        if v.get("song") and v.get("voice"):
            start = float(v.get("song_start", 0))
            db = float(v.get("song_db", -12))
            graph = (f"[2:a]atrim=start={start},asetpts=PTS-STARTPTS,volume={db}dB[s];"
                     f"[1:a]asplit[vk][vm];[s][vk]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=300[d];"
                     f"[vm][d]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1[a]")
            ins = ["-i", src, "-i", str(v["voice"]), "-i", str(v["song"])]
        else:
            start = float(v.get("song_start", 0))
            graph = f"[1:a]atrim=start={start},asetpts=PTS-STARTPTS,loudnorm=I=-14:TP=-1[a]"
            ins = ["-i", src, "-i", str(v["audio"])]
        run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", graph, "-map", "0:v", "-map", "[a]",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{secs:.3f}", "-movflags", "+faststart", *tag, str(out)])
        return out
    raise TrialError(f"unknown kind {k}")


def describe(v: dict) -> str:
    k = v["kind"]
    if k == "control":
        return "nothing (the control)"
    if k == "hook_text":
        return f"hook text \"{v['text'].replace('|', ' / ')}\" for {float(v.get('seconds', 3.0)):g}s"
    if k == "opening":
        if v.get("front"):
            (a, b), = _ranges(v["front"])
            return f"opens on {a:g}-{b:g}s" + (" (repeated later)" if v.get("keep") else " (moved to the front)")
        return f"starts at {float(v['start']):g}s"
    if k == "length":
        return "cuts " + ", ".join(f"{a:g}-{b:g}s" for a, b in _ranges(v["cut"]))
    if k == "pace":
        return f"plays at {float(v['speed']):g}x"
    if k == "audio":
        return f"sound: {Path(v.get('song') or v.get('audio')).name}"
    return "caption only: " + v["caption"][:60]


def first_frames(files: list[Path], labels: list[str], out: Path) -> Path:
    """The opening frame of every version side by side: what a scroller sees first."""
    font = Path(__file__).parent / "fonts" / "Montserrat.ttf"
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for f in files:
        cmd += ["-ss", "0.05", "-i", str(f)]
    chains = []
    for n, lab in enumerate(labels):
        text = lab.replace("\\", "").replace(":", r"\:").replace("'", "")
        chains.append(f"[{n}:v]scale=270:480:force_original_aspect_ratio=decrease,pad=270:480:(ow-iw)/2:(oh-ih)/2,"
                      f"drawtext=fontfile='{font.as_posix()}':text='{text}':x=8:y=h-30:fontsize=18:"
                      f"fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=5[f{n}]")
    stack = "".join(f"[f{n}]" for n in range(len(files)))
    graph = ";".join(chains) + (f";{stack}hstack=inputs={len(files)}[o]" if len(files) > 1 else f";[f0]null[o]")
    run(cmd + ["-filter_complex", graph, "-map", "[o]", "-frames:v", "1", str(out)])
    return out


def make(spec: dict, base: str | Path = ".", check: bool = False, log=print) -> dict:
    """Render every version of a reel into library/trials/REEL/, with trial.json, first frames and a sheet."""
    src = spec.get("video")
    if not src or not Path(src).exists():
        raise TrialError(f"cannot find the reel's video {src or '(none)'}")
    i = info(str(src))
    problems = [p for p in check_spec(spec, i.duration) if p]
    if problems:
        raise TrialError("fix the spec first:\n  " + "\n  ".join(problems))
    reel = slug(spec["reel"])
    folder = root(base) / reel
    old = folder / "trial.json"
    if old.exists() and any(v.get("posted") for v in json.loads(old.read_text())["variants"]):
        raise TrialError(f"{reel} already has posted versions; give the new set another reel name")
    folder.mkdir(parents=True, exist_ok=True)
    goal = spec.get("goal") or "reach"
    record = {"reel": reel, "made": dt.datetime.now().isoformat(timespec="seconds"), "source": str(src),
              "seconds": round(i.duration, 2), "goal": goal, "post": spec.get("post"),
              "caption": spec.get("caption", ""), "variants": [], "winner": None, "promoted": None}
    files, labels = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for n, v in enumerate(spec["variants"], 1):
            vid = f"v{n}"
            name = f"{reel}-{vid}-{v['kind'].replace('_', '-')}"
            out = folder / f"{name}.mp4"
            log(f"  {vid} {v['kind']:<10}{describe(v)}")
            render_version(str(src), v, out, f"trial {reel} {vid} {v['kind']}", Path(tmp))
            got = info(str(out))
            entry = {"id": vid, "kind": v["kind"], "label": name, "change": describe(v),
                     "hypothesis": v.get("hypothesis", ""), "tags": v.get("tags") or {},
                     "settings": {k: v[k] for k in v if k not in COMMON},
                     "file": str(out), "seconds": round(got.duration, 2),
                     "caption": v.get("caption") or record["caption"],
                     "scheduled": None, "posted": None, "url": None, "results": {}}
            if check:
                from .export import check as check_file
                c = check_file(out, expect_seconds=got.duration, width=got.width, height=got.height)
                entry["check"] = c.problems
            record["variants"].append(entry)
            files.append(out)
            labels.append(f"{vid} {v['kind']}")
    first_frames(files, labels, folder / "first-frames.jpg")
    save(record, base)
    (folder / "post-sheet.md").write_text(sheet(record))
    return record


# ---------------------------------------------------------------- records

def path_of(reel: str, base: str | Path = ".") -> Path:
    return root(base) / slug(reel) / "trial.json"


def load(reel: str, base: str | Path = ".") -> dict:
    p = path_of(reel, base)
    if not p.exists():
        raise TrialError(f"no trial set called {reel}: make one with `stylebrain trial-make`")
    return json.loads(p.read_text())


def save(record: dict, base: str | Path = ".") -> Path:
    p = path_of(record["reel"], base)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record, indent=2) + "\n")
    return p


def all_trials(base: str | Path = ".") -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(root(base).glob("*/trial.json"))]


def version(record: dict, vid: str) -> dict:
    vid = vid if vid.startswith("v") else f"v{vid}"
    for v in record["variants"]:
        if v["id"] == vid:
            return v
    raise TrialError(f"{record['reel']} has no version {vid} (it has {', '.join(v['id'] for v in record['variants'])})")


def _parse_when(text: str | dt.datetime) -> dt.datetime:
    if isinstance(text, dt.datetime):
        return text
    try:
        return dt.datetime.fromisoformat(str(text).replace(" ", "T"))
    except ValueError:
        raise TrialError(f"times look like 2026-11-29 18:00, not {text!r}") from None


def schedule(record: dict, *, start: str | dt.datetime | None = None, share_on: str | None = None,
             at: str = "18:00", gap_hours: float = 24, base: str | Path = ".") -> list[str]:
    """When to post each version: the same clock time, `gap_hours` apart. With `share_on` (the day the
    winner should reach the main feed) the trials end two days before it, so the last one has its 24
    hours of insights. Returns warnings (days over the cap)."""
    n = len(record["variants"])
    if share_on:
        day = dt.date.fromisoformat(str(share_on))
        hh, mm = (int(x) for x in at.split(":"))
        last = dt.datetime.combine(day, dt.time(hh, mm)) - dt.timedelta(hours=max(gap_hours, 24) + 24)
        first = last - dt.timedelta(hours=gap_hours * (n - 1))
    elif start:
        first = _parse_when(start)
    else:
        raise TrialError("say when: --start '2026-11-29 18:00' or --share-on 2026-12-05")
    for k, v in enumerate(record["variants"]):
        v["scheduled"] = (first + dt.timedelta(hours=gap_hours * k)).isoformat(timespec="minutes")
    if share_on:
        record["share_on"] = str(share_on)
    days: dict[str, list[str]] = {}
    for t in all_trials(base) + [record]:
        if t["reel"] == record["reel"] and t is not record:
            continue
        for v in t["variants"]:
            if v.get("scheduled"):
                days.setdefault(v["scheduled"][:10], []).append(f"{t['reel']} {v['id']}")
    return [f"{d}: {len(x)} trials planned (more than {DAILY_CAP} a day has cost creators the feature for a day)"
            for d, x in sorted(days.items()) if len(x) > DAILY_CAP]


def record_result(record: dict, vid: str, *, url: str | None = None, posted: str | None = None, **numbers) -> dict:
    v = version(record, vid)
    if url:
        v["url"] = url
        v["posted"] = v.get("posted") or posted or dt.datetime.now().isoformat(timespec="minutes")
    elif posted:
        v["posted"] = posted
    for k, val in numbers.items():
        if val is None:
            continue
        if k not in NUMBERS:
            raise TrialError(f"unknown number {k}; known: {', '.join(NUMBERS)}")
        if k == "skip_rate" and not 0 <= float(val) <= 100:
            raise TrialError("skip rate is a percent, 0 to 100")
        v["results"][k] = float(val)
    return v


# ---------------------------------------------------------------- scoring

def metrics(v: dict) -> dict:
    r = v.get("results") or {}
    base = r.get("reach") or r.get("views")
    m: dict = {}
    if base:
        for k in ("shares", "saves", "follows", "likes", "comments"):
            if k in r:
                m[f"{k}_k"] = 1000.0 * r[k] / base
    if "skip_rate" in r:
        m["skip"] = r["skip_rate"] / 100.0
    if "avg_watch" in r and v.get("seconds"):
        m["watch"] = r["avg_watch"] / v["seconds"]
    return m


def _ztest(x1: float, n1: float, x2: float, n2: float) -> float:
    """Two-proportion z: positive when the first rate is higher."""
    if n1 <= 0 or n2 <= 0:
        return 0.0
    p = (x1 + x2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2)) if 0 < p < 1 else 0.0
    return 0.0 if se == 0 else (x1 / n1 - x2 / n2) / se


def score(record: dict, min_views: int = MIN_VIEWS) -> dict:
    """Each version's index (weighted z across versions), lift on the control, the winner and how sure."""
    goal = record.get("goal") or "reach"
    weights = WEIGHTS[goal]
    vs = record["variants"]
    have = [v for v in vs if v.get("results")]
    rows = {v["id"]: metrics(v) for v in have}
    index = {v["id"]: 0.0 for v in have}
    used = 0.0
    for key, w in weights.items():
        vals = [rows[i][key] for i in rows if key in rows[i]]
        if len(vals) < 2 or len(vals) != len(rows):
            continue
        sd = statistics.pstdev(vals)
        if sd == 0:
            continue
        mu = statistics.fmean(vals)
        for i in rows:
            index[i] += w * (rows[i][key] - mu) / sd
        used += abs(w)
    if used:
        index = {i: round(x / used, 3) for i, x in index.items()}
    control = next((v for v in vs if v["kind"] == "control"), None)
    lift = {}
    if control and control["id"] in rows:
        c = rows[control["id"]]
        for i, m in rows.items():
            lift[i] = {k: (round(m[k] - c[k], 4) if k == "skip" else round(m[k] / c[k], 2) if c[k] else None)
                       for k in m if k in c}
    waiting = []
    for v in vs:
        r = v.get("results") or {}
        if not v.get("posted") and not r:
            waiting.append(f"{v['id']} not posted yet")
        elif not r:
            waiting.append(f"{v['id']} has no results yet")
        elif (r.get("views") or 0) < min_views:
            waiting.append(f"{v['id']} has {int(r.get('views') or 0)} views (under {min_views})")
    ages = [v["results"]["hours"] for v in have if "hours" in v["results"]]
    if ages and max(ages) - min(ages) > SAME_AGE_HOURS:
        waiting.append(f"results were read at ages {min(ages):g}h to {max(ages):g}h; read them all at the same age")
    out = {"reel": record["reel"], "goal": goal, "index": index, "lift": lift, "metrics": rows,
           "winner": None, "confidence": "too early", "why": waiting}
    if not index or len(index) < 2:
        out["why"] = waiting or ["fewer than two versions have results"]
        return out
    order = sorted(index, key=index.get, reverse=True)
    best, second = order[0], order[1]
    out["winner"] = best
    if waiting:
        return out
    main = MAIN[goal]
    rb, rs = version(record, best)["results"], version(record, second)["results"]
    nb, ns = rb.get("reach") or rb.get("views"), rs.get("reach") or rs.get("views")
    tests = {}
    if main in rb and main in rs:
        tests[main] = _ztest(rb[main], nb, rs[main], ns)
    if "skip_rate" in rb and "skip_rate" in rs:
        tests["skip"] = -_ztest(rb["skip_rate"] / 100 * rb["views"], rb["views"],
                                rs["skip_rate"] / 100 * rs["views"], rs["views"])
    out["tests"] = {k: round(z, 2) for k, z in tests.items()}
    if any(z >= 1.96 for z in tests.values()) and not any(z <= -1.96 for z in tests.values()):
        out["confidence"] = "clear"
        out["why"] = [f"{best} beats {second} beyond chance on " + ", ".join(k for k, z in tests.items() if z >= 1.96)]
    else:
        out["confidence"] = "lean"
        out["why"] = [f"{best} leads {second}, but within what chance gives at these view counts"]
    return out


def promote(record: dict, vid: str) -> dict:
    """Record that he shared this version to everyone (done in the app: the trial's 'Share to everyone')."""
    v = version(record, vid)
    if not v.get("posted"):
        raise TrialError(f"{v['id']} was never posted as a trial")
    record["promoted"] = v["id"]
    record["promoted_at"] = dt.datetime.now().isoformat(timespec="minutes")
    s = score(record)
    record["winner"] = s["winner"]
    record["winner_confidence"] = s["confidence"]
    return v


def learn(trials: list[dict]) -> dict:
    """Across every reel tested: how often each kind of change beat its control, by how much, and whether
    versions posted later did worse (the duplicate penalty)."""
    by_kind: dict[str, dict] = {}
    by_tag: dict[str, dict] = {}
    by_pos: dict[int, list[float]] = {}
    tested = 0
    for t in trials:
        s = score(t, min_views=0)
        if s["confidence"] == "too early" and not s["index"]:
            continue
        idx = s["index"]
        control = next((v for v in t["variants"] if v["kind"] == "control"), None)
        if not control or control["id"] not in idx:
            continue
        tested += 1
        posted = sorted((v for v in t["variants"] if v["id"] in idx),
                        key=lambda v: v.get("posted") or v.get("scheduled") or v["id"])
        for pos, v in enumerate(posted, 1):
            by_pos.setdefault(pos, []).append(idx[v["id"]])
        for v in t["variants"]:
            if v["kind"] == "control" or v["id"] not in idx:
                continue
            diff = idx[v["id"]] - idx[control["id"]]
            for bucket, key in [(by_kind, v["kind"])] + [(by_tag, f"{k}={val}") for k, val in (v.get("tags") or {}).items()]:
                b = bucket.setdefault(key, {"tests": 0, "beat_control": 0, "won": 0, "diffs": []})
                b["tests"] += 1
                b["beat_control"] += diff > 0
                b["won"] += s["winner"] == v["id"]
                b["diffs"].append(diff)
    def tidy(d):
        return {k: {"tests": b["tests"], "beat_control": b["beat_control"], "won": b["won"],
                    "mean_gain": round(statistics.fmean(b["diffs"]), 3)} for k, b in sorted(d.items())}
    return {"reels": tested, "kinds": tidy(by_kind), "tags": tidy(by_tag),
            "by_position": {p: round(statistics.fmean(x), 3) for p, x in sorted(by_pos.items())}}


# ---------------------------------------------------------------- what he reads

def sheet(record: dict) -> str:
    lines = [f"# Trial reels: {record['reel']}", "",
             f"Goal: **{record['goal']}**. Five versions, each changing one thing from the control (v1).",
             "Post each as a **trial** in Instagram (Create reel, turn on Trial). Nothing here has been posted.", "",
             "Before the first one: in Trial settings, turn **off** \"Share to everyone automatically\" "
             "(the setting carries over to later trials). Keep the caption, hashtags and hour the same for all "
             "five unless the version says otherwise.", "",
             "| Version | Post at | What changed | Hypothesis | File |", "|---|---|---|---|---|"]
    for v in record["variants"]:
        lines.append(f"| {v['id']} {v['kind']} | {v.get('scheduled') or 'not scheduled'} | {v['change']} | "
                     f"{v.get('hypothesis') or ''} | `{Path(v['file']).name}` |")
    lines += ["", "Caption (all versions unless one says otherwise):", "", "```", record.get("caption") or "(none yet)",
              "```", "", "After posting each one, keep its link:",
              f"`stylebrain trial-result {record['reel']} v2 --url https://www.instagram.com/reel/...`", "",
              "About 24 hours after the last one, read every version at the same age (Trial insights: views, "
              "accounts reached, skip rate, average watch time, shares, saves, follows) and add them:",
              f"`stylebrain trial-result {record['reel']} v2 --hours 24 --views 1200 --reach 1100 --skip-rate 41 "
              "--avg-watch 9.5 --shares 14 --saves 6 --follows 3`", "",
              f"Then `stylebrain trial-score {record['reel']}` names the winner. Share only the winner to everyone "
              "(open it, Share to everyone), and record it with "
              f"`stylebrain trial-promote {record['reel']} vN`. Leave the others as trials.", ""]
    if any(v["kind"] == "caption" for v in record["variants"]):
        lines += ["Note: the caption-only version is the same video. Instagram may give it limited reach as "
                  "previously shared content; its result says as much about that as about the caption.", ""]
    return "\n".join(lines)


def format_score(s: dict, record: dict) -> str:
    lines = [f"{s['reel']} (goal {s['goal']}):"]
    for v in record["variants"]:
        i = v["id"]
        m = s["metrics"].get(i, {})
        bits = []
        if "skip" in m:
            bits.append(f"skip {m['skip'] * 100:.0f}%")
        if "watch" in m:
            bits.append(f"watched {m['watch'] * 100:.0f}%")
        for k in ("shares_k", "saves_k", "follows_k"):
            if k in m:
                bits.append(f"{k[:-2]} {m[k]:.1f}/1k")
        idx = s["index"].get(i)
        mark = "  <- winner" if s["winner"] == i else ""
        lines.append(f"  {i} {v['kind']:<10}{'' if idx is None else f'{idx:+.2f}':>7}  {', '.join(bits) or 'no results'}{mark}")
    lines.append(f"confidence: {s['confidence']}")
    lines += [f"  {w}" for w in s["why"]]
    if s["winner"] and s["confidence"] != "too early":
        lines.append(f"next: share {s['winner']} to everyone in the app, then `stylebrain trial-promote {s['reel']} {s['winner']}`")
    return "\n".join(lines)


def format_learn(r: dict) -> str:
    if not r["reels"]:
        return "no reel has results for its control and a change yet"
    lines = [f"{r['reels']} reels tested. Each kind of change against its control (gain = index difference):"]
    for k, b in r["kinds"].items():
        lines.append(f"  {k:<10} {b['beat_control']}/{b['tests']} beat the control, won {b['won']}, mean gain {b['mean_gain']:+.2f}")
    if r["tags"]:
        lines.append("By tag:")
        for k, b in r["tags"].items():
            lines.append(f"  {k:<24} {b['beat_control']}/{b['tests']} beat the control, mean gain {b['mean_gain']:+.2f}")
    lines.append("By posting order (a steady fall suggests Instagram holds back later near-copies):")
    lines.append("  " + ", ".join(f"#{p}: {x:+.2f}" for p, x in r["by_position"].items()))
    if r["reels"] < 5:
        lines.append("Fewer than 5 reels: read these as hints, not rules.")
    return "\n".join(lines)


def copy_to(record: dict, folder: str | Path) -> list[Path]:
    """Copy the versions and the sheet somewhere he can reach from his phone (e.g. the Drive finals folder)."""
    d = Path(folder) / record["reel"]
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for v in record["variants"]:
        out.append(Path(shutil.copy2(v["file"], d / Path(v["file"]).name)))
    src = Path(record["variants"][0]["file"]).parent
    for extra in ("post-sheet.md", "first-frames.jpg"):
        if (src / extra).exists():
            out.append(Path(shutil.copy2(src / extra, d / extra)))
    return out
