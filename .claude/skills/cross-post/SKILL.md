---
name: cross-post
description: Use when Michael wants a finished reel ready for each app, such as "get this ready for TikTok and YouTube", "write the captions", "what title for Shorts", "hashtags for this", "prep this week's posts" or "is everything ready to post".
---

# One reel, every platform

`src/stylebrain/crosspost.py` turns one calendar post into a version for each
platform it is planned for: Instagram Reels, TikTok, YouTube Shorts and YouTube
long-form. `src/stylebrain/publish.py` then posts the three short-form versions
in one go, **only when Michael asks** ("post it", "post today's reel", or his
double-click shortcut). Never post on your own initiative, on a schedule, or
because a draft looks finished. Long-form YouTube is posted by hand for now.

## What each version gets

- **Instagram**: caption (hook first, about 125 characters show before "more"),
  a line or two of value, the ask, at most 5 hashtags (Instagram's limit since
  December 2025).
- **TikTok**: hook, a plain-words line for TikTok search, the ask, 4 hashtags.
- **YouTube Shorts**: title (the idea's title, under 60 characters reads best),
  description with the hook, the ask, 3 hashtags. Links in Shorts are not
  clickable: a coaching ask says "link on my channel page", and a long video is
  linked with "Related video" in YouTube Studio.
- **YouTube long-form**: title, description, chapters drafted from the
  transcript (first at 0:00, three or more, 10 s or longer), tags under 500
  characters, the coaching link from `library/social/brand.json`. Needs a 16:9
  export (`export --size 1920x1080`).

The ask comes from the post's call to action in the calendar (`none` means no
ask at all, on purpose). A series episode asks people to follow for the next one.

Each version is checked: video shape and length for that app (Reels and Shorts
3 minutes), caption and title length, hashtag count, unfilled `[weight]`-style
placeholders, and any mention of worlds (keep that out for now).

## Commands

```
uv run stylebrain crosspost POST [--video cut.mp4] [--long-video wide.mp4] [--transcript words.json] [--out DIR]
uv run stylebrain crosspost-week [DATE|this-week|next-week] [--make] [--json]
uv run stylebrain post-result POST --platform tiktok --url URL --views N --saves N ...
```

- The video defaults to the idea's `draft`; the transcript to a `.json`, `.srt`
  or `.vtt` with the same name next to it.
- Files land in `library/crosspost/POST-title/` (not committed): one
  `PLATFORM.txt` to copy from, in the order the app asks, and `crosspost.json`.
  The post in the plan remembers the folder.
- `crosspost-week --make` prepares every approved reel that has a cut and no
  package yet, then lists the week: ready, needs fixes, cut not prepared,
  waiting for the cut, not approved, and which apps it is already posted on.

## How to use it

1. Run it, then **rewrite the drafts in his voice** before he sees them. The
   middle lines come from what he said, and chapter labels are the first words
   of each chapter: both need real writing. Keep the hook, the ask and the
   hashtag counts.
2. Never invent his numbers. Leave `[weight]` placeholders and ask him.
3. Show him each platform's text with the fixes listed. He changes what he
   likes; creative choices are his.
4. When he says he posted on an app, record it with `post-result --platform`, so
   links and numbers are kept per app and summed for the week report.

## Posting (the one button)

```
uv run stylebrain publish POST --dry-run     # check everything, send nothing: run this first
uv run stylebrain publish POST               # Instagram, TikTok and Shorts, when he asks
uv run stylebrain publish today              # today's approved reel
uv run stylebrain publish POST --only tiktok
uv run stylebrain connect youtube|instagram|tiktok ...   # once per account
uv run stylebrain publish-shortcut DESKTOP   # the double-click "Post today's reel" file
```

- It posts the words in each `PLATFORM.txt`, so his edits there count. Each is
  checked again first; a platform with a problem is skipped, the rest go.
- Links are recorded on the calendar post per app; pressing twice never posts twice.
- Until TikTok audits the app, TikTok posts go up private: tell him to make it
  public in the app.
- Account setup, step by step: `docs/publishing-setup.md`. Sign-ins live in
  `library/accounts/` (never commit or print them).
- Relay the result plainly: which apps it posted to with links, and which were
  skipped and why.
