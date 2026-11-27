---
name: colour-look
description: Use when Michael wants his footage graded like a reference, such as "match the color of this video", "give it that warm look", "make a LUT from this" or "grade it like the reference".
---

# Matching the colour of a reference

Resolve's scripting cannot move colour wheels or curves. It can put a LUT on a
clip. So the look is made here as a `.cube` file and applied on build.

## Steps

1. Get the reference (`ref-fetch URL`, or a file).
2. Pick the footage to match from. It must be Michael's clip **as he normally
   sees it**: if he shoots log, export a short normalised clip first, or the
   look will be built for the wrong starting point. Ask if unsure.
3. `uv run stylebrain look-make NAME --reference REF --footage MINE`.
   Start at full strength; `--strength 0.6` is a common softer choice.
4. Check it: `uv run stylebrain look-preview NAME --video MINE --at T --out look.jpg --reference REF --ref-at T2`
   and read the image (before, after, reference). Pick moments with similar
   content, ideally a face in both. Look at skin first. If skin has gone
   orange, green or grey, lower the strength and try again.
5. Show Michael the preview and let him choose the strength.
6. `uv run stylebrain look-use NAME`, then `build`. The report says if any clip
   refused the LUT. `look-use none` removes it; `undo` works as usual.

## A creator's look, with no reference video

Saved looks `creator-adam`, `creator-alex`, `creator-cbum`, `creator-luka`, `creator-mek`,
`creator-sam`, `creator-togi`, `creator-tren` and `creator-vince` come from the measured
creator profiles. They assume a typical phone clip. For a better fit, remake one from his
own footage: `uv run stylebrain look-from-style creator-sam --style PROFILE.json --footage MINE`
(a saved style name works in place of the file). Then preview and use it as above.

## A dark physique look

For a flex or pose moment (the dark, low-colour gym look), see `docs/aesthetic-shots.md`. A grade cannot add the overhead light that makes that look: say so if the footage is flat and evenly lit.

## What this does and does not match

It matches overall brightness, contrast and colour balance. It does not copy
vignettes, skin isolation, glow, grain or anything done to one part of the
frame. Say so if the reference clearly relies on those.

The match works best when the two videos show similar things (both a person in
a gym, say). A reference shot outdoors will pull an indoor clip toward blue
sky and green grass. In that case match from a stretch of the reference that
looks most like Michael's footage: cut that stretch out with ffmpeg first.

If Resolve refuses the LUT on build, the LUT file can be applied by hand on the
Color page, or baked into a copy of the clip with `look.apply_to_file`.
