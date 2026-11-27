# Video Editor: project requirements document

As of 27 November 2026, for Michael. The living copy, where comments and edits go, is [here](https://claude.ai/artifact/LKmK73Gqo36oEewdVXKjfS). This file is a snapshot of it.

## 1. Summary and vision

This project builds Michael a free, local AI editing and content system that turns raw footage into videos people keep watching, and grows his personal brand across Instagram, TikTok and YouTube. This document audits everything said and decided in the project up to 27 November 2026 (UTC) and sets the requirements for what comes next.

**The product in one paragraph.** Michael opens one project folder ("Style Brain", the Editor repository) in Claude Code beside DaVinci Resolve Studio. He talks through an edit instead of making cuts by hand, hands over a link or screenshots of an effect or style he likes and gets it rebuilt on his own footage, asks for explainer animations, and can leave raw footage for an automatic first cut. Every video is judged story first: hook, reason to keep watching, payoff, then pacing and visuals. Around the editor sits a content system that learns from his analytics, scouts trends, proposes ideas and hooks, cuts long recordings into scored clips, prepares posts for every platform, and tracks what turns into clients and brand deals.

**Goals, in his words and order of weight**

1. Edit by talking: "I want to cut this XYZ, or I want this effect here on the timeline."
2. Copy what works: "take a YouTube video link that I give you, maybe some screenshots of an effect that I find cool in another video, and you should be able to implement that." This includes colour grading.
3. Full automation like the creator setups: raw footage in, a near-final draft out, with him as director.
4. Virality over decoration: "if there's no story that goes along, no good hook, no reason for viewers to continue to watch, there is little benefit to having good visuals. So it needs to be balanced."
5. A systematic, technical approach: measure attributes of videos, test them against performance with machine learning, and go deep. "This should not be a one-page paper."
6. Grow reach and convert it: "let's build a kick-ass personal brand", with value in every video, a high volume of reels, and tracking of client and brand-deal conversions.

**Who it is for.** One user: Michael (@michaelxbelcher on Instagram, 18.3K followers on 27 Nov 2026). He is an Army powerlifter, All-American at 516 DOTS, and sells coaching at nospotter.com. He said he will be "the only person ever using this", so the system is built for his machines and his workflow, not for distribution.

**What success looks like**

- A raw recording becomes a postable short with one command and one round of notes.
- Any effect or style he points at is on his timeline the same session, and reusable by name afterwards.
- Every clip carries a part-by-part score that he trusts, because it has been tuned against his own results.
- He posts a planned, high volume of reels and other formats each week without the editing being the bottleneck.
- Follower growth, sends and saves per reach, and coaching or brand enquiries trend up, and the system can say which attributes went with that.

**Out of scope for now.** Posting anything automatically. Paid services or API spend. Publicly framing content around a world championship goal. Distributing the tool to other people.

## 2. Constraints and standing rules

These rules apply to every workstream. A requirement that conflicts with one of them is wrong.

| # | Rule | Source |
| --- | --- | --- |
| C1 | **Free and local.** Everything runs inside Claude Code on Michael's Claude subscription with free local tools. No API keys that bill per use, no paid services (Higgsfield, Gemini, ElevenLabs and similar), no cloud GPU. Do not quote per-video dollar costs. | Michael, 27 Nov: "their setups are completely free and within the Claude Code app, minus their monthly subscription" |
| C2 | **Never post automatically.** The system scores, suggests, prepares and schedules drafts. A person presses post. | Michael, 27 Nov: "They will never post automatically, at least for now" |
| C3 | **Michael owns copyright and commercial-use calls.** Do not block on licences for media used in his videos (songs, sound effects, downloaded references). Note the licence where useful. Paid ad videos are separate and wait for his guidance. | Michael, 27 Nov, after talking to his lawyer |
| C4 | **Code in the public repo still needs a compatible licence.** Ideas may be borrowed from unlicensed or non-commercial projects, code and skill files may not be copied. | Agreed 27 Nov (Content Principles, Real SFX, One Take) |
| C5 | **Story before style.** Reviews, scores and suggestions check story and hook first. Every suggested effect names the story beat it serves (stakes, turn or payoff). Effects with no beat are flagged as decoration. | Michael, 27 Nov |
| C6 | **Creative choices are Michael's.** Offer options; do not add cuts or effects that were not asked for. Autopilot is the one exception, and it must list every cut and every sound it placed. | Repo rules (CLAUDE.md) |
| C7 | **Non-destructive editing.** Never cut, trim or move clips on a Resolve timeline in place. Change the edit list, then build a new timeline. Never delete or rename his timelines. One change per command so each can be undone. | Repo rules; Resolve scripting limits |
| C8 | **Honest reporting.** After a build, relay the report. Say plainly what is untested, approximate or failed. Models must refuse to draw conclusions from too little data (under 12 clips no run, under 30 a rough read). | Repo rules; learning layer design |
| C9 | **Private data stays private.** Analytics, reference downloads, the clip dataset and any voice model stay on his machines and out of the public repo (`library/clips/` and `references/` are git-ignored). | Build thread, voice research |
| C10 | **Burner account only for trend scouting.** Never automate browsing on his main Instagram account. Browse lightly, at human pace. | Agreed 27 Nov |
| C11 | **Worlds stays private.** Do not frame content publicly around competing at worlds until he says so, possibly when his total reaches 900 kg. | Michael, 27 Nov |
| C12 | **Niche is background.** The niche will develop on its own. The editor's job is to make whatever he posts hook and hold viewers. | Michael, 27 Nov |
| C13 | **AI voice is disclosed where required and is only ever his own voice.** Keep Chatterbox's watermark. Show him every script line before it is spoken. | Voice research, 27 Nov |
| C14 | **Depth over summaries.** Research on creators and videos is a systematic, second-by-second study that feeds a dataset, not a short write-up. | Michael, 27 Nov |

**Working agreements**

- Claude merges its own pull requests into `main` once tests pass. Work happens on branches with pull requests. (Michael, 27 Nov: "You can merge pull requests on your own. You don't need me.")
- Run `uv run pytest` after any code change. Tests must not need Resolve; they use the stand-in in `tests/fake_resolve.py`.
- Claude may find its own routes around download roadblocks ("take it as a green light to develop your own strategies"), using his own computer and connection. It does not bypass the security controls of the cloud workspace.
- He said yes to downloading reference clips on his PC (27 Nov). Downloads stay local and are never uploaded or posted.

**Environment**

| Item | Value |
| --- | --- |
| Editor | DaVinci Resolve Studio, latest paid version (21.1 or later ships the official Claude connection) |
| Main machine | MacBook Pro, M4 Max. Memory not confirmed (every M4 Max has at least 36 GB). **Not yet linked to this project** |
| Second machine | Windows PC, linked, folder `Documents\AI Editor`. Graphics card unknown |
| Repository | github.com/michaelbelcherlifts/Editor (public). Python, `uv`, ffmpeg, Playwright |
| Platforms | Instagram Reels today. Adding TikTok, YouTube long-form and YouTube Shorts |
| Where things can run | Live Resolve editing only on the Mac in the Claude desktop app. Cloud threads cannot reach Resolve or YouTube video. The built-in browser on his computer can open YouTube and Instagram and measure frames without downloading |

## 3. Current state

The editor's code is built and merged through eight pull requests, but none of it has run against real Resolve on the Mac yet. The content system around it (analytics beyond import, trends, calendar, posting, voice) is not started.

### 3.1 Built and merged to `main`

About 3,450 lines of Python in `src/stylebrain/`, 44 commands, 8 skills, tests on every pull request through GitHub Actions (101 passing at the last report).

| Capability | What it does | Where | Proven on |
| --- | --- | --- | --- |
| Edit list engine | Keeps the edit as data: cut, move, swap, overlays, every version saved, undo | `edl.py`, `store.py`, PR 0 (first push) | Tests |
| Transcript tools | Find a spoken phrase, cut it, find and tighten pauses, detect repeated-phrase retakes | `transcript.py` | Tests |
| Talk-through editing | Skill and rules for editing by conversation | `talk-edit` skill, `CLAUDE.md` | Stand-in for Resolve only |
| Resolve builder | Builds the edit as a new timeline and reads every clip back to verify | `resolve_builder.py` | Stand-in only |
| Render engine | HTML animations to transparent ProRes clips | `render.py`, PR 1 | Tests, cloud |
| Animation templates | Caption pop, lower third, callout, running captions, muscle diagram | `templates.py`, `anatomy.py`, `animate` skill | Tests, cloud |
| Effect library | Save a named effect recipe, render it, place it by name | `effects.py` | Tests |
| Baked effects | Punch-in zooms and speed changes with ffmpeg | `bake.py` | Tests |
| Reference study | Download a link, frame sheets, motion timing, palette, side-by-side compare | `reference.py`, `copy-effect` skill, PR 2 | Generated clips; first real run in progress on the PC |
| Style profiles | Measure cut rate, opening, speech pace, picture, sound; save by name | `style.py`, `copy-style` skill, PR 3 | Generated clips |
| Colour looks | A LUT that moves his footage toward a reference, preview image, applied at build | `look.py`, `colour-look` skill, PR 4 | Generated clips; Resolve apply on stand-in |
| Autopilot | One command: retakes out, pauses tightened, look, captions, build, review | `autopilot.py`, `autopilot` skill, PR 5 | End to end on a generated clip with the stand-in |
| Cut review | Timestamped notes on how a cut differs from a saved style | `review.py`, `review-cut` skill, PR 5 | Tests |
| Transcription wrapper | Runs local mlx-whisper or whisper for word timings; subtitles export | `transcribe.py`, PR 5 | Stand-in only |
| Virality score | 0 to 100 on seven parts with a story gate and penalties | `score.py`, PR 6 | Tests; two real shorts scored from transcripts (77 and 70, partial) |
| Learning layer | About 30 attributes per clip, private clip dataset, local ridge model, suggested score weights | `learn.py`, `learn-what-works` skill, PR 7 | Made-up data with a planted pattern |
| Analytics import | Reads a Meta Business Suite (Instagram) or YouTube Studio CSV; targets reach, sends, saves, likes, retention | `learn.py`, PR 8 | Column names unverified against a real export |

### 3.2 Research delivered

| Output | Content | Link |
| --- | --- | --- |
| Build plan | Architecture, Resolve limits and routes around them, eight phases | [AI editing companion for DaVinci Resolve: build plan](https://claude.ai/artifact/MsbS66XueJzZxRDQRue27S) |
| Story and hooks research | Story structure, cross-niche lessons, hook types, long-form to shorts, the score rubric, niche notes, editor feature ideas | [What makes videos and shorts hook viewers](https://claude.ai/artifact/WyEkvYkg3vor27P96ojFeo) |
| Creator styles, first pass | Nine creators, one or two videos each, five formats to copy, JSON profiles | [Fitness creator styles](https://claude.ai/artifact/Vx8RNz16GkqHFBGFgN2gVo), project files `creator-styles/` |
| Tools verdict | Five video skills, voice cloning, disclosure rules, sound effects, Content Principles | [Back-pocket tools verdict](https://claude.ai/artifact/47Aw2WG6QMSpznvY49VhUe) |
| First recreation test | Graphics-only rebuild of a 13M-view bench short, plus two scores | Project files `style-brain/youtube-tests/` |

### 3.3 In progress when this was written

| Work | State | Owner thread |
| --- | --- | --- |
| First real-machine run on the Windows PC | Three bench shorts downloaded at 1080x1920. Editor being installed, tests run, clips measured and scored with video, one text effect recreated | Build thread |
| Sound effects layer | Approved and started: sound layer in the edit list, auto-placement, tagged local folder, fetch script | Build thread |
| Deep creator study | In-browser frame-by-frame analyzer built. About 72 of 126 YouTube Shorts analysed (MekLuvin, CBum, most of Vince). Still to do: Alex Eubank, Luka, Tren Twins, Sam Sulek and TOGI openings, Adam Yu reels, dataset pull request, hits versus flops, rebuilt report | Creator styles thread |

### 3.4 Not verified on real hardware

- Anything against real Resolve: building a timeline, frame accuracy of cuts, overlays on V2, transparency import, the LUT on the first node, audio following video.
- Real mlx-whisper transcription on the Mac.
- `ref-fetch` on a real YouTube link from the Mac (the PC download worked through yt-dlp).
- The Instagram export column mapping.
- The first-run checklist in `docs/SETUP.md` has ten unticked items.

### 3.5 Planned in the build plan but not built

| Gap | Why it matters |
| --- | --- |
| Reframing and vertical crops with face tracking | In his first ask ("readjust video framing"). Needed to cut long-form into 9:16 |
| More than one source clip per project | Real shoots have many clips, b-roll and angles. Today a project starts from one clip |
| Carrying over work done by hand on the previous timeline | A rebuild drops hand-made changes |
| Reading on-screen text from references (OCR) | Needed to copy caption wording, position and timing, and to measure graphics spacing |
| Fusion comps, transitions, live (not baked) zooms and speed ramps | Baked effects cannot be adjusted in Resolve afterwards |
| Markers as a feedback channel and saved house rules | The plan's loop for teaching Claude his taste |
| On-body muscle highlight with pose tracking | The second explainer option he was shown |
| Hook check, story beat map, clip finder, series tracker | Feature ideas from the story research |
| One-prompt setup on a fresh Mac (plan Phase 7) | Lower priority now, since he is the only user |

## 4. Workstreams

There are fourteen workstreams. Three are needed before a real video can go through the editor (P0), four make each video better (P1), and seven build the content system around it (P2 and P3).

| Priority | Meaning |
| --- | --- |
| P0 | Blocks the first real video. Do now |
| P1 | Raises the quality and reach of every video. Do next |
| P2 | Content system. Start once real videos are flowing |
| P3 | Later. Design now only where it shapes earlier work |

### W1. Prove the editor on real hardware (P0)

**Goal.** Take one of Michael's real recordings from raw file to a finished timeline in Resolve on the Mac, and fix whatever breaks.

**Requirements**

- W1.1 Complete every item of the first-run checklist in `docs/SETUP.md` on the Mac and record the result of each.
- W1.2 Confirm the Resolve version and that the official Claude connection reads the playhead, markers and transcript.
- W1.3 Fix builder defects found against real Resolve. Each fix gets a test in the stand-in so it cannot return.
- W1.4 Confirm local transcription with mlx-whisper on the M4 Max and record speed for a 10 minute clip.
- W1.5 Finish the Windows PC run already under way and fold its failures into fixes, since it is the editor's first run on any real machine.
- W1.6 Setup works from one sentence ("set up Style Brain") with no terminal knowledge.

**Acceptance criteria**

- A cut made by voice lands on the right frame in a new timeline, and the build report says "all checked".
- An animation imports with transparency, a look shows on the first colour node, and audio follows video.
- Autopilot runs on one real clip and produces a timeline he can watch.
- `README.md` and `docs/SETUP.md` no longer say "not yet run" for anything that was run.

**Dependencies.** The MacBook linked to the project, or Michael following the setup guide himself. Resolve open on that Mac.

**Owner.** Build thread.

### W2. Make the editor ready for real shoots (P0 to P1)

**Goal.** Close the gaps between the engine that exists and how he actually shoots: many clips, vertical output, hand tweaks, and a way to teach it his taste.

**Requirements**

- W2.1 Projects hold more than one source clip, with b-roll and second angles on their own tracks. (P0)
- W2.2 Reframing: a 9:16 crop that follows his face or the lift, with punch-in scale and position per clip, from free local tracking. Key action stays inside the middle 4:5 so the Reels grid crop keeps it. (P1)
- W2.3 Hand work is kept: before a rebuild, read what can be read from the current timeline and warn about anything that would be lost. (P1)
- W2.4 Markers work both ways: he drops a marker to say "here", and review notes come back as markers. (P1)
- W2.5 House rules: his corrections are saved and applied on the next first cut, so the same mistake is not repeated. (P1)
- W2.6 Transitions, and zooms and speed changes that stay adjustable in Resolve where the scripting allows, with baking as the fallback. (P2)
- W2.7 Retake detection beyond exact repeated phrases. (P1)
- W2.8 A rendered export of the final cut for posting (9:16, 1080x1920, platform-safe loudness), plus a self-check that looks at frames of the render. (P1)

**Acceptance criteria**

- A shoot with at least three clips becomes one edit with b-roll placed by voice.
- A horizontal recording yields a vertical cut where he stays in frame for the whole clip.
- A correction given once ("never zoom on a sip of water") is not needed a second time.
- A hand-made change survives the next rebuild or is named in a warning before it.

**Dependencies.** W1 for anything that touches Resolve.

**Owner.** Build thread.

### W3. Sound layer (P0, in progress)

**Goal.** Sound effects placed automatically on the moments that matter, because "sound effects are crucial to making videos pop".

**Requirements**

- W3.1 A sound layer in the edit list. Today overlays are picture only.
- W3.2 Auto-placement from what the edit list already knows: a hit on scene-changing cuts, a pop when a caption or graphic appears, a riser into a zoom.
- W3.3 Sounds duck under his voice and sit on their own audio tracks in Resolve so any one can be muted.
- W3.4 Restraint by default: sounds go on story beats (hook, turn, payoff), with a cap per minute that he sets.
- W3.5 A local tagged library folder: type (whoosh, pop, impact, riser, plate clank), length, loudness, licence note. His own gym recordings come first.
- W3.6 A fetch script that fills the folder from Openverse, plus optional local generation with earshot. Licence is recorded, not used as a filter (rule C3). Fetching runs on his machine, since the cloud cannot reach Openverse.
- W3.7 Music: place a track, find its beats, and offer cut-on-beat. Not yet started or specified.
- W3.8 The build lists every sound it placed, like Autopilot lists cuts.
- W3.9 Borrow Real SFX's ideas, not its code (rule C4).

**Acceptance criteria**

- One command adds sounds to a cut, and the report lists each with its time and reason.
- In Resolve the sounds are on separate tracks, in sync to the frame, and quieter under speech.
- Setting the cap to zero removes them all; undo restores the previous version.
- Michael judges the result by ear on one real video. Claude cannot hear audio.

**Dependencies.** W1 for placement in Resolve. Ten minutes of his own gym recordings.

**Owner.** Build thread.

### W4. Reference study and creator dataset (P1, in progress)

**Goal.** Know, from data, what the creators he admires do second by second, and feed that to the model.

**Requirements**

- W4.1 For each of the nine fitness creators, 15 to 30 or more videos, hits and flops relative to that creator's normal views.
- W4.2 For every video: hook wording and type, the first 3 seconds, cut times and shot lengths, caption style and timing, zooms and effects, music and sound cues, story beats, payoff, calls to action, grade and framing.
- W4.3 One record per clip in the agreed format (`clip-schema.md`): numeric attributes, views and subscriber or follower count, judgements made before looking at views.
- W4.4 Full timelines stored in the repo under a data folder; per-clip records go to the private learning set.
- W4.5 Findings come from hits compared with flops inside each creator, not from impressions.
- W4.6 The report is rebuilt from the data, and each creator's style file is refreshed so `copy-style` and `colour-look` can use it.
- W4.7 Add the storytelling references on the same footing: Noah Anderson, Jun Yuh, TOGI, Good Good, Young Dalt, Japes Golf, Solid Heaston, Luc Bongiovanni, Hybrid TG.
- W4.8 Bring in the two borrowed pieces: a local transcript fallback for captionless reels, and reading on-screen text from keyframes.
- W4.9 Instagram reels are measured as well as YouTube Shorts, since Reels are his platform.

**Acceptance criteria**

- At least 150 clip records in the learning set, at least 12 per creator, each with a result.
- The model runs on the set and reports which attributes are steady and which are not.
- The rebuilt report states sample sizes beside every claim.
- `uv run stylebrain style-show <creator>` works for all nine.

**Dependencies.** The built-in browser on his computer. TubeAlfred has only a handful of credits left, so it is not a bulk source.

**Owner.** Creator styles thread.

### W5. Story, hook and script tooling (P1)

**Goal.** Turn the story research into checks and tools the editor runs on every video, so a good look never hides a weak story.

**Requirements**

- W5.1 Hook check: dead air before the first meaningful word, no text on frame 1, slow first visual change, a promise the clip never pays off, and whether the ending loops.
- W5.2 Three new measured checks in the score: average sentence length, seconds until the first useful point, and the longest held shot. Proposed on 27 Nov and not yet confirmed by Michael.
- W5.3 Story beat map for long-form: label hook, setup, escalation, low point and payoff, and flag any stretch over 60 seconds with no new question.
- W5.4 A "but / therefore" pass that finds "and then" stretches in narration.
- W5.5 A script skill written in our own words: story first, then the hook, then line by line (each line sells the next, a new question about two thirds through, concrete numbers, objections answered where they arise).
- W5.6 A pre-shoot "three whys" prompt that saves the raw answer as a hook or ending line.
- W5.7 A series tracker that keeps the episode count and stakes line for recurring formats.
- W5.8 Every effect suggestion in review, autopilot and animate names its story beat (rule C5).
- W5.9 Hook options: for any clip, offer three rewritten hooks by type, with the on-screen text for each.

**Acceptance criteria**

- `review` on a clip with a slow start names the problem and the second it happens.
- The score output shows the three new checks, and a clip with nothing to find out is capped at 55.
- Given a topic, the script skill returns a hook, a full script and the on-screen text, and the script scores at least 20 of 25 on story by the rubric.
- A 10 minute transcript comes back with labelled beats and flagged dead stretches.

**Dependencies.** None for the transcript-based parts. W6 for tuning weights.

**Owner.** New thread. The story research thread delivered the research and is finished.

### W6. Analytics and learning (P1)

**Goal.** A score and a set of recommendations tuned to his audience: "use machine learning to take these attributes and test them against virality."

**Requirements**

- W6.1 Import his Instagram insights export and confirm the column mapping on a real file.
- W6.2 Build his own clip set: for each posted reel, the video file, a transcript, attributes, and results (reach, views, sends, saves, likes, follows, and average watch time read from the insights screen, since the export has none).
- W6.3 Fit the local model on reference clips and on his own, separately and together, and report what is steady. Never claim a cause.
- W6.4 Suggest new score weights. Change them in `score.py` only when he says so.
- W6.5 A per-video diagnosis in his terms: where retention drops, whether the video gives value, whether there are enough calls to action.
- W6.6 A recurring analytics read (weekly) that says what worked, what did not, and what to try.
- W6.7 Add YouTube and TikTok results as he starts posting there.
- W6.8 Later: live analytics through each platform's free official interface, in place of manual exports.
- W6.9 Track follower growth per post, so "value drives follows" can be tested.

**Acceptance criteria**

- His export loads with no hand edits, and every reel in it is matched to a clip record.
- With 30 or more of his clips, `learn --mine` gives a verdict line, steady attributes and suggested weights, or says plainly that it learned nothing.
- After reweighting, the score ranks his past reels closer to how they actually did than before. The before and after are shown.
- A weekly read arrives without him asking.

**Dependencies.** His export from Meta Business Suite (asked for on 27 Nov, still waiting). His original video files for past reels. W4 for the reference set.

**Owner.** Build thread built the code. A new thread should own the analysis and the recurring read.

### W7. Auto-clipping with virality scores, and long-form (P1)

**Goal.** "We're recording clips, and then you will orchestrate agents to automatically create clips, and we'll give them a virality score." A long recording goes in; ranked, ready-to-review shorts come out.

**Requirements**

- W7.1 A clip finder that proposes 15 to 60 second moments from a long recording, each with a question and its answer inside the clip.
- W7.2 Each candidate is cold-opened on its strongest line or payoff, tightened, captioned, reframed to 9:16, and given a text hook.
- W7.3 Each candidate gets the full part-by-part score, with penalties for needing outside context or starting mid-sentence.
- W7.4 Several agents work candidates in parallel, each producing its own cut and score. One pass ranks them and removes near-duplicates.
- W7.5 Output is a review sheet: ranked clips, scores by part, the one fix that would raise each score, and a rendered preview of each.
- W7.6 Nothing posts. Approved clips move to the calendar (W11) as drafts.
- W7.7 Every cut is listed, as Autopilot does.
- W7.8 Long-form YouTube edits use the same engine: a beat map (W5.3), re-hooks every 30 to 60 seconds, chapter suggestions, and title and thumbnail ideas decided before recording.
- W7.9 A recording guide for shoots, so long-form is filmed to cut into shorts: standalone sentences, restated topics, a filmed payoff, a centre-safe frame.

**Acceptance criteria**

- A 20 minute recording yields at least five scored candidates with previews in one unattended run.
- Every candidate makes sense with no context from the long video.
- The top-ranked candidate is one he would post after at most one fix, on three recordings in a row.
- The run reports how many agents it used and what each cut.

**Dependencies.** W1, W2.2 (reframing), W5 (hook and story checks), the score. Multi-agent runs use his subscription's usage limits, so batch size must be adjustable.

**Owner.** New thread.

### W8. Animation and effect library (P2)

**Goal.** A growing set of animations and effects that look like the videos he admires, each tied to a story beat.

**Requirements**

- W8.1 Real-link test of copy-effect: give a YouTube link with a timestamp, get the effect on his clip, close enough that he would use it. Three rounds of fixing at most.
- W8.2 Templates from the creator study: TOGI-style word-by-word kinetic type with one coloured word, one-to-three-word mid-frame captions, a title bar held for the whole video, a numbers or macros end card, the "clipper" layout, a rep and day counter.
- W8.3 Fix the known flaw from the first recreation: a card must not cover running captions.
- W8.4 Explainer set: muscle diagrams for the main lifts (squat, bench, deadlift and accessories), form cues with arrows and angles on a freeze frame, tempo counters, comparison charts.
- W8.5 On-body highlight with free pose tracking, labelled as approximate.
- W8.6 Lemo OpusCar as a reference library of code-made film styles for single explainer beats. Skip its three image-generator styles.
- W8.7 One look per creator saved as a named colour look, from the measured profiles.
- W8.8 A cartoon character of his own (Claude Animation Base approach) only if he asks for a mascot.
- W8.9 Not planned: One Take (non-commercial licence), Collage B-roll (paid Gemini). The looks can be rebuilt as our own templates if he wants them.

**Acceptance criteria**

- "Show the muscles for a squat" works with no new build.
- Each new template has a preview clip in the project files and a one-line note on which story beat it serves.
- A side-by-side image of reference and remake exists for every copied effect.

**Dependencies.** W1 for transparency in Resolve. W4 for caption measurements. Michael checks the content of every explainer; Claude picks muscles from general knowledge.

**Owner.** New thread. The tools evaluation thread delivered its verdicts and is finished.

### W9. Voice clone and voiceover (P2)

**Goal.** His cloned voice narrates teaching videos over real footage and animations, from a script built on the story rules.

**Requirements**

- W9.1 Chatterbox, run locally on the M4 Max. Qwen3-TTS only if the PC turns out to have an NVIDIA card.
- W9.2 One clean voice sample (30 seconds to 5 minutes) recorded on his usual microphone.
- W9.3 Flow: script from W5.5, he approves every line, the clone reads it, transcription aligns it, animations land on cue, a new timeline is built.
- W9.4 Default advice: record the hook in his real voice and use the clone for the teaching middle and pickups.
- W9.5 Disclosure prompts at export: Instagram AI label required, TikTok very likely required, YouTube not required for one's own voice. A paid partnership label is still needed on brand deals.
- W9.6 The voice model and sample never enter the repo or shared folders. The watermark stays.
- W9.7 Only his voice, ever.

**Acceptance criteria**

- A pilot on the bench setup video: one version with the clone, one with his real voice, for him to compare.
- Generation speed on the Mac is measured and written down.
- No script line is spoken that he did not approve.

**Dependencies.** Five to ten real videos through the editor first (agreed timing). W5.5 script skill. The Mac linked.

**Owner.** New thread, started later.

### W10. Trend scout and market research (P2)

**Goal.** A steady read on what is working now in his space: "research of what's trending in my niche, gives ideas that are currently trending", including jokes and trending audio.

**Requirements**

- W10.1 A burner Instagram account that Michael creates. Never his main account (rule C10).
- W10.2 Train its feed first: a day of following the studied creators and liking fitness and powerlifting content.
- W10.3 A few short sessions a day in the built-in browser at human pace. No round-the-clock bot.
- W10.4 Each noted reel is logged: link, creator, views and likes, hook wording, format, audio, joke or trend, and why it is working.
- W10.5 Also use the low-risk signals: the trending-audio arrow, and the Trends section of his Professional dashboard.
- W10.6 Each session ends in a short trend report: hooks, jokes, audio, and ideas tagged ready to edit, each with a story arc.
- W10.7 The same for YouTube and TikTok trends where a free route exists.
- W10.8 Market research on demand: what to make videos on, who is growing and why, gaps nobody is filling.
- W10.9 Trend fit in the score stops being a neutral 3 and uses the latest report.

**Acceptance criteria**

- A week of sessions with no flag or lock on the burner account.
- Each report has at least five ideas with a hook, a format and a reference link, and takes under two minutes to read.
- At least one idea a week becomes a posted video.

**Dependencies.** The burner account and its login in the built-in browser. A computer left on. Agreed to start after his first few real edits. Risk: Instagram's rules ban automated browsing, so the burner may be flagged.

**Owner.** New thread.

### W11. Content calendar and idea pipeline (P2)

**Goal.** "A content calendar where we're posting an excellent amount of reels", fed by ideas, clips and trends, covering every platform.

**Requirements**

- W11.1 One calendar of planned posts: date, platform, format (reel, short, long-form, carousel, story, photo), topic, hook, status, call to action, score.
- W11.2 An idea backlog fed by trend reports (W10), clip candidates (W7), analytics (W6) and his own notes.
- W11.3 A weekly plan proposed for his approval, with a mix by pillar and a target volume he sets.
- W11.4 Calls to action planned on purpose: which posts point to coaching, which ask for a follow, which ask for comments. Not every post gets one.
- W11.5 Shoot lists: what to film this week so the plan can be met, with the recording guide from W7.9.
- W11.6 Series are tracked across episodes.
- W11.7 Status follows each item from idea to recorded, edited, approved, posted, measured.

**Acceptance criteria**

- He can see the next two weeks in one view and change any item by saying so.
- Each planned item links to its draft and its score.
- At the end of a week, planned versus posted is reported with results.

**Dependencies.** W6, W7 and W10 make it better, but it can start with manual ideas. Open questions: target posts per week, and where the calendar lives.

**Owner.** New thread.

### W12. Images, carousels and stories (P2)

**Goal.** "Edit images and make image carousels for Instagram posts, recommend stories to post."

**Requirements**

- W12.1 Photo edits with free local tools: crop to platform sizes, a colour look matched to his video looks, text overlays in his caption style.
- W12.2 Carousels: a hook slide, one idea per slide, a final slide with a call to action, exported at Instagram's sizes. Built from his photos and from frames of his videos.
- W12.3 Carousels can be made from a video's script or transcript, so one shoot yields a reel and a carousel.
- W12.4 Story recommendations each day: what to post around a reel (behind the scenes, poll, question box, link to coaching), with drafts.
- W12.5 Thumbnails and covers for reels and YouTube videos, decided with the title.
- W12.6 The same story-first rule: slide one is the hook.

**Acceptance criteria**

- A finished reel yields a carousel draft and three story suggestions in one command.
- Exports open at the right size on Instagram with text inside the safe zones.

**Dependencies.** The render engine (exists). W11 for scheduling. His photo library on a linked machine.

**Owner.** New thread.

### W13. Cross-poster and platform packaging (P3)

**Goal.** "We'll post to one, it posts to all of them": one approved video becomes a correct package for Instagram, TikTok, YouTube Shorts and YouTube long-form.

**Requirements**

- W13.1 Per-platform exports: size, length limits, safe zones, loudness, cover image.
- W13.2 Per-platform text: caption, title, description, hashtags, pinned comment, each written for that platform.
- W13.3 Disclosure flags carried with the package (AI voice, paid partnership).
- W13.4 A posting checklist he works through by hand to begin with. Nothing posts on its own (rule C2).
- W13.5 A later step, only when he lifts rule C2: one press publishes to all through each platform's free official interface or the built-in browser.
- W13.6 After posting, the links are recorded so analytics (W6) can match results.

**Acceptance criteria**

- One approved clip produces four packages, each passing that platform's upload checks.
- Posting all four by hand takes him under five minutes.

**Dependencies.** W2.8 (export), W11. Open question: how he wants to press post (by hand, scheduled drafts in each app, or one button).

**Owner.** New thread, started later.

### W14. Brand-deal and client conversion tracking (P3)

**Goal.** Know "how many of these convert to client brand deals".

**Requirements**

- W14.1 A simple private log: enquiry date, source (which post or platform, if known), type (coaching client, programme sale, brand deal), value, outcome.
- W14.2 Tracked links or codes per platform and per post where possible, so nospotter.com visits can be tied to content.
- W14.3 Profile visits, link clicks and follows per post from insights, as leading signals.
- W14.4 Conversions become a target in the learning layer once there are enough of them.
- W14.5 A monthly read: which content types brought clients and deals.
- W14.6 Paid ad videos are tagged, and follow whatever guidance he gives for ads (rule C3).

**Acceptance criteria**

- Every new client or deal in a month has a recorded source or is marked unknown.
- The monthly read names the top three posts by conversions.

**Dependencies.** W6. How he takes enquiries today (site form, direct messages, email) is unknown.

**Owner.** New thread, started later.

### Workstreams at a glance

| ID | Workstream | Priority | Depends on | Thread |
| --- | --- | --- | --- | --- |
| W1 | Prove the editor on real hardware | P0 | Mac linked | Build thread |
| W2 | Ready for real shoots | P0 to P1 | W1 | Build thread |
| W3 | Sound layer | P0 | W1 for Resolve | Build thread (in progress) |
| W4 | Reference study and creator dataset | P1 | Built-in browser | Creator styles thread (in progress) |
| W5 | Story, hook and script tooling | P1 | None | New |
| W6 | Analytics and learning | P1 | His export, W4 | New (code exists) |
| W7 | Auto-clipping and long-form | P1 | W1, W2, W5 | New |
| W8 | Animation and effect library | P2 | W1, W4 | New |
| W9 | Voice clone and voiceover | P2 | 5 to 10 real videos, W5 | New, later |
| W10 | Trend scout and market research | P2 | Burner account | New |
| W11 | Content calendar and idea pipeline | P2 | Better with W6, W7, W10 | New |
| W12 | Images, carousels and stories | P2 | W11 | New |
| W13 | Cross-poster and packaging | P3 | W2, W11 | New, later |
| W14 | Conversion tracking | P3 | W6 | New, later |

## 5. Roadmap and order of work

The order is set by one fact: nothing has touched real Resolve or one of his real recordings yet, so the first milestone is one real video, and everything else is ranked by how much it improves the next video.

1. **Milestone A: first real video.** W1, the multi-clip part of W2, and W3. Done when one of his recordings goes from raw file to a posted reel through the editor. Gate: the Mac is linked or set up by hand.
2. **Milestone B: story-first editing on every video.** W5, the rest of W2 (reframing, house rules, markers), and W4's dataset finished. Done when every cut he makes gets a hook check, a score by part and a review tied to story beats.
3. **Milestone C: the score is his.** W6 with his Instagram export and 30 or more of his own clips. Done when the reweighted score ranks his past reels better than the starting weights.
4. **Milestone D: one recording, many clips.** W7. Done when a long recording yields ranked candidates he would post.
5. **Milestone E: the content system.** W10, W11, W12 and W8 in parallel. Done when a weekly plan arrives with trend-backed ideas, drafts and a shoot list.
6. **Milestone F: scale and conversion.** W9 after five to ten real videos, then W13 and W14.

**What can run in parallel now, without the Mac.** W4 (in progress), W5 (transcript-based), W6 on reference data, the design of W10 and W11, and W12's carousel templates. Only W1, W2 and W3's Resolve placement need the Mac.

**Biggest risks**

| Risk | Effect | Response |
| --- | --- | --- |
| The Mac is not linked | No Resolve test, so everything stays unproven | Ask once, clearly. Meanwhile the PC run finds non-Resolve bugs |
| Rebuilds drop hand work | He stops trusting the tool | W2.3, and the rule: structural passes first, polish by hand after |
| Too little data for the model | False patterns | Refusal thresholds stay (12 and 30). Report "learned nothing" when true |
| The score rewards the wrong things | Clips optimised for a number, not for viewers | Show every part, tune on his results, keep the story gate |
| Burner account flagged | Trend scouting stops | Light, human-pace sessions; dashboard signals as fallback |
| Usage limits on multi-agent runs | Auto-clipping stalls mid-run | Adjustable batch size, saved scripts and local analysis in place of re-thinking |
| Resolve updates change the scripting interface | Builder breaks | Every write is read back; the stand-in tests pin behaviour |
| Platform rules on downloads and automation | Account or access trouble | His call under rule C3; stay local; never the main account |

## 6. Decisions made

All dated 27 November 2026 (UTC), from the project chat and threads.

| # | Decision | Who |
| --- | --- | --- |
| D1 | Build on Resolve's official Claude connection. Do not build a general Resolve connector. Build "Style Brain" beside it | Plan, accepted by Michael |
| D2 | Keep the edit as an edit list outside Resolve and rebuild a new timeline for each change, because scripting cannot cut or move clips in place | Plan, explained to and accepted by Michael |
| D3 | Target full automation: raw footage in, near-final draft out, with him as director | Michael |
| D4 | Everything free, inside Claude Code on his subscription. Paid pieces and per-video cost figures removed | Michael |
| D5 | The core workflow is link or screenshots in, effect or style on his timeline, saved for reuse | Michael |
| D6 | Talking through an edit is the first thing built | Michael asked, plan confirmed |
| D7 | Explainer animations on request, with the animated diagram as the default | Michael asked |
| D8 | Style Brain is a project folder opened in Claude Code, not a separate app | Plan revision |
| D9 | Repository is michaelbelcherlifts/Editor. Claude merges its own pull requests when tests pass | Michael |
| D10 | Looks travel as generated LUTs measured from the reference, not guessed | Plan |
| D11 | Reference creators and their confirmed names: The Tren Twins, Sam Sulek, Chris Bumstead, Luka Hocevar, Vince Wilkinson, TOGI (Shane Stoffer), Alex Eubank, Adam Yu, MekLuvin (Laith Mekdad) | Michael named, thread confirmed |
| D12 | Storytelling references: Noah Anderson, Jun Yuh, TOGI for authenticity, Good Good, Young Dalt, Japes Golf for structure, Solid Heaston for premise, Luc Bongiovanni and The Tren Twins for the "cool guy" persona, Hybrid TG as his inverse | Michael |
| D13 | Output is short-form vertical for Instagram Reels first, then TikTok, YouTube Shorts and YouTube long-form | Michael |
| D14 | Never auto-post, for now | Michael |
| D15 | Story and hook outweigh style in the score: story 25, hook 25, value 15, shareability 10, trend 10, pacing 10, craft 5. Under 10 of 25 on story caps a clip at 55 | Michael asked for the balance; thread set the numbers |
| D16 | Score weights are a starting proposal and get tuned on his analytics after about 20 to 30 posted clips | Thread |
| D17 | Use machine learning on clip attributes against performance, local and free | Michael |
| D18 | The clip record format in `clip-schema.md` is shared by the build and creator threads | Threads |
| D19 | His results come from Instagram, not YouTube. Import from Meta Business Suite | Michael |
| D20 | Creator study must be deep: 15 to 30 or more videos each, second by second, hits and flops | Michael |
| D21 | Reference clips may be downloaded on his PC for private testing. Test outputs go in the project files for him to review | Michael |
| D22 | Measure videos in the built-in browser when downloads are blocked. Skip "watch" skills that send video to paid services | Thread |
| D23 | Niche notes are background. Angle for now: exceptional lifter, good runner, "I hate the term hybrid athlete" | Michael |
| D24 | Worlds is not public. Possible reveal at a 900 kg total | Michael |
| D25 | Tools: HyperFrames is already covered by our renderer. Lemo OpusCar adopted as a style reference. Claude Animation Base later. One Take and Collage B-roll skipped | Thread, on his "keep in your back pocket" ask |
| D26 | Voice: Chatterbox on the Mac, piloted after 5 to 10 real videos, with disclosure where required | Thread; timing accepted |
| D27 | Sound: build our own sound layer and download sounds into a local folder | Michael |
| D28 | Content Principles: use the ideas in our own script skill, do not copy the file into the public repo | Thread |
| D29 | Michael handles copyright and commercial-use questions. Licences are noted, not enforced, for media in videos. Ads are separate | Michael |
| D30 | Trend scouting through a burner Instagram account, lightly, added to the backlog | Michael |
| D31 | Backlog accepted: analytics, cross-poster, trend and market research, auto-clipping with scores, conversion tracking, content calendar, images and carousels, stories, every platform, voice clone | Michael |
| D32 | He is the only user, so packaging for others (plan Phase 7) drops in priority | Follows from Michael's statement |

## 7. Open questions for Michael

The first four block work today. The rest shape later workstreams and can be answered as each starts.

**Blocking now**

- [ ] **Link the MacBook Pro** to this project, or run `docs/SETUP.md` on it yourself. Nothing has run in real Resolve yet. (W1)
- [ ] **Instagram insights export** from Meta Business Suite, plus average watch time for a few of your best and worst reels. (W6)
- [ ] **Your original video files for past reels**, so each can be measured and matched to its results. Where do they live? (W6)
- [ ] **Add the three script checks to the score?** Sentence length, time to first useful point, longest held shot. Asked on 27 Nov, not yet answered. (W5)

**Shaping the editor**

- [ ] How do you usually shoot: one camera or several, phone or camera, horizontal or vertical, separate audio? (W2)
- [ ] What is your usual camera colour setup (log or standard), so looks start from the right place? (W2, W8)
- [ ] Which three effects or styles do you want copied first? A link with a timestamp for each. (W8)
- [ ] Will you record ten minutes of gym sounds (plates, chalk, bar drops) for the sound library? (W3)
- [ ] Music: trending audio added in the app at posting, or tracks laid in the edit? (W3)
- [ ] Mac memory, and whether the PC has an NVIDIA graphics card. (W9)

**Shaping the content system**

- [ ] How many posts a week is the target, by format? You said "an excellent amount of reels". (W11)
- [ ] Where should the calendar live: a page here, a spreadsheet, or a calendar app you already use? (W11)
- [ ] Cross-posting: is preparing four packages for you to post by hand enough for now, or do you want scheduled drafts inside each app? "It posts to all of them" and "never post automatically" need one rule between them. (W13)
- [ ] Will you create the burner Instagram account, and which computer stays on for the sessions? (W10)
- [ ] Do you have TikTok and YouTube accounts already, and under what names? (W13)
- [ ] How do coaching enquiries and brand offers reach you today: the nospotter.com form, direct messages, email? (W14)
- [ ] What are the rules for paid ad videos? You said you will give guidance. (W13, W14)
- [ ] Are you comfortable labelling cloned-voice reels as AI on Instagram, as its rules require? (W9)

**Carried over, no answer needed yet**

- Federation, weight class and qualifying standard for worlds: parked with the worlds topic (rule C11).
- Whether Solid Heaston's 200K is Instagram or all platforms: could not be checked.

## 8. Sources audited

Read in full for this document on 27 November 2026 (UTC):

- The whole project chat, from the first message to the request for this document.
- Project memory: project state, niche and goals, creator research, storytelling research, the story-over-visuals feedback, and the tools verdict.
- Four threads, every message: the editor build, creator styles, story and hooks research, and the tools and voice evaluation.
- [AI editing companion for DaVinci Resolve: build plan](https://claude.ai/artifact/MsbS66XueJzZxRDQRue27S)
- [What makes videos and shorts hook viewers](https://claude.ai/artifact/WyEkvYkg3vor27P96ojFeo)
- [Fitness creator styles](https://claude.ai/artifact/Vx8RNz16GkqHFBGFgN2gVo)
- [Back-pocket tools verdict](https://claude.ai/artifact/47Aw2WG6QMSpznvY49VhUe)
- The [Editor repository](https://github.com/michaelbelcherlifts/Editor) at `main` after pull request 8: README, setup guide, rules, skills, command list, source layout and git history.
- Project files: the clip record format, the creator style files, and the first test outputs.

**Limits of this audit.** Work in progress in the build and creator threads was read from their status notes, not from finished results, so section 3.3 will be out of date first. The test count (101) is the build thread's last report; I did not rerun the suite, since this change adds a document only. Acceptance numbers such as "five candidates from a 20 minute recording" are my proposals for him to adjust, not figures he gave.
