# Creator study

254 clips from 14 creators, each measured second by second in a browser, and
each with its view count. The style files in `library/styles/` are built from
these records with `uv run stylebrain style-from-study`.

## What is here

- `records/<creator>__<video id>.json`: one clip each. Holds the video's
  details (title, views, date, size), the `attributes` (the numbers below),
  every cut time, the opening words, the first part of the transcript, and a
  per-second `timeline`. The timeline columns are listed in `timeline_fields`.
- `clips.csv`: the same attributes, one row per clip, for a spreadsheet.
- `hits_vs_flops.md`: within each creator, which attributes go with more views.
- `scripts/`: `analyzer.js` (the in-page measuring code), `build_dataset.py`
  and `build_dataset_lib.py` (records from the raw scans), and `analyse.py`
  (the hits vs flops report).

## Clips per creator

| creator | slug | clips | format |
|---|---|---|---|
| MekLuvin | mekluvin | 27 | Shorts |
| Chris Bumstead | cbum | 26 | Shorts |
| Vince Wilkinson | vince | 26 | Shorts |
| Alex Eubank | alex | 24 | Shorts |
| Noah Anderson | noah | 20 | Shorts |
| Jun Yuh | jun | 20 | Shorts |
| Good Good | goodgood | 20 | Shorts |
| Japes | japes | 20 | Shorts |
| Solid Heaston | solidheaston | 20 | Shorts |
| Luka Hocevar | luka | 15 | Shorts |
| Sam Sulek | sam | 13 | first minute of long videos |
| TOGI | togi | 9 | first minute of long videos |
| Young Dalt | youngdalt | 8 | Shorts (all he has) |
| Tren Twins | tren | 6 | Shorts (all on YouTube) |

Sam Sulek and TOGI post almost no Shorts, so their records are the opening
minute of their long videos. Adam Yu posts only on Instagram, and the Tren
Twins post most reels there, so both still need Instagram reels (see below).

## How each clip was measured

The video plays in a browser tab and a script reads its frames into a canvas
about 8 times a second.

- **Cuts**: a jump in the frame's colour layout from one sample to the next.
  Cuts between two similar angles of the same scene are missed.
- **On-screen text**: high-contrast edge density in horizontal bands.
  `text_changes_per_10s` counts how often that changes. Word-by-word captions
  show as 8 or more changes per 10 s with text on screen 40% of the time or more.
  Thin, animated kinetic text (TOGI) is under-counted.
- **Zooms**: steady scale change across the frame without a cut.
- **Picture**: brightness, contrast, black and white points, saturation,
  warmth, green to magenta, and the average shadow and highlight colours.
- **Speech**: from YouTube's own captions. Each caption line is split into
  words with even timing, and only words inside the scanned window count.
- **Hook**: the words in the first 3 seconds, and flags for question, number,
  "you", "me", money and warning words. Song lyrics can set these flags.
- **loop_gap**: how different the last frame is from the first (low means the
  clip loops cleanly).

## Things to know before trusting a number

- **Speech pace in older records.** Records with `speech_v` 1 counted caption
  lines, not words. Those were renamed `caption_lines_per_minute`, and
  `words_per_minute` was recomputed only where the transcript was short enough
  to cover the whole clip. Records with `speech_v` 2 are correct.
- **Dropped scans.** Scans that an ad cut short, and age-restricted videos that
  would not play while signed out, are left out.
- **Clip age.** Older clips have had longer to collect views. `age_days` goes
  with more views for 6 of 11 creators, so it is in the report beside every
  other attribute.
- **Sample size.** Every claim in `hits_vs_flops.md` gives n. With 20 clips,
  a rank correlation under about 0.45 can be chance. Trust an attribute that
  points the same way for several creators more than one strong result.

## What points the same way across creators

From `hits_vs_flops.md` (11 creators with 8 or more Shorts, |rho| of 0.3 or more):

- Faster speech goes with more views for 5 of 9 creators, and with fewer for none.
- Text on the first frame: 4 of 10 more, none fewer.
- A clip whose end does not match its start (higher `loop_gap`): 4 of 11 more, none fewer.
  This argues against making clips loop, but it may only mean that clips with more happening do better.
- A cut in the first 3 seconds: 3 of 10 more, none fewer.
- Longer clips: 3 of 11 fewer, 1 more.

## Still to add

- Instagram reels for Adam Yu, the Tren Twins, Luc Bongiovanni and Hybrid TG,
  and Michael's own reels (`mine: true`). Instagram does not list a profile's
  reels when signed out, so this needs a burner account signed in to the
  browser. Michael's main account is never used to browse other creators.

## Story judgements

`story_judgements.json` scores each of the 232 Shorts from 1 to 5 on promise
(does the opening set up a question or stakes), payoff (does what follows
deliver on it), value (does the viewer learn or get something) and share
(would someone send it to a friend). The same scores are in the learning-set
clips as `judge_promise`, `judge_payoff`, `judge_value` and `judge_share`.

They come from a fresh judge that saw only shuffled titles and the first 420
or so characters of each transcript, with no view counts, no rankings and no
creator names. 50 clips have no speech or only song lyrics, so they were scored
from the title alone.

An earlier set of scores, made by a judge that had seen each creator's best and
worst titles, showed a link between share or payoff and views. That link
disappeared once those clips were dropped, so the earlier scores were replaced.

Result, within creators (11 creators with 8 or more Shorts): blind story scores
do not go with views. The median rank correlation is near 0 for all four
scores (promise +0.01, payoff +0.14, value -0.08, share +0.08), with no
consistent direction, and with each creator's top and bottom 3 dropped as
well. The two judges agreed closely (rank agreement 0.62 to 0.79), so the
scores themselves are steady. Opening text alone does not explain why one of a
creator's clips beats another.
