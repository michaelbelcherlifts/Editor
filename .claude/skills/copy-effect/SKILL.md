---
name: copy-effect
description: Use when Michael gives a YouTube link, a video file or screenshots and asks to recreate an effect, title, caption style or transition he saw, such as "make this", "I want that effect", "copy how they did this caption" or "do what this video does at 0:42".
---

# Recreating an effect from a reference

The reference is studied, never reused. Nothing from someone else's video goes
on Michael's timeline: the effect is rebuilt as our own HTML animation.

## Steps

1. **Get the reference.**
   - Link: `uv run stylebrain ref-fetch URL` (needs `yt-dlp`; saves under
     `references/`, which is not committed).
   - Screenshots: read the image files directly. Ask which moment matters if
     more than one thing is happening.
2. **Find the moment.** If Michael gave a time, use it with a second either
   side. If not, make a wide sheet first (`ref-sheet VIDEO --start 0 --end 60 --out wide.jpg`)
   and ask him to point.
3. **Look closely.**
   - `uv run stylebrain ref-sheet VIDEO --start S --end E --out sheet.jpg` then read
     the image. Each tile is stamped with its time.
   - `uv run stylebrain ref-motion VIDEO --start S --end E` lists when things
     move and for how long. Use these as the animation timings.
   - `uv run stylebrain ref-palette VIDEO --at T` gives the main colours. Add
     `--box '[x, y, w, h]'` (fractions) to read only the graphic.
   - `uv run stylebrain ref-frames ...` for larger stills when detail matters
     (font weight, stroke, shadow).
4. **Write down what the effect is** before building: what appears, where on
   the frame, entry motion and its length, hold, exit, colours, type style.
   Tell Michael in two or three lines so he can correct it.
5. **Build it.** Start from a template if one is close (`uv run stylebrain
   templates`). Otherwise write an HTML file with CSS animations, with
   `{{placeholders}}` for text and colours, and render it with the `html`
   template. See the animate skill for rendering rules.
6. **Check it against the reference.**
   `uv run stylebrain ref-compare VIDEO MINE.mov --ref-start S --seconds N --out compare.jpg --background STILL.png`
   puts the reference on the top row and ours below at matching moments. Read
   it, fix timing, size or colour, and repeat. Two or three rounds is normal.
   Stop when the remaining differences are ones Michael would not notice, or
   say plainly what could not be matched.
7. **Save it** so it is reusable:
   `uv run stylebrain effect-save NAME --template html --params '{...}' --about "from <where>, <what it is>"`.
8. **Place it** only where Michael asked: `effect-place NAME --at TIME --set text="..."`,
   then `build`, and relay the report.

## Limits to be honest about

- Fonts: use a free lookalike that is installed, and name the one chosen.
- Effects that warp the footage itself (zooms, speed ramps, shakes) are not
  overlays. Use `bake.py` for punch-ins and speed changes; say so if the effect
  needs something Resolve must do by hand.
- Do not copy logos, characters, music or footage from the reference.
