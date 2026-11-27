---
name: sound-effects
description: Use when Michael wants sound effects on his edit or in his sound library, such as "add whooshes on the cuts", "put a pop on the captions", "add sound design", "download some impact sounds" or "use my plate drop here".
---

# Sound effects

Sounds sit on the edit list like overlays: they follow cuts and can be
undone. At `build` they are mixed into one audio file, levels set and lowered
under speech, and placed on audio track 2 in Resolve.

## The library

`library/sfx/` on this computer (not committed). Each sound has tags, a
licence and where it came from. `uv run stylebrain sfx-list` shows it.

- Starter set, made here: `uv run stylebrain sfx-basics` (pop, click, whoosh, thud, riser).
- His own recordings are the best ones (plates, chalk, bar drops):
  `uv run stylebrain sfx-add FILE --tags hit,plates --licence own`.
- From Openverse: `uv run stylebrain sfx-fetch "whoosh" --tags whoosh --count 5`.
  This takes CC0 sounds by default. `--licence any` or `--licence cc0,by`
  widens it. Listen to what came down and remove weak ones from the folder
  and `index.json`.
- Any other file: `sfx-add FILE --tags ... --licence WHAT_IT_IS --source URL`.

The licence is recorded and shown, never enforced. What to use where is
Michael's decision; do not refuse or lecture. The one built-in rule: for a
video he says is a **paid ad**, add `--ad` to `sfx-auto` and `sfx-place`,
which keeps to his own, made-here, CC0 and public-domain sounds, and ask him
for his guidance on that video.

## Placing

- Automatic: `uv run stylebrain sfx-auto --transcript CLIP.words.json`
  puts a whoosh on cuts that are at least 2.5 s apart, a pop where a graphic
  appears, and a whoosh on zooms, 6 dB lower where someone is speaking.
  It prints every sound it placed: relay the list and the count.
  `--on cuts` or `--on overlays,zooms` limits it. Running it again replaces
  its earlier sounds and keeps hand-placed ones.
- By hand: `uv run stylebrain sfx-place TAG --at TIME --gain -12`.
- Remove: `sfx-remove NAME`, `sfx-remove auto`, or `sfx-remove all`.

Start quiet (the defaults). Sound effects that are noticed as sound effects
are too loud. After `build`, ask him to listen once through and say which to
drop or turn up.
