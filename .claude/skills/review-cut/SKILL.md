---
name: review-cut
description: Use when Michael asks how his cut compares or what to improve, such as "review my edit", "how does this compare to that video", "what would make the hook better", "is the pacing right" or "recommend changes".
---

# Reviewing a cut against a style

1. Pick the style to measure against (`uv run stylebrain style-list`). If none
   fits, learn one first with the copy-style skill.
2. Review the current edit:
   `uv run stylebrain review STYLE --transcript CLIP.words.json`
   or a finished export: `uv run stylebrain review STYLE --video EXPORT.mp4 --transcript ...`.
   The export route also compares picture and sound.
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
gives 0 to 100 with every part listed. Run `score --questions` for the
judgements to make (1 to 5 each, from reading the transcript and looking at a
`ref-sheet` of the clip) and the flags. Always show the parts, name the weakest
one, and say that the weights are untuned: the score ranks clips against each
other and does not predict views.

For a clip with no speech (music and pictures only), leave out `--transcript`:
the opening is then judged on how soon the picture changes. A transcript that
is only "Thanks for watching" is the speech tool inventing words over music,
and is ignored.
