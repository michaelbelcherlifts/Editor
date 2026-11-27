# Cinematic edits: what Blaze Kennedy does

Use this when Michael wants a reel to feel cinematic rather than talky: a
military or event montage, a meet day, a training block set to music, or a
behind-the-scenes "how I made this". Creative choices stay Michael's: offer
these as options for the moment he names, and do not add them on your own.

## Where this comes from (27 Nov 2026)

Blaze Kennedy (Instagram @blazekennedy, about 36K followers, "U.S. Army
Officer | Videographer") films West Point and Army events on Sony A7 IV and
A1 II and edits in DaVinci Resolve. Seven of his reels were played in the
browser pane signed out and measured about ten times a second (cuts, picture,
on-screen text), with frame grids of each.

| reel | likes | length | what it is | cuts a minute | median shot |
|---|---|---|---|---|---|
| "Where's my popcorn?" (Apr 2025) | 92K | 13 s | phone clip with a joke caption, hard cut to dark cinematic diving and night shots | 14 | 4.1 s |
| "now this one is easy" (Apr 2026) | 8.8K | 36 s | tutorial: Magic Mask on a skydiver, then Zoom Blur on the background | 27 | 0.9 s |
| "SEND ME!" (Aug 2026) | 5.2K | 21 s | parade and flyover montage, 2.39 strip in a vertical frame | 51 | 1.0 s |
| "have you found your purpose?" (Aug 2026) | 3.4K | 18 s | Army-Navy game, voice-over words as spaced titles | 17 | 2.9 s |
| "Speed ramps are my most used effect!" (Jul 2026) | 2.1K | 29 s | tutorial: speed ramp in Resolve on a gymnast | 10 | 3.5 s |
| "Would you dare jump?" (Jul 2026) | 1.3K | 21 s | parachute jump montage on the beat | 31 | 1.2 s |
| "Who brought tanks to Arrakis?" (Nov 2026) | 1.2K | 57 s | widescreen armour film in a desert grade | 50 | 1.05 s |

Seven reels is a small sample. His best reel by far (92K) is the one with a
story: "cadet said he was gonna learn to film" over flat phone footage, then
the payoff of the cinematic shots. The pure montages sit at 1K to 5K. That
fits the creator study: story beats editing style.

## What he does

1. **A lo-fi setup, then the cinematic payoff.** The 92K reel opens on 3
   seconds of bright, flat phone footage with Instagram's own plain caption
   (white text on a dark box), then hard cuts to dark, high-contrast shots
   (brightness falls from 36% to under 10%). The contrast is the hook.
2. **Widescreen inside the vertical frame.** Most reels put a 2.39:1 or 16:9
   picture across the middle of a 9:16 frame with black above and below
   (35 to 79% of the frame is black bars). It reads as "film". It also makes
   the picture small on a phone, so use it for montages, not for talking.
3. **Spaced title words from the voice-over.** "TELL ME / HOW / LIFE / MOVE /
   WEST / ACROSS THE SEA / LAND / CALL": one or two words at a time, tall
   condensed capitals with very wide letter spacing, a worn print texture and
   a soft shadow, centred over the lower half of the picture. Large but quiet.
4. **Plain captions in tutorials.** "IN JUST", "FIRST,", "CMD + R.": one or
   two words, bold white capitals, no box, no outline, no coloured word, no
   bounce, just below the middle. This is the opposite of the busy
   highlighted-word caption look that reads as auto-generated.
5. **Cuts on the beat, about once a second,** with a burst of four or five
   cuts inside one second as an accent (27.2 to 28.2 s in the tank reel). The
   slower, emotional reel holds shots for about 3 seconds.
6. **Speed ramps** (his "most used effect"), done in Resolve with the retime
   curve, plus zoom and position keyframes.
7. **Blur transitions:** a sideways motion smear between clips, and a zoom
   blur on the background behind a masked subject.
8. **Hand-drawn burst marks** around the subject on a hit (white chalky
   dashes radiating out from the gymnast).
9. **Grade:** crushed blacks (black point 0 to 1%), low saturation, either
   teal and cold or a warm sandy desert look, with golden-hour backlight,
   haze and silhouettes in camera. He often opens on a texture close-up
   (tank road wheels) before the wide shot.

## With the editor

| technique | how |
|---|---|
| Spaced title words | render `spaced_title` with the voice-over's word timings (`words`) or `text`, place it as an overlay |
| Plain captions | render `plain_captions` (or use it as the caption treatment in a first cut) |
| Widescreen strip in a vertical reel | `letterbox` template with `ratio` 2.39 and `slide 0` held for the whole reel, or export a 16:9 edit with `--fit fit` |
| Whip between two shots | `transition --at CUT --kind whip` (`--left` to flick the other way) |
| Zoom blur into a shot | `transition --at CUT --kind zoom` |
| Speed ramp | `speed --from A --to B --speed 0.5 --ramp 0.3` |
| Burst marks on a hit | render `burst` with `x`, `y` on the subject, place it on the frame of the hit |
| Cuts on the beat | `music-add`, then `music-snap` |
| Dark, low-colour grade | `look-make` from a reference, see `docs/aesthetic-shots.md` |

## Not built yet (say so if asked)

- **Text behind the subject** (the jets flying in front of "THE SEA") and a
  **zoom blur on the background only**: both need a moving mask of the person,
  which the editor cannot make yet. Resolve's Magic Mask does it by hand.
- **The lo-fi to cinematic hook** is a filming and story choice, not an effect.
  Suggest it in `script` when Michael has a "learning to" or "behind the
  scenes" angle.
