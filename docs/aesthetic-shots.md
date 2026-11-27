# Aesthetic gym shots: flex, pose and physique moments

Use this when a scene calls for the physique to look its best: a pose, a pump
check, a flex between sets, a before and after, or a reveal at the end of a
story. Keeping Michael in frame is only the starting point. These shots are
mostly made with light and angle when filming, then finished in the edit.

Creative choices are still Michael's. Offer these as options for the moment he
names, and do not add them on your own.

## Where this comes from (27 Nov 2026)

12 YouTube videos were measured frame by frame in the browser, and frame grids
were made of their flex moments.

| video | views | what it is |
|---|---|---|
| Breathedivinity-style fan edits (4) | 12K to 50K | dark gym edits in the brand's clothes |
| "aesthetic body flex" and "Eternal pump" | 2.9M, 27K | one slow pose take, letterboxed |
| "BEFORE & AFTER (1 Hour Body Transformation)" | 7.5M | same body, flat light vs top light |
| "How I make CINEMATIC gym videos" | 1.9M | shot list tutorial, on-screen text |
| "How to Film Cinematic Gym Videos as a Solo Filmmaker" | 620K | shot list tutorial, on-screen text |
| David Laid 3 year and 6 year transformations | 60M, 10M | chronological clips and photos to music |
| "DAVID LAID - Outside" gym motivation edit | 3.3M | fan montage |

Breathedivinity's own Instagram and TikTok could not be opened signed out, so
the brand's own posts are not in this sample. These are small samples: treat
the numbers as a description of this look, not as rules.

## The five things that make it look aesthetic

1. **One hard light from above, dark everywhere else.** This is the biggest
   single difference. The 7.5M before and after shows the same body: "before"
   is flat, even, bright light (low contrast), "after" is a dark room with one
   light overhead, so every muscle casts a shadow below it. The flex Shorts sit
   at 6 to 11% average brightness with true blacks. When filming: stand right
   under one ceiling light, turn others off or move away from windows, and keep
   the background dark. No edit can add this later.
2. **Low angle, close, with something in the foreground.** The camera sits at
   waist or bench height looking up ("makes you look powerful", per both
   tutorials). Fan edits frame the shoulder, arm or back tight, often with a
   blurred shoulder, plate or rack edge in front of the lens. Phone: use the
   2x or 3x lens and step back rather than the wide lens up close, which
   distorts.
3. **Slow movement or held poses, not reps.** The flex moments are between
   sets: a slow lat spread, a shirt pulled up, an arm turned under the light,
   looking down. The 2.9M flex Short is a single 15 s take with no cuts at all.
   Film at 60 fps (or 120) so it can play at half speed without stutter.
4. **A dark, low-colour grade.** Saturation drops to about 0.07 to 0.10 (close
   to black and white) on the pure flex clips and about 0.3 on the clothing
   edits, with crushed blacks (black point 0 to 2%) and slightly warm
   highlights against cool or neutral shadows. The tutorials push teal into the
   shadows.
5. **Cuts on the music, then one held shot.** The fan edits cut every 1.3 to
   1.5 s (about 42 cuts a minute) through the build, then hold on the best
   pose at the drop. David Laid's 6 year video changes picture every 1.7 s, on
   the beat, for almost 5 minutes. The motion edit holds 12 s on one shot
   before the first cut.

## Shot list to give Michael before filming

From the two tutorials and the fan edits, one of each per scene:

- **Wide**: sets the place and shows the full movement.
- **Medium**: shows the exercise clearly.
- **Close-up**: the detail (hands on the bar, chalk, a vein, a muscle under the light).
- **Low-angle**: from below, makes him look powerful.
- **B-roll**: plates going on, the setting, walking in.
- **Beauty shot**: a slow, moody pose under the light, filmed for slow motion.

When a planned reel has a physique moment, give him this list beside `shoot-list`, with the light from point 1.

## In the edit, with the tools there are today

| technique | how |
|---|---|
| Punch in on a pose, or crop tight on a muscle | `reframe --from A --to B --zoom 1.2 --y 0.4` (1.1 to 1.3, or ask for more) |
| Hide a jump between two poses | punch in on the second one, same command |
| Dark, low-colour look | `ref-fetch` a reference edit, then `look-make NAME --reference <that file> --footage <his clip>`, then `look-preview` to check and `look-use NAME` |
| Cut the build on the beat, hold at the drop | `music-add`, then `music-snap` to move cuts onto beats; leave the hero pose as one long clip |
| Before and after in one clip | `add-source` the old clip, then the new one with the same pose; match the framing with `reframe` so only the body changes |
| Check the result against a reference | `ref-compare` |

## Not built yet (say so if asked)

- **Slow motion and speed ramps on a clip.** `bake.py` can change a whole
  file's speed, but there is no edit command to slow one part of the timeline.
  For now, slow it in Resolve by hand after `build`, or bake a slowed copy and
  `add-source` it.
- **Letterbox bars** (the cinematic black bars on the 2.9M flex Short) and film
  grain or glow. These can be done in Resolve, or added later as an effect.
- **Judging the light.** Nothing checks whether a shot has top light. Look at
  a `ref-sheet` frame and say so if the shot is flat and evenly lit, since
  that is the one thing the edit cannot fix.
