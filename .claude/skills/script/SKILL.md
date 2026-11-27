---
name: script
description: Use when Michael wants a video planned or written before he films, or wants better hooks, such as "write me a script", "what should I say", "give me hook ideas", "plan this video", "rewrite this hook", "help me find the story" or "prep me for this shoot".
---

# Writing a script: story first, then the hook, then the lines

The look of a video never rescues a weak story. So write in this order and
do not skip ahead: find the story, then the hook, then each line. Michael
films; the words are suggestions he can change. Read the reference creators
and pillars in project memory (storytelling-hooks-research) before writing.

## 1. Find the story (before any line is written)

Ask the three whys. Take the topic he gave ("I'm deadlifting 405 for reps")
and ask "why does that matter to you?" three times, one at a time, and wait
for each answer. The first answer is safe, the second is real, the third is
raw. Save his raw answer word for word: it is usually the hook or the last
line. Do not invent the raw answer for him. If he is not around, write the
script with a marked gap: `[RAW LINE: ask Michael why this matters]`.

Then write the story in five short lines, one for each story question
(`uv run stylebrain script-check --questions` lists them: `want`,
`stakes`, `question`, `causes`, `payoff`):

- **Want:** the goal with a number or a deadline.
- **Stakes:** why it might fail, or what it costs if it does.
- **Question:** what the viewer will wait to find out.
- **Causes:** the beats, each joined to the last by "but" or "therefore".
- **Payoff:** what we will see that answers the question, and what is
  different at the end.

If any line is empty, the video is a format without a story. Say so and offer
a way to add the missing piece (a number to chase, a real doubt, a turn)
before writing anything else. A rep counter or a day count only shows the
stakes; it is not the story.

## 2. Write the hook

Run `uv run stylebrain hooks` for the hook types, then
`uv run stylebrain hooks --examples TYPE --niche NICHE` for proven YouTube
examples of a type with their views and first spoken line (the researched
library is `library/hooks/patterns.json`; niches: powerlifting, running, food,
guns, lockpicking, fpv). Pick types whose examples did well in his niche, and
copy the shape of their first line, never their words. What the top openings
share: the first spoken line is the title nearly word for word, a number is in
the first five words, and the bar to clear is said before the attempt.

Then climb the hook ladder (Robert McKeaveney's method, in
`library/hooks/playbooks/mckeaveney.json`). Start from the plain value line
("How to bench more"), then add layers one at a time: a bold claim, the payoff
they'll get, a number, then credibility. Credibility for Michael means his real
proof (All-American, Army powerlifting team, his actual lifts), never invented
numbers. `uv run stylebrain hooks "LINE"` shows which layers a line has and
which it could add. Every hook must make the viewer ask a question the video
answers.

Offer **three** hooks, each a different type, each with:

- the spoken line (under 15 words, the first word means something, no
  greeting, no "in this video"),
- the on-screen text (3 to 8 words, readable at a glance, not a copy of the
  spoken line),
- what is on screen in frame 1 (movement already happening, his face close,
  or the payoff itself).

Check each one: `uv run stylebrain hooks "SPOKEN LINE" --text "ON-SCREEN TEXT"`.
It prints the hook's type; a line that fits no type usually does not hook.
Every hook must promise something the script pays off on screen. Never write
a hook the video cannot deliver.

To rewrite the hook of a clip that already exists, read its transcript, run
`hook-check` on it, then offer three rewrites the same way, using only what
the clip actually shows. Each rewrite can be cut from words he already said
(name the time) or needs a new line recorded (say so).

## 3. Write the lines

Shape it as hook, buildup, payoff. The hook asks the question, the buildup keeps
them watching by strengthening that question (every beat raises the stakes or
adds a doubt), and the payoff answers it. When a posted reel has a retention
graph, `uv run stylebrain retention '[[0,100],[3,70],...]'` names which of the
three lost people.

A borrowed format is fine and often best: take one that has already gone viral,
add his topic or a twist, and make it his. For a reel that should lead somewhere
(coaching), open on the entertaining clip and transition into the lift or the
offer. A rewatch reason (a challenge they can just miss, like "pause when the bar
hits depth") makes average watch time longer than the reel.

One spoken line per line of text. Rules for each line:

- It earns the next one. If a line could be cut without the next line making
  less sense, cut it.
- Short. One idea per line, about 14 words or fewer on average.
- Concrete. A weight, a time, a count, a place. "190 g of protein" over
  "a lot of protein". Use only Michael's real numbers; ask if you do not
  have them.
- Joined by cause. "But" and "therefore", not "and then".
- Doubts answered where they come up. When a viewer would think "that only
  works because...", say it and answer it on the next line.
- A new question about two thirds through, before the first one is fully
  closed, so the viewer stays for the end.
- A call to action only comes after the value, and it asks for more of the same
  ("for more cues like this, follow").
- The end pays off the hook on screen, then stops. For a short, the last line
  can lead back into the first so the replay feels seamless. No "so yeah".
- For long-form, a re-hook (a question, a reveal or a change of scene) at
  least every 60 seconds. Write each key point as a sentence that makes
  sense on its own, so it can be cut into a short later.

Mark where each effect would go and which beat it serves: stakes, turn or
payoff. An effect that serves none is left out.

## 4. Check it

Save the script to a text file and run:

`uv run stylebrain script-check SCRIPT.txt --story '{"want": 4, "stakes": 4, "question": 5, "causes": 4, "payoff": 5}'`

Score the five story questions honestly, 1 to 5 each, from reading the script
as a stranger would. The story must reach 20 of 25 before the script is
offered as ready; under that, fix the story, not the wording. Fix every note
the check prints, or say why it does not apply.

## What to give Michael

1. The story in five lines, with the raw line in his words.
2. Three hooks: spoken line, on-screen text, frame 1.
3. The script, one line per line, with effect marks and their beats.
4. A shot list of what to film for the payoff (the rep, the scale, the
   reaction). A video with no filmed payoff rarely travels.
5. The script-check result and the story score.

Keep the language his: blunt, funny where it fits, no hype words. Never
claim results he has not got.

## Series

For a recurring format ("Mid at both?", "30 days to X"), keep the episode
number and the stakes line ("Day 12: 385 to go") in the series notes in
project memory, and open each episode on the last one's open question.
