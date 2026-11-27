---
name: long-form
description: Use when Michael wants a long YouTube video (8 minutes or more) planned, cut or checked, such as "plan a 15 minute video", "make this a YouTube video", "add chapters", "is my long video paced right", "set this up for YouTube" or "write the description timestamps".
---

# Long-form YouTube: 16:9, chapters, a re-hook every two minutes

Read `docs/long-form.md` first: it is what the reference channels do and why.
Story comes before the look here too (project memory: feedback-story-over-visuals).
Creative choices stay Michael's: offer chapter titles and cuts, do not make them.

## Before filming

1. Find the story with the `script` skill (the three whys, want, stakes, question).
2. Pick the shape and print a plan: `uv run stylebrain outline` lists them,
   `uv run stylebrain outline challenge --minutes 15` prints the chapters with
   start times and the job of each. Powerlifting meets and PR attempts fit
   `challenge`; "I tried X for 90 days" fits `experiment`; tips fit `list`.
3. Give him the first 30 seconds word for word: the premise with a number or a
   question, and one open loop ("you'll see the total at the end").

## Cutting

1. `uv run stylebrain format longform` once per project. Build, reframe and
   export then use 1920x1080 (`longform-4k` for 3840x2160). If the clips were
   framed for vertical, run `reframe --auto` again.
2. Cut as usual with the talk-edit skill. Long-form keeps more air than a reel:
   leave silences over a lift or a scene that moves.
3. Add chapters where each section starts: `uv run stylebrain chapter 1:10 "Why I tried it"`.
   Chapters are pinned to the moment, so later cuts move them with it.
   `chapter --remove "Why I tried it"` takes one out.
4. `uv run stylebrain build`: the timeline is set to 16:9 and each chapter is a
   blue marker. Relay the report; a chapter on a cut moment is listed as a problem.

## Checking

1. `uv run stylebrain longform-check --transcript FILE.words.json --payoff 11:30`
   (`--video cut.mp4` also flags shots over 45s; `--cta 9:40` marks a pitch).
   `--payoff` is when the main question is answered; read it from the
   transcript if he has not said. Relay every line marked `!` first; the rest
   are things to look at, not rules.
2. `uv run stylebrain chapters --out description.txt` prints the block for the
   YouTube description and says whether YouTube will show it (at least 3, the
   first at 0:00, each 10s or more).
3. Captions: long-form does not burn captions in. Write an SRT for upload with
   `uv run stylebrain srt --transcript FILE.words.json --out captions.srt`.
4. Export with `uv run stylebrain export`; it renders at the format's frame.

## What not to claim

The 16:9 timeline setting and chapter markers are only tested against the
stand-in Resolve until a real build confirms them. The targets come from six
other creators, not from Michael's retention; say so when quoting them.
