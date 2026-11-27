---
name: sound-effects
description: Use when Michael wants sound effects on his edit or in his sound library, such as "add whooshes on the cuts", "put a pop on the captions", "add sound design", "download some impact sounds" or "use my plate drop here".
---

# Sound effects

Sounds sit on the edit list like overlays: they follow cuts and can be
undone. At `build` each kind of sound (whoosh, pop, hit, riser) is mixed into
its own file, levels set and lowered under speech, and placed on its own audio
track from A2 up, so he can mute or turn down one kind in Resolve. The build
report says which kind is on which track.

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
- It holds back by default: at most 8 automatic sounds a minute
  (`--per-minute N`, 0 for no limit). When there are more moments than that it
  keeps story beats and the first moment of the opening, then zooms, graphics
  and cuts, spread through the video, and says how many it left quiet.
- Story beats: when the script or he names the turn and the payoff, pass their
  times with `--beats 12.5,31`. Each gets a hit and is kept first.
- `--on cuts,overlays,zooms,risers` also runs a riser into each zoom that has
  a clear run-up. Offer it; it is not on by default.
- By hand: `uv run stylebrain sfx-place TAG --at TIME --gain -12`.
- Remove: `sfx-remove NAME`, `sfx-remove auto`, or `sfx-remove all`.

Start quiet (the defaults). Sound effects that are noticed as sound effects
are too loud. After `build`, ask him to listen once through and say which to
drop or turn up.
