---
name: learn-what-works
description: Use when Michael wants to know which editing or storytelling attributes go with his clips performing well, wants the virality score tuned to his results, or shares analytics, such as "what's working on my channel", "learn from my analytics", "which hooks do best" or "retrain the score".
---

# Learning which attributes go with performance

A small model, run locally, compares what each clip is like with what happened
to it. The clip data lives in `library/clips/`, which is not committed: his
analytics stay on his computer.

## Building the set

For each clip, two things are needed: attributes and a result.

1. **His own clips.** In YouTube Studio: Analytics, Advanced mode, Content tab,
   filter to Shorts, add the metrics Views, Average percentage viewed, Shares
   (and "Stayed to watch / Swiped away" if offered), then Export as CSV.
   `uv run stylebrain clip-import FILE.csv --subscribers N`.
   Then for each id it lists: get the video file and a transcript, and
   `uv run stylebrain clip-add ID --video CLIP.mp4 --transcript CLIP.words.json --judge '{...}'`.
2. **Reference clips.** `ref-fetch` the short, transcribe it, then
   `clip-add ID --video ... --transcript ... --views V --subscribers S --about "creator, title"`.
   Views divided by subscribers is the fair comparison across channels.
3. Make the judgements (`score --questions`) the same way for every clip:
   read the transcript, look at a `ref-sheet`, answer each from 1 to 5. Judge
   before looking at the view count, so the result does not colour the judgement.

`uv run stylebrain clip-list` shows the set.

## Learning

`uv run stylebrain learn` (target `reach`, views over subscribers), or
`--target retention` / `--target kept` with his analytics, and `--mine` to use
only his clips.

Relay, in this order:

1. The verdict line. If it says "no better than guessing the average", stop
   there: nothing was learned, and say so.
2. The top few attributes that are steady, as "in these clips, X went with
   doing better". Skip ones marked unsteady.
3. The suggested score weights, as a suggestion. Do not change `score.py`
   weights unless he says to.

## Honesty rules

- Under 12 clips it will not run. Under 30 it is a rough read. Say the count.
- It finds what goes together, not what causes what. A creator with a big
  following and fast cuts makes fast cuts look good. Mixing many creators
  blurs this; his own clips are the cleanest test.
- The way to prove an attribute is to test it: post two similar clips that
  differ in that one thing, and compare.
- Reference clips teach what works in the niche; only his analytics teach
  what works for his audience. Weight his own results more as they grow.
