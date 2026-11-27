---
name: review-cut
description: Use when Michael asks how his cut compares or what to improve, such as "review my edit", "how does this compare to that video", "what would make the hook better", "is the pacing right" or "recommend changes".
---

# Reviewing a cut against a style

Story and hook come before style. Every review starts with the hook check,
and a long video also gets a beat map, before any note about pacing or look.

## Story and hook first

- `uv run stylebrain hook-check --transcript CLIP.words.json --video CLIP.mp4`
  names what holds the first seconds back and the second it happens: dead
  air before the first meaningful word, a greeting opener, the first useful
  point landing after 3 s, the first change of picture after 1.5 s. Look at
  frame 1 and read the end, then pass what you saw:
  `--judge '{"text_on_frame_1": false, "undelivered": true}'`.
  `review` runs the same check on the current cut whenever it has a
  transcript, and `review --transcript ...` with no style runs only that.
- For long-form, read the transcript and label the beats (hook, setup,
  escalation, low point, payoff, next loop), then:
  `uv run stylebrain beats --transcript LONG.words.json --beats '[{"label": "hook", "start": 0}, ...]'`.
  It flags any stretch over 60 s with no new question and any run of
  "and then" sentences with no but or therefore. Add reveals or scene
  changes the words do not show with `--questions '[95.0, 240.0]'`.
- For each problem, offer a fix tied to a beat: cold-open on the payoff line,
  cut the greeting, a re-hook line to record, a "but" that names the stake.
  To rewrite a hook, follow the script skill's hook step.

## Against a style

1. Pick the style to measure against (`uv run stylebrain style-list`). If none
   fits, learn one first with the copy-style skill.
2. Review the current edit:
   `uv run stylebrain review STYLE --transcript CLIP.words.json`
   or a finished export: `uv run stylebrain review STYLE --video EXPORT.mp4 --transcript ...`.
   The export route also compares picture and sound.
   Add `--markers` to also write each note onto the open Resolve timeline as
   a coloured marker he can step through (Shift+Up and Shift+Down). They
   replace the last review's markers; `uv run stylebrain markers --clear`
   removes them. His own markers are never touched.
3. Read the list back in order. Each line has a time, a kind (opening, pace,
   long_shot, pause, picture, sound) and what differs from the style.
4. Then look for what numbers miss. Make a `ref-sheet` of his first 15 seconds
   and of the style's source, side by side in your reading, and comment on the
   opening line, framing, captions and graphics.
5. Offer fixes as choices, each tied to a line: `tighten` for pauses, `cut` for
   a slow start, a punch-in or graphic for a long shot, `look-make` for picture.
   Make only the ones he picks, one command each.

## Be straight about what this is

The review measures his cut against one reference. It does not know what
performs well; it knows what the reference does. Say "the reference does X",
not "X is better". In an edit made of jump cuts on one camera, every jump
counts as a cut, while the reference's cuts may be changes of picture, so
treat pace comparisons as a prompt to look, not a verdict.

## Scoring a short

`uv run stylebrain score --transcript CLIP.words.json --video CLIP.mp4 --judge '{...}'`
gives 0 to 100 with every part listed. The hook part includes how soon the
first useful point lands (pass `first_point` in seconds if your reading
differs from the measured one); pacing includes the longest held shot and
average sentence length. Always judge `story` (1 to 5): 2 or less means there
is nothing to find out, and the total is capped at 55 however good the rest
is. Run `score --questions` for the
judgements to make (1 to 5 each, from reading the transcript and looking at a
`ref-sheet` of the clip) and the flags. Always show the parts, name the weakest
one, and say that the weights are untuned: the score ranks clips against each
other and does not predict views.

For a clip with no speech (music and pictures only), leave out `--transcript`:
the opening is then judged on how soon the picture changes. A transcript that
is only "Thanks for watching" is the speech tool inventing words over music,
and is ignored.
