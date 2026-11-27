# Style Brain

Talk through an edit in DaVinci Resolve Studio with Claude Code. You say "cut that
retake" or "swap these two sections"; Claude changes the edit and a new timeline
version appears in Resolve.

This is the first piece of a larger plan (copying effects from reference videos,
explainer animations, color looks, overnight autopilot). What exists today:

| Piece | What it does | State |
| --- | --- | --- |
| Edit list engine | Keeps the edit as data: cut, move, swap, overlays, with every version saved | Tested |
| Transcript tools | Find where a phrase is said; find and shorten pauses | Tested |
| Command line | The commands Claude runs while you talk | Tested |
| Animation renderer | Renders HTML animations to transparent clips for the timeline | Tested |
| Animation templates | Caption pop, lower third, callout, running captions, muscle diagram | Tested |
| Effect library | Named, reusable effect recipes you can place by name | Tested |
| Baked effects | Punch-in zooms and speed changes made with ffmpeg | Tested |
| Resolve builder | Builds the edit in Resolve as a new timeline and checks it | Tested against a stand-in only. **Not yet run against real Resolve** |

## Why an edit list

Resolve's scripting API cannot cut, trim or move a clip that is already on a
timeline. So the edit is kept outside Resolve as a list of decisions. Each change
edits the list and rebuilds the timeline as a new version. Old versions stay, which
is what makes undo work.

## Setup

See [docs/SETUP.md](docs/SETUP.md). Short version: Resolve Studio 21.1 or later,
External scripting set to Local, [uv](https://docs.astral.sh/uv/) and ffmpeg
installed, then `uv sync --all-extras` and `uv run playwright install chromium` in
this folder, and open the folder in Claude Code.

## Using it

Open this folder in Claude Code and talk. The rules Claude follows are in
[CLAUDE.md](CLAUDE.md) and the workflow is in
[.claude/skills/talk-edit/SKILL.md](.claude/skills/talk-edit/SKILL.md).

The same commands work by hand:

```
uv run stylebrain new bench --source ~/Movies/bench.mov
uv run stylebrain cut 1:10 1:24            # cut a stretch, close the gap
uv run stylebrain cut-phrase "let me start over" --transcript bench.words.json
uv run stylebrain tighten --transcript bench.words.json
uv run stylebrain swap 0:30 1:00 2:00 2:45
uv run stylebrain show
uv run stylebrain undo
uv run stylebrain build                    # new timeline in Resolve
```

Animations:

```
uv run stylebrain templates
uv run stylebrain render muscle_diagram --out bench.mov \
  --params '{"title": "Bench press", "highlights": ["chest", "front delts", "triceps"]}'
uv run stylebrain effect-save pop --template caption_pop --params '{"text": "x"}'
uv run stylebrain effect-place pop --at 0:42 --set text="This changes everything"
```

Times are timeline times: seconds (`83.5`), `1:23.5`, timecode `00:01:23:12`, or
frames `120f`.

## Development

```
uv sync --all-extras
uv run playwright install chromium
uv run pytest
```

## Known limits of this version

- One layer of footage on the main track, plus overlays above it. No transitions or
  audio-only edits yet. Zooms and speed changes are baked into a new file, not live
  in Resolve.
- Transparent clips are ProRes 4444 and large, roughly 10 to 20 MB per second at 1080p.
- The muscle figure is a simple stylized diagram, not a medical illustration.
- Rebuilding does not carry over work done by hand on the previous timeline.
- Transcripts are read from a word-timing JSON file; making one is not built in yet.
