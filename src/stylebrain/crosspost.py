"""The cross-poster: one finished reel in, a ready-to-post version for each platform out.

It prepares posts only. Nothing here uploads or posts anything: Michael posts
each version himself, then records it with `post-result POST --platform NAME`.

For each platform a post goes to, it writes:

- the words that go with the video, fitted to that app: a caption for Instagram
  and TikTok, a title and description for YouTube Shorts, and a title,
  description, chapters and tags for YouTube long-form;
- hashtags in the number that app rewards (Instagram allows five);
- the call to action in that app's terms (Shorts links are not clickable, so a
  coaching ask there points to the channel page, not a link);
- checks against the app's limits: length of the video, frame shape, caption
  length, hashtag count, unfilled `[placeholders]`, and the house rule that
  nothing mentions worlds.

The drafts are a starting point built from the plan's idea (title, hook, pillar,
series, call to action) and, when given, the transcript. Claude rewrites them in
Michael's voice before he sees them, the same as carousel text.

Platform facts were checked on 2026-11-27: Instagram limits a post to 5
hashtags (since December 2025) and a caption to 2,200 characters; TikTok
captions run to 4,000; Shorts run to 3 minutes and YouTube ignores every
hashtag on a video that has more than 15; YouTube titles stop at 100
characters and tags at 500 in total.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .edl import EditError
from .transcript import Word

# What each app allows, and what reads best there.
PLATFORMS = {
    "instagram": {
        "name": "Instagram Reels", "frame": (1080, 1920), "max_seconds": 180,
        "caption_max": 2200, "hashtags": 5, "hashtags_max": 5, "visible": 125,
        "notes": ["Upload the clean export, never a file saved from TikTok: Instagram holds back watermarked reels.",
                  "Pick the cover from the social package, and check it in the 3:4 profile-grid crop.",
                  "Trending audio can be added in the app under the voice, at a low level."],
    },
    "tiktok": {
        "name": "TikTok", "frame": (1080, 1920), "max_seconds": 600,
        "caption_max": 4000, "hashtags": 4, "hashtags_max": 10, "visible": 100,
        "notes": ["TikTok is searched like a search engine: keep the plain-words line in the caption.",
                  "A link in bio needs a business account or 1,000 followers; until then point to Instagram.",
                  "Trending audio can be added in the app under the voice, at a low level."],
    },
    "youtube-shorts": {
        "name": "YouTube Shorts", "frame": (1080, 1920), "max_seconds": 180,
        "title_max": 100, "title_good": 60, "description_max": 5000, "hashtags": 3, "hashtags_max": 15,
        "notes": ["Links in Shorts descriptions are not clickable. To send people to a long video, use "
                  "'Related video' in YouTube Studio.",
                  "The first three hashtags show above the title."],
    },
    "youtube": {
        "name": "YouTube", "frame": (1920, 1080), "max_seconds": None,
        "title_max": 100, "title_good": 70, "description_max": 5000, "hashtags": 3, "hashtags_max": 15,
        "tags_max": 500,
        "notes": ["Thumbnail: 1280x720, from `stylebrain social covers --thumbnail`.",
                  "Chapters need the first at 0:00, at least three, each 10 seconds or longer.",
                  "Add an end screen pointing to the next video in the series."],
    },
}

# Words that pick the most specific tags first. Order matters: first match wins a slot.
TOPICS = [
    (("bench",), ["benchpress", "bench"]),
    (("squat",), ["squat", "squats"]),
    (("deadlift", "pull from the floor"), ["deadlift", "deadlifts"]),
    (("meet", "opener", "platform"), ["powerliftingmeet"]),
    (("run", "mile", "5k", "10k", "marathon", "pace", "track"), ["running", "runner"]),
    (("eat", "meal", "protein", "calories", "food"), ["whatieatinaday", "highprotein"]),
    (("army", "soldier", "military"), ["armylife"]),
    (("drone", "fpv"), ["fpv", "fpvdrone"]),
    (("lock", "pick"), ["lockpicking"]),
    (("range", "rifle", "pistol", "shooting"), ["shooting"]),
]
PILLAR_TAGS = {
    "strength": ["powerlifting", "strengthtraining", "powerlifter", "gym"],
    "run": ["powerlifter", "running", "strengthandconditioning", "fitness"],
    "humour": ["gymhumor", "powerliftinghumor", "gymmemes", "powerlifting"],
    "life": ["powerlifter", "strength", "fitness"],
}
# Plain words for TikTok search and the first line of a YouTube description.
PILLAR_WORDS = {
    "strength": "powerlifting tips",
    "run": "powerlifter running",
    "humour": "powerlifting humor",
    "life": "powerlifter life",
}

PLACEHOLDER = re.compile(r"\[[^\]\n]{1,40}\]")
NEVER = [(re.compile(r"\bworlds?\b", re.IGNORECASE), "mentions worlds; keep competing at worlds out of posts for now")]


def slug(text: str, n: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:n].strip("-") or "post"


def _first(text: str | None) -> str:
    return (text or "").strip()


def _tag(t: str) -> str:
    return "#" + re.sub(r"[^A-Za-z0-9_]", "", t)


def hashtags(idea: dict, text: str = "", extra: list[str] | None = None, series_name: str | None = None) -> list[str]:
    """Most specific first: the lift or topic, the series, then the pillar, then his own tags."""
    words = " ".join([idea.get("title") or "", idea.get("hook") or "", text]).lower()
    out: list[str] = []
    for keys, tags in TOPICS:
        if any(re.search(r"\b" + re.escape(k), words) for k in keys):
            out += tags[:1]
    if series_name:
        out.append(re.sub(r"[^a-z0-9]", "", series_name.lower()))
    out += PILLAR_TAGS.get(idea.get("pillar") or "", ["fitness"])
    out += [t.lstrip("#") for t in extra or []]
    seen, clean = set(), []
    for t in out:
        k = t.lower()
        if k and k not in seen:
            seen.add(k)
            clean.append(_tag(t))
    return clean


def cta_line(cta: str, platform: str, idea: dict, brand: dict, series_name: str | None = None) -> str:
    """The ask, in the terms of each app. 'none' is a planned choice: no ask at all."""
    site = (brand.get("site") or "").strip()
    yt = platform in ("youtube", "youtube-shorts")
    follow = "Subscribe" if yt else "Follow"
    pillar = idea.get("pillar")
    friend = {"run": "the runner in your life", "humour": "the friend this is about"}.get(pillar, "your training partner")
    if cta == "none":
        return ""
    if cta == "follow":
        if series_name and idea.get("episode"):
            return f"{follow} for episode {idea['episode'] + 1} of \"{series_name}\"."
        return f"{follow} for more."
    if cta == "comment":
        return "What would you add? Tell me in the comments."
    if cta == "send":
        return f"Send this to {friend}."
    if cta == "save":
        return "Save this for your next session." if not yt else "Keep this for your next session: save it to a playlist."
    if cta == "coaching":
        if platform == "youtube":
            return f"Want a plan built for you? Coaching: {site}" if site else "Want a plan built for you? Coaching link below."
        if platform == "youtube-shorts":
            return "Want a plan built for you? Coaching link on my channel page."
        return "Want a plan built for you? Coaching link in bio."
    if cta == "long-form":
        if platform == "youtube-shorts":
            return "Full video linked above."
        if platform == "youtube":
            return ""
        return "Full video on my YouTube."
    raise EditError(f"unknown call to action {cta!r}")


def _sentences(words: list[Word] | None) -> list:
    if not words:
        return []
    from .story import sentences
    return sentences(words)


def summary(words: list[Word] | None, hook: str, n: int = 2) -> list[str]:
    """The first spoken lines after the hook, as a draft of the caption's middle (to be rewritten)."""
    hook_l = hook.lower().strip(" .!?")
    out = []
    for s in _sentences(words):
        t = s.text.strip()
        if not t or (hook_l and t.lower().strip(" .!?") in hook_l) or s.words < 4:
            continue
        out.append(t[0].upper() + t[1:])
        if len(out) == n:
            break
    return out


def _clock(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t // 60 % 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


def chapters(words: list[Word] | None, duration: float | None = None, min_len: float = 10.0,
             target: float = 60.0) -> list[dict]:
    """Draft chapters from the transcript: start at 0:00, at least 10 s each, about one a minute.

    The labels are the first words of each chapter, to be rewritten into real names.
    Returns none when there is not enough for three chapters (YouTube needs three)."""
    sents = _sentences(words)
    if not sents:
        return []
    end = duration or sents[-1].end
    starts = [0.0]
    for s in sents[1:]:
        if s.start - starts[-1] >= target and end - s.start >= min_len:
            starts.append(s.start)
    if len(starts) < 3:
        return []
    out = []
    for i, a in enumerate(starts):
        first = next((s for s in sents if s.start >= a - 0.01), sents[0])
        label = " ".join(first.text.split()[:6]).rstrip(",.;:!?")
        out.append({"at": _clock(a), "seconds": round(a, 2), "label": label[0].upper() + label[1:] if label else f"Part {i + 1}"})
    return out


def youtube_tags(idea: dict, tags: list[str], max_chars: int = 500) -> list[str]:
    """Search words for YouTube's tags box: the topic tags spelled out, then the pillar words."""
    out, seen = [], set()
    cand = [idea.get("title") or ""] + [t.lstrip("#") for t in tags] + [PILLAR_WORDS.get(idea.get("pillar") or "", "")]
    for c in cand:
        c = re.sub(r"\s+", " ", re.sub(r"[^\w\s'-]", "", c)).strip().lower()
        if c and c not in seen and len(", ".join(out + [c])) <= max_chars:
            seen.add(c)
            out.append(c)
    return out


def _fit_title(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0]
    return cut.rstrip(",;:-") + "…"


@dataclass
class Version:
    platform: str
    name: str
    text: dict                  # caption | title, description, chapters, tags
    hashtags: list[str]
    cta: str
    video: str | None
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"platform": self.platform, "name": self.name, **self.text, "hashtags": self.hashtags,
                "cta": self.cta, "video": self.video, "problems": self.problems, "notes": self.notes}

    def paste(self) -> str:
        """What he copies into the app, in the order the app asks for it."""
        t = self.text
        lines = [f"{self.name}", "=" * len(self.name)]
        if self.video:
            lines += [f"Video: {self.video}", ""]
        if "title" in t:
            lines += ["TITLE", t["title"], "", "DESCRIPTION", t["description"], ""]
            if t.get("tags"):
                lines += ["TAGS", ", ".join(t["tags"]), ""]
        else:
            lines += ["CAPTION", t["caption"], ""]
        for p in self.problems:
            lines.append(f"FIX BEFORE POSTING: {p}")
        for n in self.notes:
            lines.append(f"note: {n}")
        return "\n".join(lines).rstrip() + "\n"


def _check_words(v: Version, everything: str) -> None:
    for ph in sorted(set(PLACEHOLDER.findall(everything))):
        v.problems.append(f"fill in {ph} with the real figure")
    for rx, why in NEVER:
        if rx.search(everything):
            v.problems.append(why)


def _check_video(v: Version, spec: dict, facts: dict | None) -> None:
    if not facts:
        if v.video:
            v.notes.append("could not read the video to check it")
        else:
            v.problems.append("no video yet: export the cut, then run this again with --video")
        return
    w, h = spec["frame"]
    fw, fh, secs = facts["width"], facts["height"], facts["seconds"]
    if (fw > fh) != (w > h):
        shape = "vertical" if fh > fw else "wide"
        v.problems.append(f"the video is {shape} ({fw}x{fh}); {v.name} wants {w}x{h}"
                          + (": export again with --size 1920x1080" if w > h else ": export again with --size 1080x1920"))
    elif min(fw, fh) < min(w, h):
        v.notes.append(f"the video is {fw}x{fh}, below {w}x{h}; it will look soft")
    if spec.get("max_seconds") and secs > spec["max_seconds"] + 0.5:
        v.problems.append(f"{secs:.0f}s is over {v.name}'s {spec['max_seconds'] // 60} minute limit")


def video_facts(path: str | Path | None) -> dict | None:
    if not path:
        return None
    try:
        from .media import info
        i = info(str(path))
    except Exception:  # noqa: BLE001  ffprobe missing or the file unreadable: report, do not stop
        return None
    return {"width": i.width, "height": i.height, "seconds": round(i.duration, 2), "fps": round(i.fps, 3)}


def build(idea: dict, platforms: list[str], cta: str, *, words: list[Word] | None = None,
          video: str | None = None, long_video: str | None = None, brand: dict | None = None,
          series_name: str | None = None, facts: dict | None = None, long_facts: dict | None = None,
          duration: float | None = None) -> list[Version]:
    """The text and checks for each platform. Pure: reads no files, so it is easy to test."""
    brand = brand or {}
    hook = _first(idea.get("hook")) or _first(idea.get("title"))
    spoken = " ".join(w.text for w in words or [])
    tags_all = hashtags(idea, spoken, brand.get("hashtags"), series_name)
    middle = summary(words, hook)
    out = []
    for p in platforms:
        if p not in PLATFORMS:
            raise EditError(f"unknown platform {p!r} (platforms: {', '.join(PLATFORMS)})")
        spec = PLATFORMS[p]
        ask = cta_line(cta, p, idea, brand, series_name)
        tags = tags_all[: spec["hashtags"]]
        vid, vf = (long_video, long_facts) if p == "youtube" else (video, facts)
        if p in ("instagram", "tiktok"):
            body = [hook]
            if p == "instagram" and middle:
                body += ["", " ".join(middle)]
            if p == "tiktok":
                body += ["", PILLAR_WORDS.get(idea.get("pillar") or "", "")]
            if ask:
                body += ["", ask]
            body += ["", " ".join(tags)]
            text = {"caption": "\n".join(x for x in body if x is not None).strip()}
        else:
            title = _fit_title(idea.get("title") or hook, spec["title_max"])
            desc = [hook if hook != title else ""]
            if middle:
                desc.append(" ".join(middle))
            if ask:
                desc.append(ask)
            chaps = chapters(words, duration) if p == "youtube" else []
            if chaps:
                desc.append("\n".join(f"{c['at']} {c['label']}" for c in chaps))
            desc.append(" ".join(tags))
            text = {"title": title, "description": "\n\n".join(d for d in desc if d).strip()}
            if p == "youtube":
                text["chapters"] = chaps
                text["tags"] = youtube_tags(idea, tags_all, spec["tags_max"])
        v = Version(p, spec["name"], text, tags, cta, vid, notes=list(spec["notes"]))
        everything = "\n".join(str(x) for x in text.values())
        _check_words(v, everything)
        _check_video(v, spec, vf)
        if "caption" in text:
            if len(text["caption"]) > spec["caption_max"]:
                v.problems.append(f"caption is {len(text['caption'])} characters; {v.name} allows {spec['caption_max']}")
            if len(hook) > spec["visible"]:
                v.notes.append(f"the hook line is {len(hook)} characters; only about {spec['visible']} show before 'more'")
        else:
            if len(text["title"]) > spec["title_good"]:
                v.notes.append(f"the title is {len(text['title'])} characters; about {spec['title_good']} show in search")
            if len(text["description"]) > spec["description_max"]:
                v.problems.append(f"description is over {spec['description_max']} characters")
            if p == "youtube" and not text["chapters"]:
                v.notes.append("no chapters: add a transcript (--transcript) or write them by hand")
        if cta == "coaching" and p == "youtube" and not (brand.get("site") or "").strip():
            v.problems.append("no coaching link: put the site in library/social/brand.json")
        if len(tags) > spec["hashtags_max"]:
            v.problems.append(f"{len(tags)} hashtags; {v.name} allows {spec['hashtags_max']}")
        out.append(v)
    return out


def make(plan, post_id: str, *, video: str | None = None, long_video: str | None = None,
         transcript: str | None = None, out_dir: str | Path | None = None, base: str | Path = ".",
         attach: bool = True) -> dict:
    """Write the cross-post package for one calendar post, and note it on the post.

    The video defaults to the idea's draft (the cut file), and the transcript to a
    .json, .srt or .vtt next to it with the same name."""
    from .social import brand as load_brand
    from .transcript import load_words

    post = plan.post(post_id)
    idea = plan.idea(post["idea"])
    video = video or idea.get("draft")
    platforms = list(post["platforms"])
    vertical = [p for p in platforms if p != "youtube"]
    if "youtube" in platforms and not long_video:
        long_video = video if idea.get("format") == "long-form" or not vertical else None
    if transcript is None and video:
        for ext in (".words.json", ".json", ".srt", ".vtt"):
            cand = Path(video).with_suffix(ext)
            if cand.exists() and cand.resolve() != Path(video).resolve():
                transcript = str(cand)
                break
    words = load_words(transcript) if transcript else None
    series_name = plan.data["series"].get(idea.get("series") or "", {}).get("name")
    facts = video_facts(video) if vertical else None
    long_facts = video_facts(long_video) if "youtube" in platforms else None
    duration = (long_facts or facts or {}).get("seconds")
    versions = build(idea, platforms, post["cta"], words=words, video=video if vertical else None,
                     long_video=long_video, brand=load_brand(base), series_name=series_name,
                     facts=facts, long_facts=long_facts, duration=duration)

    out = Path(out_dir) if out_dir else Path(base) / "library" / "crosspost" / f"{post['id']}-{slug(idea['title'])}"
    out.mkdir(parents=True, exist_ok=True)
    for v in versions:
        (out / f"{v.platform}.txt").write_text(v.paste())
    result = {"post": post["id"], "idea": idea["id"], "title": idea["title"], "date": post["date"],
              "cta": post["cta"], "transcript": transcript, "made": dt.date.today().isoformat(),
              "versions": [v.to_dict() for v in versions]}
    (out / "crosspost.json").write_text(json.dumps(result, indent=2) + "\n")
    if attach:
        post["crosspost"] = str(out)
    result["dir"] = str(out)
    return result


def week(plan, monday, *, make_missing: bool = False, base: str | Path = ".") -> list[dict]:
    """Every reel and long video in a week, with whether its cross-posts are ready.

    With make_missing, builds the package for each post whose idea has a cut (draft) and no package yet."""
    from .content import monday_of, parse_date

    monday = monday_of(parse_date(monday))
    rows = []
    for r in plan.rows(monday, 7):
        if r["format"] not in ("reel", "long-form"):
            continue
        post = plan.post(r["post"])
        made = None
        if make_missing and r["draft"] and not post.get("crosspost") and r["post_status"] != "proposed":
            made = make(plan, r["post"], base=base)
        folder = post.get("crosspost")
        problems: list[str] = []
        if folder and Path(folder, "crosspost.json").exists():
            data = json.loads(Path(folder, "crosspost.json").read_text())
            problems = [f"{v['platform']}: {p}" for v in data["versions"] for p in v["problems"]]
            state = "ready" if not problems else "needs fixes"
        elif folder:
            state = "missing"  # the folder was moved or deleted
        elif r["post_status"] == "proposed":
            state = "not approved"
        elif r["draft"]:
            state = "cut, not prepared"
        else:
            state = "waiting for the cut"
        posted = post.get("urls") or {}
        rows.append({"post": r["post"], "date": r["date"], "day": r["day"], "title": r["title"],
                     "platforms": r["platforms"], "state": state, "dir": folder, "problems": problems,
                     "posted": sorted(posted), "made": bool(made)})
    return rows


def format_week(rows: list[dict]) -> str:
    if not rows:
        return "no reels or long videos this week"
    lines = []
    for r in rows:
        done = f"  posted on {', '.join(r['posted'])}" if r["posted"] else ""
        lines.append(f"{r['day']} {r['date'][5:]}  {r['post']:<5}{r['state']:<20}{r['title']}{done}")
        lines.append(f"{'':<12}to {', '.join(r['platforms'])}" + (f"  ({r['dir']})" if r["dir"] else ""))
        for p in r["problems"]:
            lines.append(f"{'':<12}fix: {p}")
    ready = sum(r["state"] == "ready" for r in rows)
    lines.append(f"{ready} of {len(rows)} ready to post")
    return "\n".join(lines)
