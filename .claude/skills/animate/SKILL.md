---
name: animate
description: Use when Michael asks for an animation, title, caption, callout or explainer graphic on his video, such as "show the muscles worked", "add a lower third", "pop a caption here" or "highlight this part of the frame".
---

# Animations on the timeline

Animations are HTML pages rendered frame by frame to a transparent ProRes 4444
clip, then placed above the footage as an overlay.

## Ready-made templates

Run `uv run stylebrain templates` for the list. Today:

| Template | For | Key settings |
| --- | --- | --- |
| `caption_pop` | A short phrase popping in word by word | `text`, `accent_words`, `duration`, `size`, `y` |
| `lower_third` | Name and title | `name`, `title`, `accent`, `x`, `y` |
| `callout` | A box drawn round part of the frame, with a label | `text`, `box` = [x, y, w, h] as fractions |
| `captions` | Running captions with the spoken word highlighted | `words` = [{word, start, end}] |
| `muscle_diagram` | Body figure with muscles lighting up | `title`, `highlights`, `side` |
| `html` | Any hand-written animation file | `path`, `duration`, plus `{{placeholders}}` |

`muscle_diagram` highlights are muscle names, or `{"muscle", "label", "at", "role"}`
with role `primary` or `secondary`. Known muscles: traps, shoulders, rear delts,
chest, biceps, triceps, forearms, abs, obliques, quads, calves, lats, lower back,
glutes, hamstrings. Front and back views are picked automatically.

## Steps

1. Work out where it goes (playhead, marker, a spoken phrase, or a time) and how
   long it should stay.
2. Try it: `uv run stylebrain render TEMPLATE --params '{...}' --out /tmp/try.mov`,
   pull a frame with ffmpeg over a still of his footage, and look at it before
   placing it.
3. Save it if it will be reused: `uv run stylebrain effect-save NAME --template T --params '{...}' --about "..."`.
4. Place it: `uv run stylebrain effect-place NAME --at TIME --set text="..."`, then
   `uv run stylebrain build`.

For 4K or vertical timelines pass `--width` and `--height`; templates scale to fit.

## When no template fits

Write a new HTML file in `library/effects/`. Rules for the page:

- Transparent background, no external files or fonts from the network.
- Animate with CSS animations (or the Web Animations API). The renderer pauses
  them and steps time. For script-driven motion, define `window.seek = (seconds) => {...}`.
- Use `{{name}}` where text should be replaceable.

Save it with `--template html --params '{"path": "library/effects/NAME.html", "duration": 3}'`.

## Facts on screen

For teaching graphics (muscles worked, form cues, numbers), state what you chose
and why, and ask Michael to confirm before it goes in a final cut. He is the expert.

## Timing to speech

To sync highlights to words, find each word with `stylebrain find`, subtract the
overlay's start time, and pass the results as `at` values.
