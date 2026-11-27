---
name: copy-style
description: Use when Michael wants a whole video's editing style learned or applied, such as "edit it like this video", "learn this creator's pacing", "what makes this video feel fast" or "make my cut feel like that one".
---

# Learning and applying a style

A style is measured, saved under a name, and then used as a target. It guides
choices; it never applies itself. Michael approves what changes.

## Learn

1. Get the video: `uv run stylebrain ref-fetch URL` (or use a file he gives).
2. If there are subtitles or a word-timing transcript, pass it with
   `--transcript` so speech pace and the opening words are measured too.
3. `uv run stylebrain style-learn VIDEO --name NAME --about "who and what"`.
4. Read the summary back to Michael in a few lines. Then look, do not just
   count: make `ref-sheet` images of the first 15 seconds and of two typical
   stretches, and describe what the numbers cannot see: caption style and
   position, how often graphics appear, framing (tight or wide, centred or
   offset), punch-ins, b-roll use. Save those notes in the style's `about`.

Fast action or flashing lights can read as cuts. If the count looks wrong
against a frame sheet, re-run with `--threshold 0.4` (fewer) or `0.2` (more).

## Apply to Michael's edit

Offer these as options, with the numbers, and do only the ones he picks:

- **Pauses**: if his gaps are longer than the style's, `tighten --min-gap` set
  near the style's long gap.
- **Opening**: compare first word time and cuts in the opening. Suggest what
  to trim or move so the first line lands as early as the style's does.
- **Shot length**: list his stretches that run far longer than the style's
  long shot, as places for a punch-in (`bake.py`), a graphic or b-roll.
- **Captions and graphics**: rebuild the style's caption look with the
  copy-effect skill, then place it.
- **Picture**: see the colour skill once a look has been made from the style.

`uv run stylebrain style-show NAME` prints a saved style; `style-list` lists them.
