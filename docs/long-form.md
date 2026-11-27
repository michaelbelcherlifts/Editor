# How fitness YouTubers build a 10 to 20 minute video

Studied November 2026 for the long-form format (`formats.py`, `longform.py`,
the `long-form` skill). Sources: the 15 latest uploads of Jeff Nippard, Chris
Bumstead, Sam Sulek, Noah Anderson, Jun Yuh, TOGI (Shane Stoffer) and Alex
Eubank, read from YouTube's own pages in the built-in browser: length, views,
chapters and description. 37 videos of 8 to 25 minutes had chapters. Seven
transcripts were read for the opening, each chapter's first lines and the
ending (Jeff x3, CBum, Noah x2, Jun; one more each from CBum, Sam and TOGI
would not load a transcript).

These describe what these channels do. They are not proof of what holds
viewers; that needs Michael's own retention graphs once he posts long-form.

## The numbers

| | Jeff | CBum | Noah | Jun | Sam | All 37 |
|---|---|---|---|---|---|---|
| Typical length | 12 to 20 min | 12 to 18 | 12 to 24 | 9 to 40 | 20 to 45 | |
| Opening before chapter 1 (median) | 40s | 98s | 92s | 67s | 166s | **79s** (quartiles 50 to 122) |
| Chapter length (median) | 122s | 136s | 134s | 90s | 170s | **131s** (three in four under 175s) |
| Chapters per video (median) | 7 | 7 | 6 | 7 | 4.5 | **7** |
| Talking pace (words a minute) | 190 to 204 | 175 | 169 to 193 | 244 | | |

TOGI runs 25 to 250 minutes with no chapters on most uploads: a different
format (event docs), not a model for 10 to 20 minutes.

## What the openings do

Every opening read stated a premise with a number or a question inside 30
seconds, then promised what comes later.

- **Jeff, "I Cut The Number Of Sets I Do In Half"**: "For the last 100 days, I
  cut all my workouts in half ... Would I lose muscle? Well, in this video,
  I'll break down exactly what I did, what the science says, and what happened
  to my physique." Premise, doubt, a three-part map. First chapter at 0:20.
- **Jeff, "How To Look Enhanced Without Steroids"**: opens on the question,
  then strangers judging his subjects (proof on screen), then at 1:10 an open
  loop: a doctor blood tests everyone "later in the video". That answer lands
  at 12:06 of 16:04 (75%).
- **Jun Yuh**: contradiction then a number: not naturally gifted, yet "$13
  million in 15 months. How?"
- **Noah, "I trained months for this... and then this happened"**: a
  flash-forward to the turn ("Event update. The Chicago River Swim has been...")
  cut off mid-sentence, then the goal with last year's time. The cancellation
  itself lands at 13:54 of 20:44 (67%).
- **CBum, "This Chest Workout Won Me 6 Olympias"** (4.2M views): opens "What is
  up, YouTube? Today I'm going to be taking you through..." The weakest opening
  read, carried by authority in the title. Michael cannot lean on six Olympias
  yet; his openings should do the work.

## What the middles do

- **A chapter about every 2 minutes**, each opening with its own small question
  ("So, after 100 days of low volume workouts, what happened? Did it work?").
- **List videos** (Jeff's 7 exercises, CBum's numbered workout) give each item
  its own chapter: claim, proof, demo, next.
- **Experiment videos** run why, then the plan, then the science, then results,
  and hold the result to the last quarter.
- **The turn sits past halfway**: Noah's cancelled swim at 67%, Jeff's blood
  tests at 75%, his 100-day results at 73%.
- **Workout and vlog footage** leaves gaps with no talking (CBum 6, Noah 8 gaps
  of 15s or more). Explainers have none.

## Pitches and endings

- Jeff pitches his app in the last minute, after the results. Noah's sponsor sits
  at about 10:00 of 20:44, Jun's at 6:00 of 10:01: at a chapter break, after a
  payoff. Nobody pitched in the opening.
- Endings are short: payoff, one pitch, "see you in the next one".

## What did best (views)

- Jeff: experiments and tested claims with a number ("Peptides Are Insane" 20M,
  "What Every Body Fat % Actually Looks Like" 18M, "How Much Muscle Did I Gain In
  365 Days?" 8.3M).
- CBum: authority workouts ("This Back/Chest Workout Won Me 6 Olympias" 4.2 to
  4.3M) beat the life-advice videos (0.3 to 0.9M).
- Noah: a plain struggle ("Running at 200lbs sucks", 0.22M, his best of 15).
- Sam: the weight in every title of a daily series ("Day 64 - 365 lb Incline Bench").

## What this means for Michael

His Minecraft background (no pauses, strong exposition) fits the explainer and
experiment formats: fast talk, a premise up front, a map of what is coming.
Story beats the look, so:

1. Pick the shape before filming: `uv run stylebrain outline experiment|list|challenge|day|explainer --minutes 14`.
2. Say the premise with a number or a question in the first 30 seconds, and
   promise one thing the viewer only gets later.
3. A chapter every 2 minutes or so, each opening with its own question.
4. Hold the main answer (the total, the meet result, the blood work) for the last 40%.
5. Pitch coaching after a payoff, never in the opening. End within 90 seconds of the payoff.
6. Powerlifting fits the challenge shape best: a meet or a PR attempt has a
   date, a number and a real way to fail.

These targets are coded in `longform.TARGETS` and checked by `longform-check`.
