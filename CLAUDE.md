# Style Brain: rules for Claude Code

This folder lets Michael talk through a video edit in DaVinci Resolve Studio.
The edit is kept as an edit list in `.stylebrain/`; Resolve timelines are built
from it. Read `.claude/skills/talk-edit/SKILL.md` before editing, and
`.claude/skills/animate/SKILL.md` before making any animation, and
`.claude/skills/copy-effect/SKILL.md` before recreating an effect from a link or
screenshots, and `.claude/skills/script/SKILL.md` before writing a script or hooks. Other skills in `.claude/skills/` cover styles, colour, autopilot, reviews,
sound, reframing, export, the content calendar and social posts.

## Rules

- Never edit a Resolve timeline in place to cut, trim or move clips. Change the
  edit list with `uv run stylebrain ...`, then `uv run stylebrain build`.
- Every build makes a new timeline. Never delete or rename Michael's timelines.
- Make one change per command so each can be undone on its own.
- After `build`, relay the report. If it lists problems, say so plainly and do
  not claim the edit landed.
- When a request is ambiguous about where ("cut this"), find out before cutting:
  read the playhead or markers through the Resolve MCP, or ask.
- Say what changed in one line, including the new length.
- Creative choices are Michael's. Offer options; do not add effects or cuts that
  were not asked for. Autopilot is the exception he asked for: it may cut retakes
  and pauses, and must list every cut it made.

## Layout

- `src/stylebrain/edl.py`: the edit list and its operations
- `src/stylebrain/transcript.py`: phrase search and pause finding
- `src/stylebrain/store.py`: saved versions and undo
- `src/stylebrain/resolve_builder.py`: builds and verifies a Resolve timeline
- `src/stylebrain/render.py`: HTML animation to transparent video
- `src/stylebrain/templates.py`, `anatomy.py`: animation templates and the body figure
- `src/stylebrain/kinetic.py`, `explainers.py`, `pagekit.py`: type templates (kinetic type, mid captions, counters, end cards, clipper), lift explainers (lift presets, form cues, tempo, charts), and the shared stage and caption safe zone
- `src/stylebrain/effects.py`: the saved effect library (`library/effects/`)
- `src/stylebrain/reference.py`: studying a reference video (frame sheets, motion timing, colours, side-by-side check)
- `src/stylebrain/style.py`: measuring a video's style (cuts, opening, speech pace, picture, sound) into `library/styles/`
- `src/stylebrain/look.py`: colour looks: a LUT made from a reference or a measured style, saved in `library/looks/`
- `src/stylebrain/transcribe.py`: word-timing transcripts from a local speech-to-text tool
- `src/stylebrain/autopilot.py`: first cut in one command (retakes, pauses, look, captions, build, review)
- `src/stylebrain/review.py`: timestamped suggestions from comparing a cut with a style
- `src/stylebrain/story.py`: hook check, beat map, "and then" pass, hook types, script checks
- `src/stylebrain/score.py`: the virality rubric: a 0 to 100 score for a short clip, part by part
- `src/stylebrain/learn.py`: clip attributes, the private clip dataset (`library/clips/`, not committed) and the model that finds what goes with performance
- `src/stylebrain/sfx.py`: the sound library (`library/sfx/`, not committed), automatic placement, and the mix that goes on audio track 2
- `src/stylebrain/reframe.py`: finds the subject and sets each clip's framing (`x`, `y`, `zoom`) for vertical crops and punch-ins
- `src/stylebrain/export.py`: renders the edit list to a postable file with ffmpeg, and checks any finished file (frame, length, loudness, black frames)
- `src/stylebrain/social.py`: stills for Instagram and YouTube: photo edits, carousels, covers, story suggestions, and the package a reel becomes
- `src/stylebrain/content.py`: the content plan: idea backlog, series, calendar, weekly plans, shoot lists, calls to action (`library/content/`, not committed; never posts)
- `src/stylebrain/bake.py`: ffmpeg zooms and speed changes
- `src/stylebrain/cli.py`: the `stylebrain` command

## Development

Run `uv run pytest` after any code change. Tests must not need Resolve; use
`tests/fake_resolve.py`.
