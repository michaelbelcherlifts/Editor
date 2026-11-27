---
name: autopilot
description: Use when Michael wants a first cut made for him from a raw recording without talking through each step, such as "edit this for me", "do a first pass", "run autopilot on this", "cut this while I'm away" or "make this like my usual style".
---

# First cut in one go

`uv run stylebrain auto NAME --source FILE` does, in order, each as its own
undoable version:

1. Transcribes the clip (or uses `FILE.words.json` / `--transcript`).
2. Cuts failed attempts it is sure of: a phrase said again, a line that breaks off and restarts,
   and anything before "let me start over" (`--keep-retakes` to skip).
3. Tightens pauses. With `--style NAME` the pause length comes from that style.
4. Puts on a saved look (`--look NAME`).
5. Places running captions (`--captions`).
6. Builds the timeline in Resolve (`--no-build` to skip).
7. Reviews the cut against the style and lists what stands out.

## The three-question start

When he gives a clip and says little else, ask these three and nothing more,
in one message, each with its options. Skip any his house rules or his words
already answer.

1. **Style**: one of the presets from `uv run stylebrain presets` (one-word,
   punchy, slam, talking-head, clean), or a style learned from a reference
   (`--style`). If he has not seen them, run `uv run stylebrain preset-preview all`
   and show him the files first.
2. **Look**: leave the colour as it is, or one of his saved looks
   (`uv run stylebrain look-list`).
3. **Frame**: vertical 1080x1920 or wide 1920x1080, unless the house rule
   for frame is set.

Then run `uv run stylebrain auto NAME --source FILE --preset STYLE [--look LOOK]
--width W --height H`. A preset sets the caption treatment and how tight the
pauses are; his house rules still win where set. The caption font is the same
for every preset for now.

## How to run it

1. Ask only what is not already known: which clip, and whether he wants
   captions, a style and a look. If he says "the usual", use what the last
   project used.
2. For vertical or 4K timelines pass `--width` and `--height`.
3. Run it and relay the report. Always pass on:
   - every "retake cut" line, since those are guesses. Offer `undo` or
     `goto` if any was a deliberate repeat.
   - every "possible ... not cut" line. These are his call: read them back
     and cut the ones he picks (`retakes --cut --maybe` cuts them all).
   - the new length.
   - whether it was built. If Resolve was closed, the edit is saved and
     `uv run stylebrain build` finishes the job later.
4. Walk through the review list, top to bottom, and ask which to act on.
   Do not act on review items unasked.

## Working unattended

When Michael is away, do steps 1 to 3, then stop at the review list. Do not
apply review suggestions, add effects or change the look on your own. Leave a
short note: what was cut, the new length, the timeline name, and the list.

## Limits

- Captions are transparent video and are large: about 3 to 8 MB per second.
  For long videos offer the `.srt` file instead (always written to
  `.stylebrain/renders/NAME.srt`), which Resolve imports as a subtitle track.
- No speech-to-text tool installed: say so and give the install line from
  the error, or use Resolve's own transcription and export it.
- Retake detection reads the words, not the delivery. It cuts repeats, restarts and
  "start over" moments it is sure of, and lists the rest as "possible ... not cut"
  (a line said again in other words, a doubled small word, "one more time"). Read
  those back and let him choose. A take that is worded the same but simply flat
  is invisible to it.
