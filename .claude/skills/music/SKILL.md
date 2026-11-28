---
name: music
description: Use when Michael wants music under an edit or cuts timed to it, such as "put this song under it", "cut on the beat", "sync the lifts to the music", "start the song at the drop", "turn the music down" or "take the music off".
---

# Music and cutting on the beat

One music track sits under the whole edit. It plays through cuts and does not
move when clips do. Which song to use is his choice (see the licensing note in
the sound-effects skill: recorded, never refused; ask for his guidance on paid ads).

## Adding it

`uv run stylebrain music-add SONG.mp3 --start 31.5 --gain -21`

- `--start` is where in the song the edit begins. To open on the drop, find the
  drop's time in the song and start there, or a bar before it.
- `--gain` is the level. -21 is the default and sits clearly under talking; -10 to -8 for a montage with
  no speech. Michael wants the music consistent: one song at one steady level. It dips by only about 2 dB (never more than 3)
  while he speaks and holds there across the gaps between lines (`--no-duck` for no dip at all).
  After an export, check the level between lines: the voice should sit well above the music (6 dB or more)
  and the music should hold within about 2 dB.
- It reports the tempo and whether the pulse is clear. If it says there is no
  clear pulse, say so: beat times on that track are a rough guide only.

`music-remove` takes it off. Running `music-add` again replaces it.

## Cutting on the beat

1. `uv run stylebrain music-beats` lists the beats on the timeline and how far
   each cut is from one. Read it first; often only a few cuts are off.
2. `uv run stylebrain music-snap --transcript CLIP.words.json` moves each cut
   back onto the beat before it by trimming the end of the clip before the cut,
   by at most 0.3s (`--max-trim`). It never trims into a word when the
   transcript is given, and says which cuts it left alone and why.
   `--every 2` or `--every 4` uses every second beat or the bar, which suits slower cutting.
3. Relay the lines and the new length. The edit gets shorter by what was trimmed.

Cutting on every beat is a creative choice: offer it, do not do it unasked. For
a lift montage, the usual ask is the hit of each lift on a beat; that is a move
of the clip, not a trim, so do it by hand with `cut` and check with `music-beats`.

## Where it ends up

- `export` mixes it in: lowered under his voice, faded over the last second,
  and the whole mix set to posting loudness.
- `build` puts it on its own audio track in Resolve, already cut to length,
  levelled and lowered under speech, so he can mute or replace it there.

## Limits to say out loud

Beat finding is proven only on test tracks with a steady pulse. The one try on
a real song was inconclusive (the pulse read as unclear). So on every new song:
say what `music-add` reported about the pulse, and before `music-snap` have
him listen to an `export` or check two or three beat times against the song by
ear. If the beats are off, cut by hand to times he gives.
