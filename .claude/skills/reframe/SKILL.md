---
name: reframe
description: Use when footage has to fill a frame of another shape or Michael wants a punch-in, such as "make this vertical", "keep me in frame", "I'm cut off on the left", "follow the bar", "punch in here" or "zoom in on this line".
---

# Reframing and punch-ins

Each main-track clip carries a framing: `x` and `y` (the point of the picture
kept in the middle, 0 to 1) and `zoom` (1 is none). It follows the clip through
cuts and moves, exports with `export` and is set on the clips in Resolve at `build`.

## Wide footage to vertical

1. `uv run stylebrain reframe --auto` finds the subject in every shot (faces
   when the tracking extra is installed, otherwise where the movement is) and
   gives each shot one steady framing. Jump cuts of the same shot share it,
   and a clip that holds a hard cut to another shot is split there first.
2. Relay the lines. A `warning` means the subject moves across more than the
   frame can hold in that shot: offer to split the shot there, or to leave it.
   `nothing to follow` means it stayed in the middle.
3. Open the preview image it names and look. Say plainly if a head is cut off
   or the lift is half out of frame, and fix it by hand (below).

Upright phone footage already fits and is left alone.

## By hand

- Move the crop: `uv run stylebrain reframe --from 12 --to 18 --x 0.35`
  (smaller x looks further left, smaller y looks higher up).
- Punch in: `uv run stylebrain reframe --from 12 --to 18 --zoom 1.15 --y 0.4`.
  A punch-in on a jump cut hides the jump. Keep it between 1.1 and 1.3 unless asked.
  After `--auto` found a face, a punch-in closes in on the face by itself.
  Otherwise give `--y` (about 0.35 to 0.4 for a standing shot) or it crops his head.
- Leave out `--from` and `--to` to set the whole edit.

Punch-ins are a creative choice: offer them, do not add them unasked. A punch-in
counts as a zoom for `sfx-auto`.

## Limits to say out loud

- The framing is locked per shot. It does not pan to follow someone walking
  across the frame, and a slow zoom or pan inside one clip is not a cut, so
  that clip gets one framing: split it by hand where it should change.
- Words burned into wide footage get cut off by a vertical crop. Say so when
  the preview shows it.
- Instagram's grid shows the middle 4:5 of a reel. Keep faces and the lift
  away from the top and bottom sixth when choosing `y`.
- In Resolve the framing is set as Zoom, Pan and Tilt on each clip, and he can
  adjust it there. This has not been confirmed against real Resolve yet, so on
  the first build check one reframed clip by eye and report what you see.
