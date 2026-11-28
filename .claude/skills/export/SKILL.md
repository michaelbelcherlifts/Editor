---
name: export
description: Use when Michael wants a file to post or to watch on his phone, or wants a finished render checked, such as "export this", "render it for Instagram", "give me the file", "is this ready to post" or "check my export".
---

# Exporting a cut and checking it

There are two ways to a finished file. Ask which he wants if it is not clear.

- **Straight from the edit list** (no Resolve needed):
  `uv run stylebrain export` writes `exports/PROJECT-vN.mp4` at 1080x1920 with
  the look baked in, sounds mixed under the voice and loudness set to -14 LUFS,
  then checks it. Use this for a quick watch on a phone, or when the cut needs
  no hand polish.
- **From Resolve**, after he has polished the timeline by hand. He renders it
  in Resolve; then run `uv run stylebrain export-check FILE --seconds LENGTH`.

Wide footage: `--fit fill` (the default) crops to cover the vertical frame from
the centre. `--fit fit` keeps the whole picture with bars. Say which was used.

## After every export

1. Relay the check. Problems (wrong frame size, wrong length, too quiet or too
   loud, peaks, black frames, opening on black, no sound) mean it is not ready;
   say so plainly. Notes are for him to judge.
2. Open the frame sheet (`exports/NAME.frames.jpg`) and look at it. Say what
   you see: captions cut off, a graphic off-centre, his head cropped, a frame
   that looks wrong. Numbers do not catch these.
3. Give the path and the length in one line. Never post or upload the file.
4. A finished reel gets its five trial versions next (`.claude/skills/trial-reels/SKILL.md`).

The straight export does not include anything he changed by hand in Resolve.
If he has polished the timeline there, say that before exporting this way.
