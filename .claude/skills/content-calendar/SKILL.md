---
name: content-calendar
description: Use when Michael wants to plan what to post, such as "plan next week", "what should I film", "add this idea", "move that reel to Friday", "what's on the calendar", "how did this week go" or "which posts get a coaching link".
---

# Planning the content

The plan lives in `library/content/plan.json` (not committed). It holds the idea
backlog, the series, the posts on the calendar and the settings. Nothing in it
posts anything: Michael presses post himself, then tells you, and you record it.

## The pieces

- **Idea**: one piece of content with a pillar, format, hook, where it is filmed,
  the shots, and its production status: idea, planned, recorded, edited,
  approved, posted, measured. An idea with `hold` set (a reason, such as "needs a
  runner friend") stays out of weekly plans.
- **Post**: an idea on a date and platforms with a call to action. A reel goes to
  Instagram, TikTok and YouTube Shorts by default; long-form to YouTube.
- **Pillars** (weights in `plan-settings`): strength 0.5, run 0.2, humour 0.2,
  life 0.1. Life is the cool guy side (Army, range days, lock picking, FPV
  drones, food), always with a lifting angle in the hook.
- **Series**: `mid-at-both` and `strong-vs-runner` to start; episodes number
  themselves. Add more with `series-add`.

## Rules

- Never frame anything around competing at worlds. Never invent his numbers in
  a hook: leave `[weight]`-style placeholders until he gives the real figure.
- Creative choices are his. Propose; he approves (`plan-approve`) or changes.
- Calls to action are planned on purpose: at most `coaching_per_week` coaching
  links (teaching strength posts), follow on series episodes, and at least
  `no_cta_share` of posts with no ask at all.
- Change one thing per command, and say what changed in one line.

## Commands

```
uv run stylebrain idea-add "TITLE" --pillar strength --hook "..." [--format reel] [--series KEY]
    [--location gym] [--shots "a;b"] [--cta save] [--score 77] [--draft PATH] [--hold "reason"]
uv run stylebrain idea-import FILE.json [--source trend|clip|analytics]   # a JSON list of ideas
uv run stylebrain idea-list [--status idea] [--pillar run]
uv run stylebrain idea-set ID --status recorded | --set hook="..." --set score=81 --set hold=none
uv run stylebrain plan-settings [--set volume.reel=7 --set volume.long-form=0.5 --set pillars.life=0.1]
uv run stylebrain plan-week [DATE|next-week]       # proposes; shows what is short in the backlog
uv run stylebrain plan-approve [DATE|next-week]
uv run stylebrain calendar [--start today --days 14] [--html page.html]
uv run stylebrain post-add IDEA DATE [--cta coaching] [--platforms instagram,tiktok]
uv run stylebrain post-set POST --date 2026-12-04 | --cta none | --status dropped
uv run stylebrain post-result POST --url URL --views N --sends N --saves N --follows N --enquiries N
uv run stylebrain shoot-list [DATE|next-week]      # what to film, by location, with the recording guide
uv run stylebrain week-report [DATE|this-week]     # planned versus posted, with results
uv run stylebrain social-import library/social/NAME/package.json --reel POST   # carousels and stories
```

## Feeding the backlog

- Clip candidates (auto-clipping), trend reports and analytics ideas arrive as a
  JSON list: each item needs `title` and `pillar`; optional `format`, `hook`,
  `series`, `cta`, `location`, `shots`, `note`, `score`, `draft`, `status`,
  `hold`. Use `idea-import FILE --source clip` (or `trend`, `analytics`).
- When a draft is cut, `idea-set ID --status edited --set draft=PATH`, and add
  its virality score with `--set score=N` from `stylebrain score`.

## A week, start to finish

1. Friday or Saturday: `plan-week next-week`. Show him the plan, the shortfalls
   and the call-to-action mix. Change what he asks, then `plan-approve`.
2. `shoot-list next-week` and send it to him: grouped by gym, track, range,
   kitchen, with film-by dates (two days before posting by default).
3. As he films and cuts, move statuses along (`recorded`, `edited`, `approved`).
4. When he says he posted, `post-result POST --url ...`; add numbers later.
5. End of the week: `week-report this-week`, and relay planned versus posted.
