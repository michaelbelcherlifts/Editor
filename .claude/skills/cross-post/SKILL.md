---
name: cross-post
description: Use when Michael wants a finished reel ready for each app, such as "get this ready for TikTok and YouTube", "write the captions", "what title for Shorts", "hashtags for this", "prep this week's posts" or "is everything ready to post".
---

# One reel, every platform

`src/stylebrain/crosspost.py` turns one calendar post into a version for each
platform it is planned for: Instagram Reels, TikTok, YouTube Shorts and YouTube
long-form. It prepares posts only. **Never post, upload or schedule anything**:
Michael presses post himself in each app, then tells you, and you record it.

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
