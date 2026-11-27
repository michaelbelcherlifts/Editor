# Two caption looks, and the shots that go with them

Built from the practice reels (Nov 2026). Round 1 used the default templates and Michael rated it a D:
"the captions, the color schemes, and the fonts ... It's very AI-ish." He also asked for text behind people,
lifts shown wide enough to see the plates, better music, and endings that loop into the hook. Round 2 made
the same two reels in two looks for him to choose between. Both are here as presets; pick by sight with
`preset-preview house` and `preset-preview cinematic`.

## house

From his strength.now x theswolefessor reference.

- Captions: `house_captions`. Montserrat Black (ships with the editor), slight italic, warm white with a
  thin dark edge, two or three words, a group ends at a full stop, a comma or a pause. One red word at most
  per group (`accent_words`). y 0.62 on a talking head; y 0.80 over a wide lift so the words sit under the
  plates.
- Opening text: `house_hook`, already on screen on frame 1 (no entry animation).
- Big numbers: `big_title` (Anton), placed high (y about 0.27), then `behind` so the lifter stands in
  front of it. Lower than that and his head covers the middle digit.
- `notification`: a tilted phone banner carrying the viewer's or a coach's question. Keep it off the face.

## cinematic

From the Blaze Kennedy study (`docs/cinematic-editing.md`).

- Captions: `plain_captions` in Montserrat, one or two words, plain white, no outline or colour.
- Titles: `spaced_title`.
- Lifts: `wide-clip --fill film`, a graded strip with black bars; a burst of 4 to 5 short cuts in the grind.

## Shots and sound for both

- `wide-clip SRC --start A --end B --x X --share 0.62`: a landscape lift kept wide in a vertical frame
  (blurred fill or film bars), so the weight is visible. Lay it over the main track with `broll`.
- `behind BASE TEXT.mov --out OUT`: text behind the person (needs `uv sync --extra people`; the
  segmentation model downloads to `library/models/` on first use). About 30 seconds of work per second of
  1080x1920 on a laptop CPU.
- `speech-only SRC --transcript WORDS --out OUT`: the source's own sound muted between spoken lines, so a
  vlog's background music drops out and a new song (`music-add`) can sit under the edit.

## Habits that came with them

- Cut on accurate word timings (`transcribe`), never on YouTube's auto captions: every clip starts on a
  sentence's first word and ends after its last. Round 1 cut lines a word short.
- End on a line that hands back to the first line, so the replay loops.
- One look per reel. Never rotate accent colours.
