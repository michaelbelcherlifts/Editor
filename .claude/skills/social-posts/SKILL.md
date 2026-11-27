---
name: social-posts
description: Use when Michael wants stills for Instagram or YouTube, such as "make a carousel from this reel", "edit this photo for my feed", "make a cover", "thumbnail options", "what should I post on my story" or "turn this video into posts".
---

# Photos, carousels, covers and stories

Stills are drawn as HTML and saved as one screenshot, so text matches his
video captions (heavy white type, black edge, yellow accent). Words wrapped in
`*stars*` get the accent colour. Photos and video frames are cropped with
ffmpeg and can take a colour look from `library/looks/`, so posts match his
graded reels. Nothing posts anything (rule: never auto-post).

`library/social/brand.json` holds his handle, site and colours.
`uv run stylebrain social sizes` lists sizes and where text must stay.

## Story first

The same rule as the reels: slide one is the hook, a promise the rest pays
off. One idea per slide. The last slide asks for one thing. Not every post
asks for coaching: coaching goes in stories, after a reel has shown value.

## One reel in, a package out

```
uv run stylebrain social package REEL.mp4 --transcript REEL.json --name NAME \
  --title "Stop *flaring* your elbows" [--hook "..."] [--topic bench] \
  [--cta follow|save|send|comment|coaching] [--look NAME] [--thumbnail]
```

Writes `library/social/NAME/` (not committed): `carousel.json` and slides,
three covers (each with a `_grid` crop showing what the profile grid shows),
three stories with sticker drafts, overview images, and `package.json`, which
the content calendar reads (`stylebrain social-import`, W11).

The first carousel is made of the words he said. Do not hand that over as is:

1. Read `carousel.json`. Rewrite each slide: the hook as a promise of 14 words
   or fewer, each idea in 35 words or fewer (shorter is better), accent one or
   two key words.
2. Re-render: `uv run stylebrain social carousel library/social/NAME/carousel.json --out library/social/NAME/carousel`.
3. Look at `overview.jpg` and any slide flagged with a problem. A "too many
   words" or "outside the safe zone" problem must be fixed before he sees it.
4. Rewrite the story drafts in `stories.json` the same way, with his voice
   (powerlifting humour is welcome). Re-render with `social stories`.
5. Show him the overview images and let him pick the cover.

## Single pieces

- Photo: `social photo IMG.jpg|REEL.mp4@12.5 --out OUT.jpg --size portrait|square|story|thumbnail [--look NAME] [--text "..."] [--place top|middle|bottom] [--focus 0.5,0.3]`
- Carousel draft from a transcript: `social carousel-draft --transcript T.json [--video REEL.mp4] --out plan.json`
- Carousel from his photos: write `plan.json` by hand, `{"slides": [{"kind": "hook"|"idea"|"cta", "text": "...", "image": "photo.jpg"}]}`, then `social carousel plan.json --out DIR`.
- Covers: `social covers REEL.mp4 --title "..." --out DIR [--at 3.2,8.0] [--thumbnail]`. A title is 7 words or fewer; decide it with the reel's hook.
- Stories: `social stories --hook "..." [--video REEL.mp4] [--topic ...] [--cta coaching] --out DIR`.

Frames from video are taken at the sharpest moment near the time asked for,
so a lift is not caught mid-blur. Sizes: portrait 1080x1350, square
1080x1080, story and cover 1080x1920, thumbnail 1280x720.
