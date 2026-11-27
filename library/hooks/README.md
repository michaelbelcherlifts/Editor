# Hook library

Researched hook patterns and video ideas for Michael's niches (powerlifting with
powerlifting humour, running, food, guns, lock picking, FPV drones).

- `patterns.json`: 18 hook types (the keys of `story.HOOK_TYPES`). Each has why it
  works, how the best openings do it (`opening`), lines written for Michael
  (`for_michael`, with `[weight]`-style gaps for his real numbers), the niches it
  fits, and proven YouTube examples with views and the first spoken line.
- `ideas.json`: video ideas built on those patterns, in the format
  `stylebrain idea-import` reads. Each names its hook type and the videos that
  prove the format in `note`.

- `playbooks/mckeaveney.json`: Robert McKeaveney's rules for reels that reach
  millions (hook ladder, hook / buildup / payoff, reading retention, borrowing
  formats, baseline, what doesn't matter), with his reels as sources and how
  each fits Michael.

Use:

```
uv run stylebrain hooks                                  # types, with how many proven examples each
uv run stylebrain hooks --examples challenge             # proven examples of one type, most viewed first
uv run stylebrain hooks --examples --niche guns          # all types in one niche
uv run stylebrain hooks "Can I run a sub 6 mile?" --text "182 lb vs 1 mile"   # its type and problems
uv run stylebrain retention '[[0,100],[3,70],[10,62],[20,55]]'               # which part lost viewers
uv run stylebrain idea-import library/hooks/ideas.json --source trend          # into the content plan
```

Views are a snapshot from 2026-11-27 (some rounded from search results, such as
60M). They show a format can travel, not that it will for Michael: his own
analytics decide that once they are connected. To refresh, run
`data/hook-research/youtube_hooks.js` in the desktop browser pane on youtube.com
(instructions at the top of the file), then update `patterns.json`.

Not copied: no creator's name, characters, look or catchphrases. A format (a
"how many does it take" ladder, a versus, a bet) is used with Michael's own
angle: the lifter who can run and hates the term hybrid athlete. Nothing frames
content around competing at worlds.
