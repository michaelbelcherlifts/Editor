"""The content plan: idea backlog, series, calendar, weekly plans, shoot lists and calls to action.

Everything lives in one file, `library/content/plan.json`, which is not committed:
the plan is Michael's. Nothing here posts anything. A post moves to "posted" only
when he says he posted it.

Two kinds of record:

- An **idea** is one piece of content: a title, a pillar, a hook, a format, what
  to film and where. Its status follows production: idea, planned, recorded,
  edited, approved, posted, measured.
- A **post** puts an idea on a date, on one or more platforms, with a call to
  action. Its status is proposed (in a weekly plan he has not approved),
  planned, posted, measured or dropped.

A weekly plan is proposed from the backlog by pillar mix and target volume, and
only becomes the calendar when he approves it.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import math
from pathlib import Path

from .edl import EditError

STATUSES = ["idea", "planned", "recorded", "edited", "approved", "posted", "measured"]
POST_STATUSES = ["proposed", "planned", "posted", "measured", "dropped"]

# Where each format goes by default. A reel is cut once and posted to all three.
FORMATS = {
    "reel": ["instagram", "tiktok", "youtube-shorts"],
    "long-form": ["youtube"],
    "carousel": ["instagram", "tiktok"],
    "story": ["instagram"],
    "photo": ["instagram"],
}

PILLARS = {
    "strength": {"name": "Strength first", "weight": 0.5,
                 "job": "Proof and identity: PRs, training, the cues that work. Teaching clips lead to coaching."},
    "run": {"name": "The lifter who can run", "weight": 0.2,
            "job": "The twist that sets him apart; the stakes are 'will the big guy hold up?'"},
    "humour": {"name": "Humour", "weight": 0.2,
               "job": "Reach and shares: the anti-hybrid joke, powerlifting POVs."},
    "life": {"name": "The cool guy life around it", "weight": 0.1,
             "job": "Personality: Army life, guns, lock picking, FPV drones, food. A lifting angle in every hook."},
}

# Calls to action. Not every post gets one: "none" is a planned choice too.
CTAS = {
    "none": "No ask. Let the video do the work.",
    "follow": "Ask for a follow, tied to the next episode or the series.",
    "comment": "Ask a question people will want to answer or argue with.",
    "send": "Ask them to send it to the friend it is about.",
    "save": "Ask them to save it for their next session.",
    "coaching": "Point to coaching: link in bio (nospotter.com), or in the description on YouTube.",
    "long-form": "Point to the full video, only when it adds something.",
}

DEFAULT_SERIES = {
    "mid-at-both": {"name": "Mid at both?",
                    "premise": "Each episode tests one claim about lifters who run. Stake, attempt, twist, verdict."},
    "strong-vs-runner": {"name": "Strong guy vs runner",
                         "premise": "Head-to-heads where each side picks the event. Scoreboard and a loser's forfeit."},
    "one-cue": {"name": "One cue", "premise": "One cue per episode that fixes one lift, shown before and after."},
}

DEFAULT_SETTINGS = {
    "volume": {"reel": 7, "carousel": 1, "long-form": 0.5},  # per week; 0.5 = every other week
    "pillars": {k: v["weight"] for k, v in PILLARS.items()},
    "coaching_per_week": 2,   # most posts that point to coaching in one week
    "no_cta_share": 0.3,      # at least this share of posts carry no ask
    "film_days_before": 2,    # a shoot list says to film this many days before posting
}

READINESS = {"approved": 0, "edited": 1, "recorded": 2, "planned": 3, "idea": 3}

# The recording guide (PRD W7.9): long-form filmed so it cuts into shorts.
RECORDING_GUIDE = [
    "Say each key point as one standalone sentence; never 'like I said earlier'.",
    "Restate the topic before each segment so a clip can start there.",
    "Keep your face and the lift in the centre third, so a 9:16 crop works.",
    "Film the payoff on purpose: the rep, the time on the watch, the reaction.",
    "Leave real reactions in. Start talking on the first frame, no greeting.",
]

DEFAULT_SHOTS = {
    "reel": ["Hook shot: the payoff or a face close to camera, moving on frame 1",
             "The attempt or the demo, centre third", "The payoff, held long enough to read"],
    "long-form": ["Cold open: the strongest moment", "Each segment opens with its topic restated",
                  "B-roll of every noun you mention", "The payoff, filmed from two angles"],
    "carousel": ["Cover photo with the hook as text space", "One clean photo per slide"],
    "story": ["Vertical phone clip"],
    "photo": ["Vertical photo"],
}


def root(base: str | Path = ".") -> Path:
    return Path(base) / "library" / "content"


def parse_date(text: str | dt.date) -> dt.date:
    if isinstance(text, dt.date):
        return text
    t = text.strip().lower()
    today = dt.date.today()
    if t == "today":
        return today
    if t in ("this-week", "this week"):
        return monday_of(today)
    if t in ("next-week", "next week"):
        return monday_of(today) + dt.timedelta(days=7)
    try:
        return dt.date.fromisoformat(t)
    except ValueError:
        raise EditError(f"not a date: {text!r} (use YYYY-MM-DD, today, this-week or next-week)") from None


def monday_of(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def quotas(n: int, weights: dict[str, float]) -> dict[str, int]:
    """Split n slots by weight, largest remainder first."""
    total = sum(weights.values()) or 1
    raw = {k: n * w / total for k, w in weights.items()}
    out = {k: math.floor(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: (-(raw[k] - out[k]), -weights[k]))[: n - sum(out.values())]:
        out[k] += 1
    return out


def count_this_week(per_week: float, monday: dt.date) -> int:
    """How many of a format fall in this week, so 0.5 a week lands every other week."""
    n = monday.toordinal() // 7
    return math.floor((n + 1) * per_week + 1e-9) - math.floor(n * per_week + 1e-9)


class Plan:
    def __init__(self, base: str | Path = "."):
        self.path = root(base) / "plan.json"
        if self.path.exists():
            self.data = json.loads(self.path.read_text())
        else:
            self.data = {"settings": json.loads(json.dumps(DEFAULT_SETTINGS)),
                         "series": json.loads(json.dumps(DEFAULT_SERIES)), "ideas": [], "posts": []}
        self.data.setdefault("settings", {})
        for k, v in DEFAULT_SETTINGS.items():
            self.data["settings"].setdefault(k, v)

    # ----- storage
    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2) + "\n")

    @property
    def settings(self) -> dict:
        return self.data["settings"]

    @property
    def ideas(self) -> list[dict]:
        return self.data["ideas"]

    @property
    def posts(self) -> list[dict]:
        return self.data["posts"]

    def _next_id(self, prefix: str, items: list[dict]) -> str:
        nums = [int(x["id"][1:]) for x in items if x["id"][1:].isdigit()]
        return f"{prefix}{max(nums, default=0) + 1}"

    def idea(self, idea_id: str) -> dict:
        for i in self.ideas:
            if i["id"] == idea_id:
                return i
        raise EditError(f"no idea {idea_id!r}")

    def post(self, post_id: str) -> dict:
        for p in self.posts:
            if p["id"] == post_id:
                return p
        raise EditError(f"no post {post_id!r}")

    # ----- ideas and series
    def add_idea(self, title: str, pillar: str, *, format: str = "reel", hook: str | None = None,
                 series: str | None = None, cta: str | None = None, source: str = "own",
                 location: str | None = None, shots: list[str] | None = None, note: str | None = None,
                 score: float | None = None, draft: str | None = None, status: str = "idea",
                 hold: str | None = None) -> dict:
        self._check(pillar=pillar, format=format, cta=cta, series=series, status=status)
        idea = {"id": self._next_id("i", self.ideas), "title": title, "pillar": pillar, "format": format,
                "hook": hook, "series": series, "episode": None, "cta": cta, "source": source,
                "location": location or "anywhere", "shots": shots or [], "note": note, "score": score,
                "draft": draft, "status": status, "hold": hold, "added": dt.date.today().isoformat()}
        if series:
            idea["episode"] = 1 + max((i["episode"] or 0 for i in self.ideas if i.get("series") == series), default=0)
        self.ideas.append(idea)
        return idea

    def import_ideas(self, items: list[dict], source: str | None = None) -> list[dict]:
        """Ideas from trend reports, clip candidates, analytics or his notes (JSON list)."""
        out = []
        for it in items:
            it = dict(it)
            if source:
                it.setdefault("source", source)
            title, pillar = it.pop("title", None), it.pop("pillar", None)
            if not title or not pillar:
                raise EditError(f"each idea needs a title and a pillar: {it}")
            allowed = {"format", "hook", "series", "cta", "source", "location", "shots", "note", "score",
                       "draft", "status", "hold"}
            out.append(self.add_idea(title, pillar, **{k: v for k, v in it.items() if k in allowed}))
        return out

    def set_idea(self, idea_id: str, **fields) -> dict:
        idea = self.idea(idea_id)
        self._check(**{k: v for k, v in fields.items() if k in ("pillar", "format", "cta", "series", "status")})
        for k, v in fields.items():
            if k not in idea and k != "hold":
                raise EditError(f"ideas have no field {k!r} (fields: {', '.join(idea)})")
            if k == "score" and v is not None:
                v = float(v)
            if k == "shots" and isinstance(v, str):
                v = [s.strip() for s in v.split(";") if s.strip()]
            idea[k] = v
        return idea

    def add_series(self, key: str, name: str, premise: str) -> None:
        self.data["series"][key] = {"name": name, "premise": premise}

    def series_view(self) -> list[dict]:
        out = []
        for key, s in self.data["series"].items():
            eps = sorted((i for i in self.ideas if i.get("series") == key), key=lambda i: i["episode"] or 0)
            out.append({"key": key, **s, "episodes": [
                {"episode": i["episode"], "id": i["id"], "title": i["title"], "status": i["status"],
                 "date": self._first_date(i["id"])} for i in eps]})
        return out

    def _check(self, pillar=None, format=None, cta=None, series=None, status=None) -> None:
        if pillar is not None and pillar not in self.settings["pillars"]:
            raise EditError(f"unknown pillar {pillar!r} (pillars: {', '.join(self.settings['pillars'])})")
        if format is not None and format not in FORMATS:
            raise EditError(f"unknown format {format!r} (formats: {', '.join(FORMATS)})")
        if cta is not None and cta not in CTAS:
            raise EditError(f"unknown call to action {cta!r} (choices: {', '.join(CTAS)})")
        if series is not None and series not in self.data["series"]:
            raise EditError(f"unknown series {series!r}; add it with series-add first "
                            f"(series: {', '.join(self.data['series']) or 'none'})")
        if status is not None and status not in STATUSES:
            raise EditError(f"unknown status {status!r} (statuses: {', '.join(STATUSES)})")

    # ----- posts
    def _live_posts(self) -> list[dict]:
        return [p for p in self.posts if p["status"] != "dropped"]

    def _first_date(self, idea_id: str) -> str | None:
        dates = [p["date"] for p in self._live_posts() if p["idea"] == idea_id]
        return min(dates) if dates else None

    def schedule(self, idea_id: str, date: str | dt.date, *, platforms: list[str] | None = None,
                 cta: str | None = None, status: str = "planned") -> dict:
        idea = self.idea(idea_id)
        self._check(cta=cta)
        post = {"id": self._next_id("p", self.posts), "idea": idea_id, "date": parse_date(date).isoformat(),
                "format": idea["format"], "platforms": platforms or FORMATS[idea["format"]],
                "cta": cta or idea.get("cta") or "none", "status": status, "url": None, "results": {}}
        self.posts.append(post)
        if status == "planned" and idea["status"] == "idea":
            idea["status"] = "planned"
        return post

    def set_post(self, post_id: str, *, date=None, cta=None, platforms=None, status=None) -> dict:
        post = self.post(post_id)
        if date is not None:
            post["date"] = parse_date(date).isoformat()
        if cta is not None:
            self._check(cta=cta)
            post["cta"] = cta
        if platforms is not None:
            post["platforms"] = platforms
        if status is not None:
            if status not in POST_STATUSES:
                raise EditError(f"unknown post status {status!r} (statuses: {', '.join(POST_STATUSES)})")
            post["status"] = status
            idea = self.idea(post["idea"])
            if status in ("posted", "measured") and STATUSES.index(idea["status"]) < STATUSES.index(status):
                idea["status"] = status
        return post

    def record_result(self, post_id: str, url: str | None = None, **results) -> dict:
        """He posted it (by hand). Record the link and any numbers."""
        post = self.post(post_id)
        if url:
            post["url"] = url
        clean = {k: float(v) for k, v in results.items() if v is not None}
        post["results"].update(clean)
        self.set_post(post_id, status="measured" if clean else "posted")
        return post

    def import_social(self, package: dict, reel_post: str) -> list[dict]:
        """Place a carousel, image and story package (library/social/NAME/package.json) around a reel's post date."""
        reel = self.post(reel_post)
        reel_idea = self.idea(reel["idea"])
        base = dt.date.fromisoformat(reel["date"])
        made = []
        for item in package.get("posts", []):
            files = item.get("files") or []
            if item.get("format") == "cover":
                if files:
                    reel_idea["note"] = "; ".join(x for x in [reel_idea.get("note"), "cover: " + ", ".join(files)] if x)
                continue
            caption = (item.get("caption") or package.get("name") or "social post").strip()
            title = caption.splitlines()[0][:80]
            note = "; ".join(x for x in [item.get("notes"),
                                         f"sticker: {item['sticker']}" if item.get("sticker") else None,
                                         f"from social package {package.get('name', '?')}",
                                         f"time {item['suggested_time']}" if item.get("suggested_time") else None,
                                         "files: " + ", ".join(files) if files else None] if x)
            idea = self.add_idea(title, reel_idea["pillar"], format=item.get("format", "carousel"), hook=caption,
                                 cta=item.get("cta"), source="social", note=note,
                                 draft=files[0] if files else None, status="edited")
            day = base + dt.timedelta(days=math.floor(float(item.get("suggested_day", 0))))
            made.append(self.schedule(idea["id"], day, cta=item.get("cta")))
        return made

    # ----- weekly plan
    def propose_week(self, monday: str | dt.date) -> dict:
        """Fill a week from the backlog by target volume and pillar mix. Proposed only: nothing is final until approved."""
        monday = monday_of(parse_date(monday))
        days = [monday + dt.timedelta(days=d) for d in range(7)]
        week = {d.isoformat() for d in days}
        # Replace any earlier proposal for this week; keep what he already approved.
        self.data["posts"] = [p for p in self.posts if not (p["status"] == "proposed" and p["date"] in week)]
        taken = {p["idea"] for p in self._live_posts()}
        shortfalls, made = [], []
        for offset, (fmt, per_week) in enumerate(self.settings["volume"].items()):
            have = [p for p in self._live_posts() if p["date"] in week and p["format"] == fmt]
            n = count_this_week(float(per_week), monday) - len(have)
            if n <= 0:
                continue
            pool = [i for i in self.ideas if i["format"] == fmt and i["id"] not in taken and not i.get("hold")
                    and i["status"] in ("idea", "planned", "recorded", "edited", "approved")]
            pool.sort(key=lambda i: (READINESS[i["status"]], i.get("series") or "~", i["episode"] or 0,
                                     -(i["score"] or 0), int(i["id"][1:])))
            want = quotas(n, self.settings["pillars"])
            picked: dict[str, list[dict]] = {}
            for pillar, k in want.items():
                got = [i for i in pool if i["pillar"] == pillar][:k]
                picked[pillar] = got
                if len(got) < k:
                    shortfalls.append(f"{k - len(got)} more {fmt} idea(s) for {pillar}")
            # Give unfilled slots to whatever is left in the backlog.
            spare = n - sum(len(v) for v in picked.values())
            chosen_ids = {i["id"] for v in picked.values() for i in v}
            for i in [i for i in pool if i["id"] not in chosen_ids][:spare]:
                picked.setdefault(i["pillar"], []).append(i)
            order = _interleave(picked)
            if len(order) < n:
                shortfalls.append(f"{fmt}: {n - len(order)} slot(s) empty this week")
            for idx, idea in enumerate(order):
                day = days[(math.floor(idx * 7 / max(len(order), 1)) + offset * 3) % 7]
                made.append(self.schedule(idea["id"], day, status="proposed"))
                taken.add(idea["id"])
        self._assign_ctas([p for p in self.posts if p["date"] in week and p["status"] in ("proposed",)], week)
        return {"week": monday.isoformat(), "posts": made, "shortfalls": shortfalls}

    def _assign_ctas(self, proposed: list[dict], week: set[str]) -> None:
        """Calls to action on purpose: coaching on a few teaching posts, follow on series, many with none."""
        all_week = [p for p in self._live_posts() if p["date"] in week]
        coaching_left = self.settings["coaching_per_week"] - sum(
            1 for p in all_week if p["cta"] == "coaching" and p["status"] != "proposed")
        auto = []
        for p in proposed:  # his own choices first, so they count against the coaching limit
            cta = self.idea(p["idea"]).get("cta")
            if cta:
                p["cta"] = cta
                coaching_left -= cta == "coaching"
        for p in sorted(proposed, key=lambda p: (-(self.idea(p["idea"])["score"] or 0), p["date"])):
            idea = self.idea(p["idea"])
            if idea.get("cta"):
                continue
            if p["format"] == "long-form":
                p["cta"] = "follow"
            elif idea["pillar"] == "strength" and coaching_left > 0:
                p["cta"], coaching_left = "coaching", coaching_left - 1
            elif idea.get("series"):
                p["cta"] = "follow"
            else:
                p["cta"] = {"strength": "save", "run": "comment", "humour": "send", "life": "none"}.get(
                    idea["pillar"], "none")
            auto.append(p)
        need_none = math.ceil(self.settings["no_cta_share"] * len(all_week)) - sum(
            1 for p in all_week if p["cta"] == "none")
        for p in [p for p in reversed(auto) if p["cta"] in ("save", "send", "comment")][:max(need_none, 0)]:
            p["cta"] = "none"

    def approve_week(self, monday: str | dt.date) -> list[dict]:
        monday = monday_of(parse_date(monday))
        week = {(monday + dt.timedelta(days=d)).isoformat() for d in range(7)}
        done = []
        for p in self.posts:
            if p["date"] in week and p["status"] == "proposed":
                p["status"] = "planned"
                idea = self.idea(p["idea"])
                if idea["status"] == "idea":
                    idea["status"] = "planned"
                done.append(p)
        if not done:
            raise EditError(f"nothing proposed for the week of {monday}; run plan-week first")
        return done

    # ----- views
    def rows(self, start: str | dt.date, days: int = 14) -> list[dict]:
        s = parse_date(start)
        e = s + dt.timedelta(days=days)
        out = []
        for p in sorted(self._live_posts(), key=lambda p: (p["date"], p["id"])):
            d = dt.date.fromisoformat(p["date"])
            if s <= d < e:
                i = self.idea(p["idea"])
                series = self.data["series"].get(i.get("series") or "", {}).get("name")
                out.append({"post": p["id"], "idea": i["id"], "date": p["date"], "day": d.strftime("%a"),
                            "format": p["format"], "platforms": p["platforms"], "pillar": i["pillar"],
                            "title": i["title"], "hook": i["hook"], "cta": p["cta"],
                            "post_status": p["status"], "status": i["status"], "score": i["score"],
                            "draft": i["draft"], "series": f"{series} #{i['episode']}" if series else None,
                            "location": i["location"]})
        return out

    def shoot_list(self, monday: str | dt.date) -> dict:
        """What to film so the week's plan can be met, grouped by where it is filmed."""
        monday = monday_of(parse_date(monday))
        groups: dict[str, list[dict]] = {}
        for r in self.rows(monday, 7):
            if r["status"] not in ("idea", "planned"):
                continue  # already filmed
            idea = self.idea(r["idea"])
            film_by = dt.date.fromisoformat(r["date"]) - dt.timedelta(days=self.settings["film_days_before"])
            groups.setdefault(idea["location"], []).append({
                "idea": idea["id"], "title": idea["title"], "hook": idea["hook"], "format": idea["format"],
                "post_on": r["date"], "film_by": film_by.isoformat(),
                "shots": idea["shots"] or DEFAULT_SHOTS[idea["format"]]})
        for items in groups.values():
            items.sort(key=lambda x: x["film_by"])
        return {"week": monday.isoformat(), "locations": groups, "guide": RECORDING_GUIDE}

    def week_report(self, monday: str | dt.date) -> dict:
        """Planned versus posted for one week, with whatever results were recorded."""
        monday = monday_of(parse_date(monday))
        rows = [r for r in self.rows(monday, 7) if r["post_status"] != "proposed"]
        posted = [r for r in rows if r["post_status"] in ("posted", "measured")]
        missed = [r for r in rows if r["post_status"] == "planned"]
        totals: dict[str, float] = {}
        for r in posted:
            for k, v in self.post(r["post"])["results"].items():
                totals[k] = totals.get(k, 0) + v
        by_pillar = {}
        for r in rows:
            b = by_pillar.setdefault(r["pillar"], {"planned": 0, "posted": 0})
            b["planned"] += 1
            b["posted"] += r in posted
        return {"week": monday.isoformat(), "planned": len(rows), "posted": len(posted),
                "missed": [{"post": r["post"], "date": r["date"], "title": r["title"], "status": r["status"]}
                           for r in missed],
                "by_pillar": by_pillar, "totals": totals,
                "results": [{"post": r["post"], "title": r["title"], **self.post(r["post"])["results"]}
                            for r in posted]}


def _interleave(picked: dict[str, list[dict]]) -> list[dict]:
    """Order a week so the same pillar is not posted twice in a row when it can be avoided."""
    queues = {k: list(v) for k, v in picked.items() if v}
    out, last = [], None
    while queues:
        options = sorted(queues, key=lambda k: (k == last, -len(queues[k])))
        k = options[0]
        out.append(queues[k].pop(0))
        last = k
        if not queues[k]:
            del queues[k]
    return out


# ----- text and HTML

def format_rows(rows: list[dict]) -> str:
    if not rows:
        return "nothing on the calendar for these dates"
    lines, week = [], None
    for r in rows:
        w = monday_of(dt.date.fromisoformat(r["date"]))
        if w != week:
            week = w
            lines.append(f"Week of {w:%a %d %b %Y}")
        extra = " ".join(x for x in [f"[{r['series']}]" if r["series"] else "",
                                     f"score {r['score']:g}" if r["score"] is not None else "",
                                     "(proposed)" if r["post_status"] == "proposed" else ""] if x)
        lines.append(f"  {r['day']} {r['date'][5:]}  {r['post']:<5}{r['format']:<10}{r['pillar']:<9}"
                     f"{r['status']:<9}cta {r['cta']:<9}{r['title']} {extra}".rstrip())
        if r["hook"]:
            lines.append(f"{'':<23}hook: {r['hook']}")
    return "\n".join(lines)


def format_shoot_list(sl: dict) -> str:
    lines = [f"Shoot list, week of {sl['week']}"]
    if not sl["locations"]:
        lines.append("  nothing left to film for this week")
    for loc, items in sorted(sl["locations"].items()):
        lines.append(f"\n{loc} ({len(items)})")
        for it in items:
            lines.append(f"  {it['idea']} film by {it['film_by']} (posts {it['post_on']}): {it['title']}")
            if it["hook"]:
                lines.append(f"      hook: {it['hook']}")
            for s in it["shots"]:
                lines.append(f"      - {s}")
    lines.append("\nRecording guide")
    lines += [f"  - {g}" for g in sl["guide"]]
    return "\n".join(lines)


def format_week_report(rep: dict) -> str:
    lines = [f"Week of {rep['week']}: {rep['posted']} of {rep['planned']} planned posts went out"]
    for k, v in rep["by_pillar"].items():
        lines.append(f"  {k:<9} {v['posted']}/{v['planned']}")
    if rep["missed"]:
        lines.append("Not posted:")
        lines += [f"  {m['date']} {m['post']} {m['title']} (still {m['status']})" for m in rep["missed"]]
    if rep["totals"]:
        lines.append("Totals: " + ", ".join(f"{k} {v:g}" for k, v in rep["totals"].items()))
        for r in rep["results"]:
            nums = ", ".join(f"{k} {v:g}" for k, v in r.items() if k not in ("post", "title"))
            lines.append(f"  {r['post']} {r['title']}: {nums or 'no numbers yet'}")
    else:
        lines.append("No results recorded yet (post-result ID --views N ...).")
    return "\n".join(lines)


def to_html(plan: Plan, start: str | dt.date, days: int = 28, title: str = "Content calendar") -> str:
    """A self-contained page of the calendar, one row per week, for review."""
    s = monday_of(parse_date(start))
    rows = plan.rows(s, days)
    by_day: dict[str, list[dict]] = {}
    for r in rows:
        by_day.setdefault(r["date"], []).append(r)
    e = html.escape
    weeks = []
    for w in range(math.ceil(days / 7)):
        cells = []
        for d in range(7):
            day = s + dt.timedelta(days=w * 7 + d)
            cards = "".join(
                f'<div class="card {e(r["pillar"])}"><div class="meta">{e(r["format"])} · {e(r["pillar"])}'
                f'{" · " + e(r["series"]) if r["series"] else ""}</div><div class="t">{e(r["title"])}</div>'
                + (f'<div class="h">“{e(r["hook"])}”</div>' if r["hook"] else "")
                + f'<div class="meta">CTA: {e(r["cta"])} · {e(r["status"])}'
                + (" · proposed" if r["post_status"] == "proposed" else "") + "</div></div>"
                for r in by_day.get(day.isoformat(), []))
            cells.append(f'<td><div class="d">{day:%a %d %b}</div>{cards}</td>')
        weeks.append(f'<tr>{"".join(cells)}</tr>')
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{e(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{font:14px/1.4 system-ui,sans-serif;margin:24px;color:#1d1d1f;background:#fafafa}}
table{{border-collapse:collapse;width:100%;table-layout:fixed}}td{{vertical-align:top;border:1px solid #ddd;padding:6px;background:#fff}}
.d{{font-weight:600;font-size:12px;color:#666;margin-bottom:4px}}.card{{border-left:4px solid #999;padding:4px 6px;margin:4px 0;background:#f4f4f4;border-radius:4px}}
.strength{{border-color:#c0392b}}.run{{border-color:#2471a3}}.humour{{border-color:#d4ac0d}}.life{{border-color:#1e8449}}
.t{{font-weight:600}}.h{{font-style:italic}}.meta{{font-size:11px;color:#666}}
</style></head><body><h1>{e(title)}</h1><p>From {s:%d %b %Y}, {len(rows)} posts. Nothing posts automatically.</p>
<table>{"".join(weeks)}</table></body></html>"""
