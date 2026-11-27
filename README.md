# Style Brain

Talk through an edit in DaVinci Resolve Studio with Claude Code. You say "cut that
retake" or "swap these two sections"; Claude changes the edit and a new timeline
version appears in Resolve.

Where the project is going, and what is built versus planned, is in
[docs/PRD.md](docs/PRD.md).

What exists today:

| Piece | What it does | State |
| --- | --- | --- |
| Edit list engine | Keeps the edit as data: cut, move, swap, overlays, with every version saved | Tested |
| Transcript tools | Find where a phrase is said; find and shorten pauses | Tested |
| Command line | The commands Claude runs while you talk | Tested |
| Animation renderer | Renders HTML animations to transparent clips for the timeline | Tested |
| Animation templates | Caption pop, lower third, callout, running captions, muscle diagram | Tested |
| Effect library | Named, reusable effect recipes you can place by name | Tested |
| Baked effects | Punch-in zooms and speed changes made with ffmpeg | Tested |
| Reference study | Downloads a link, makes frame sheets, reads motion timing and colours, and compares a remake against the original | Tested on clips made here. **Not yet run on a real YouTube link** |
| Style profiles | Measures a video's cut rate, opening, speech pace, picture and sound, and saves it by name | Tested on clips made here |
| Colour looks | Makes a LUT that moves your footage toward a reference's tone and colour balance, and puts it on the clips at build | Tested on clips made here; applying it in Resolve is tested against a stand-in only |
| Autopilot | One command from a raw clip to a first cut: retakes out, pauses tightened, look, captions, build, review | Tested with a stand-in for Resolve; ran end to end here on a generated clip |
| Cut review | Timestamped notes on how your cut differs from a saved style | Tested |
| Transcription | Runs a free local speech-to-text tool (mlx-whisper or whisper) | Plumbing tested with a stand-in. **Not yet run with the real tools** |
| Story and hook checks | Hook check with the second each problem happens, a beat map for long-form that flags stretches with no new question and "and then" runs, hook types and a checker for written hooks, script checks. A script skill writes story first, then hooks, then lines | Tested on made-up transcripts. **Not yet run on his real videos** |
| Virality score | Scores a short clip 0 to 100 on seven listed parts (hook, pacing, payoff, value, shareability, trend, craft), including time to first useful point, longest held shot and sentence length, with a story gate that caps a clip with nothing to find out at 55. Weights are a starting proposal, not yet tuned on real analytics | Tested |
| Learning | Turns clips into attributes, reads a YouTube Studio export, and fits a small local model that shows which attributes go with reach or retention and suggests score weights | Tested on made-up data with a planted signal. **No real result yet: it needs at least 12 clips with results, 30 to rely on** |
| Sound effects | A tagged local sound library, a fetcher for Openverse, automatic hits on cuts, graphics and zooms lowered under speech, mixed onto its own audio track at build | Tested with a stand-in for Resolve. **Openverse download not yet run for real; nobody has listened to a mix yet** |
| Export | Renders the edit to a 1080x1920 file with the look, sounds and loudness set, then checks frame, length, loudness, peaks and black frames and saves a sheet of frames to look at | Tested on clips made here. **Not yet tried on a real recording** |
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

Styles, colour, autopilot and review:

```
uv run stylebrain ref-fetch https://youtube.com/watch?v=...
uv run stylebrain style-learn references/ID.mp4 --name fastcut
uv run stylebrain look-make warm --reference references/ID.mp4 --footage ~/Movies/bench.mov
uv run stylebrain auto bench2 --source ~/Movies/bench2.mov --style fastcut --look warm --captions
uv run stylebrain review fastcut --transcript ~/Movies/bench2.words.json
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

- Several clips can share the main track, with b-roll and graphics above it, but all
  must be at the edit's frame rate. No transitions or audio-only edits yet. Zooms and speed changes are baked into a new file, not live
  in Resolve.
- Transparent clips are ProRes 4444 and large, roughly 10 to 20 MB per second at 1080p.
- The muscle figure is a simple stylized diagram, not a medical illustration.
- Rebuilding does not carry over work done by hand on the previous timeline.
- Transcription needs a free local tool installed (`uv tool install mlx-whisper` on Apple Silicon).
- Retake detection only catches a phrase repeated in the same words.
- A colour look matches overall tone and balance, not local work such as vignettes or skin isolation.
