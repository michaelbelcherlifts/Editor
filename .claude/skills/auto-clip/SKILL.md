---
name: auto-clip
description: Use when Michael wants short reels cut out of a long recording, such as "clip this vlog", "find the best moments", "make reels from this video", "auto-clip my long video", "what in here would make a good short" or "give me clips with scores".
---

# Auto-clip a long recording into scored reels

Story before style: a clip is only worth cutting if it has something to find
out and an answer inside it. The finder only proposes; the full score, with
your judgement of story, promise and payoff, decides the order.

## Steps

1. **Find.** `uv run stylebrain clip-find VIDEO --count 10 --out exports/clips/NAME`
   - Uses `VIDEO.words.json`, or the YouTube `.en-orig.vtt` beside it (word
     times included), else transcribes. For a long recording on a slow
     computer, say transcription will take a while.
   - `--skip-intro 30` leaves out a channel intro; `--min`/`--max` set the length (15 to 60 s).
   - Writes `candidates.json` and `brief.txt` (every candidate's timed lines and the questions).
2. **Judge.** Read `brief.txt`. For each candidate decide, as a viewer who has
   never seen the long video:
   - `story`, `promise`, `payoff`, `value`, `share`, `trend` (1 to 5; `uv run stylebrain score --questions` lists them)
   - `needs_context`, `undelivered`, `mid_sentence` (true/false). Be strict about context: inside jokes,
     "he", "that" or "this" with nothing to point at, ad reads.
   - `cold_open`: `[start, end]` source seconds of the strongest line (12 s or less), when opening on it beats the
     natural start. It plays first and is taken out of the body.
   - `start` / `end`: move the edges to a whole sentence, or to end on the payoff.
   - `hook_text`: 8 words or less, saying what the viewer will get, not a summary.
   - `skip`: a reason, for a candidate that does not stand alone.
   Save `judgements.json` in the same folder: `{"c01": {...}, "c02": {...}}`.
   With many candidates, one agent per clip (or per batch) can judge in parallel; give each the brief
   lines for its clips and the questions, and merge their answers. Keep the batch size modest, since
   agents use his plan's limits, and say how many agents were used.
3. **Cut.** `uv run stylebrain clip-cut exports/clips/NAME`
   For each candidate: cold open, pauses over 0.5 s tightened, framed 9:16 on the
   subject, captions, the text hook on top, rendered at 1080x1920 and -14 LUFS,
   measured and scored on the full rubric. Then ranked, repeats marked, and
   `review.html` written (video, score by part, the one fix, every cut, framing).
   `--no-render` plans and scores without video; `--only c01,c03` redoes some.
4. **Report.** Lead with the top clips: score, length, the hook and the one fix.
   Attach or link `review.html`. Say plainly which parts were judged by you and
   that the score ranks clips against each other; it does not predict views.

## Rules

- Never post anything. Approved clips can go to the content calendar as drafts.
- Every cut is listed (`cuts` in `review.json`, "Every cut" on the sheet); relay them when asked.
- Do not add effects, music or sound unasked. The hook text and captions are part of the clip format.
- Downloaded YouTube videos are practice material only.
- Read the house rules first (`uv run stylebrain rules`) and follow them.

## Limits

- Framing follows faces, then motion. Two people talking can leave one out of
  the 9:16 frame; the framing notes say so.
- YouTube caption word times are close but not frame-exact; a whisper
  transcript is better for the final cut.
- Scene detection misses some jump cuts, so the joins in the edit are counted
  as visual changes too.
