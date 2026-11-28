---
name: trial-reels
description: Use when a reel is finished and needs its Instagram Trial Reel versions, or Michael asks about trials, such as "make the trial versions", "5 copies for trial reels", "which trial won", "test the hook", "post this as a trial" or "what wins in my trials".
---

# Trial reels: five versions of every reel

Every finished reel becomes five versions: **v1 the control** (the reel as made)
and four that each change **one** thing. Michael posts them as Instagram Trial
Reels (shown to non-followers only), the results score each version, and only the
winner is shared to his main feed. Each version is a hypothesis, scored like a
trade. Read `docs/trial-reels.md` for the research and its sources.

Nothing is posted by this. He posts in the app, or says "post v2 as a trial"
(`trial-publish`). Never post on your own initiative or on a schedule.

## Steps

1. `uv run stylebrain trial-suggest FINAL.mp4 --reel NAME --post pN --hook "LINE|SECOND LINE"`
   drafts the spec: control, hook text, opening (starts on the second shot,
   moved past any transition blur), length (cuts part of the longest shot), pace
   (1.1x). Then **edit the spec**:
   - Hooks are Michael's call. Offer lines from his transcript or the hook
     library (`library/hooks/`), true to the video, never invented numbers.
     Tag each with its hook type (`"tags": {"hook_type": "stakes"}`) so
     `trial-learn` can say which types win.
   - If the reel already has text on frame 1, set `cover` to a box over it
     (x, y, w, h in pixels, full width works best) and `y` so the new line sits
     in the same place.
   - Length: cut dead time (a walkout, a pause), never the payoff or a sentence.
   - Write a one-line hypothesis for each.
2. `uv run stylebrain trial-make SPEC --check --share-on DATE` renders
   `library/trials/NAME/`: the five files (named `NAME-v2-hook-text.mp4` and so
   on, the label also in the file's comment tag), `trial.json`,
   `first-frames.jpg` and `post-sheet.md` with the posting times. `--share-on`
   is the calendar day the winner should reach the feed; the trials run a day
   apart and end two days before it.
3. Look at `first-frames.jpg` and say what you see (old text showing through, a
   blurred first frame, text on the person). Watch the joins of length and
   opening versions: a jump in the music is worth saying.
4. Hand him the sheet. `trial-copy NAME FOLDER` copies the set to the Drive
   finals folder for his phone.
5. As he posts: `trial-result NAME v2 --url LINK`. About 24 hours after the last
   one, read every version **at the same age** from Trial insights:
   `trial-result NAME v2 --hours 24 --views --reach --skip-rate --avg-watch --shares --saves --follows`.
6. `trial-score NAME` ranks them for the reel's goal (reach: skip rate, watch
   share, shares; follows: follows, saves, then the rest) and says clear, lean
   or too early. He shares the winner to everyone in the app; record it with
   `trial-promote NAME vN` (his pick stands even if the scores favoured another).
7. `trial-learn` across every reel: how often each kind of change beat its
   control, by hook type, and by posting order (a fall in later versions means
   Instagram is holding back near-copies; then post fewer versions or change
   more of the opening).

## Rules

- One change per version (`trial-make` refuses two). Same caption, hashtags and
  hour for all five unless the version is the caption test.
- A caption-only version is the same video: Instagram may limit it as
  previously shared. Prefer opening, hook and length changes.
- At most 5 trials a day across all reels (`trial-schedule` warns).
- Auto-share stays off (manual), so two versions never both reach followers.
