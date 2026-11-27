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
| `kinetic_type` | Huge tilted word-by-word titles, one key word in colour (TOGI style) | `words` or `text`, `accent_words`, `per_group`, `y` |
| `mid_captions` | One to three words at a time, mid-frame | `words` or `text`, `max_words`, `accent_words` |
| `title_bar` | A title held for the whole video | `text`, `duration` (the video's length), `sub`, `light` |
| `end_card` | Numbers or macros counting up on a card | `items` = [{label, value, unit}], `title` |
| `counter` | Rep counter ticking on each rep, or a day counter | `ticks` (rep times) or `value`, `label`, `total` |
| `clipper` | Vertical frame: bands round a fitted landscape clip, headline on top | `headline`, `sub`, `duration`, `accent_words` |
| `lift_diagram` | Muscle diagram preset for a lift | `lift` (bench, squat, deadlift, sumo_deadlift, rdl, overhead_press, row, pull_up, dip, hip_thrust, lunge, close_grip_bench, low_bar_squat), `only` |
| `form_cue` | Arrows, lines and measured joint angles over a freeze frame | `arrows`, `lines`, `angles` (points as [x, y] fractions) |
| `tempo_counter` | Rep tempo counted down phase by phase | `tempo` such as "3-1-1-0", `reps` |
| `compare_chart` | Bars that grow and count, for comparisons | `bars` = [{label, value}], `highlight`, `unit` |
| `html` | Any hand-written animation file | `path`, `duration`, plus `{{placeholders}}` |

Cards (`muscle_diagram`, `lift_diagram`, `end_card`, `compare_chart`) stay out of the
running-caption band (70% to 92% down the frame) so they never cover captions. Pass
`keep_clear` as another [top, bottom] band if captions sit elsewhere, or `null` to turn it off.

Every graphic should serve a story beat (stakes, turn or payoff). Say which one when
offering it.

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

The `lift_diagram` presets are a coaching summary chosen by Claude. Show Michael the
preset (muscles and which are primary) before it goes in a final cut. `form_cue`
measures angles from the points you place, so place them on the joints in the frame.

For teaching graphics (muscles worked, form cues, numbers), state what you chose
and why, and ask Michael to confirm before it goes in a final cut. He is the expert.

## Timing to speech

To sync highlights to words, find each word with `stylebrain find`, subtract the
overlay's start time, and pass the results as `at` values.
