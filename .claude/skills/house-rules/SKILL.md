---
name: house-rules
description: Use when Michael corrects how something was cut or sets a standing preference, such as "that's too tight", "always add captions", "stop cutting my breaths", "less sound effects from now on", "I always shoot vertical" or "remember that for next time". Also read the rules before any first cut.
---

# House rules: corrections that stick

A correction should only have to be made once. When he corrects something, fix
the edit in front of you **and** save the lesson, in the same turn.

## Before any first cut or autopilot run

Run `uv run stylebrain rules` and read it. Settings are applied by the tools on
their own. The notes are in his words and only you can follow them: check your
plan against each one before cutting.

## Saving a correction

1. If a setting covers it, set it:
   `uv run stylebrain rule pause_min_gap 0.45`
   - `pause_min_gap`, `pause_air`: how hard pauses are tightened ("too tight"
     means raise `pause_air` or `pause_min_gap`; "too slow" means lower them)
   - `cut_retakes on|off`, `captions on|off`
   - `style NAME`, `look NAME`: what a first cut aims for
   - `frame 1080x1920`: his frame size for captions and exports
   - `sounds_per_minute`, `sound_gain`: how much sound design, and how loud
2. If no setting fits, save a note in his words:
   `uv run stylebrain rule-note "never cut the breath before a heavy pull"`
3. Tell him in one line what was saved, so he can object:
   "Saved as a house rule: pauses under 0.45s are left alone."

A one-off ("just for this video") is not a rule. If you cannot tell, ask once.
A flag on a command still wins over a rule for that one run.

## Changing your mind

`uv run stylebrain rule NAME --clear` goes back to the default.
`uv run stylebrain rule-note --remove N` drops a note. When a new correction
contradicts an old note, remove the old one and say so.

The rules live in `library/house-rules.json` on this computer and are not
committed, because the notes are his. They do not follow him to another
computer unless he copies the file.
