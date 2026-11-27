---
name: talk-edit
description: Use when Michael describes an edit to make in DaVinci Resolve in words, such as "cut this part", "swap these sections", "tighten the pauses", "put this here" or "undo that".
---

# Talk-through editing

Michael works in Resolve and says what he wants. You change the edit list and
rebuild the timeline as a new version.

## Starting a session

1. Run `uv run stylebrain show`. If there is no project, ask which clip to start
   from and run `uv run stylebrain new NAME --source PATH`.
2. If the request involves spoken words or pauses, you need a word-timing JSON for
   the source clip. Get it from Resolve's transcription through the Resolve MCP,
   or from a local transcriber, and save it next to the clip as `NAME.words.json`
   (a list of `{"word", "start", "end"}` in seconds of the source clip).

## Working out where

| He says | Do this |
| --- | --- |
| "here", "this", "from here" | `uv run stylebrain markers` prints the playhead as an edit time (or read the timecode through the Resolve MCP and subtract the timeline start) |
| "on the marker", "between my markers" | `uv run stylebrain markers` lists his markers as edit times, with their notes. A marker with a length is a range |
| "the part where I say ..." | `uv run stylebrain find "words" --transcript FILE` |
| a time | Use it directly |

If `markers` says the open timeline is not a build of the current version, its
times may not match the edit: build first, or ask him. If two readings are
plausible, ask one short question before cutting.

## Making the change

| Request | Command |
| --- | --- |
| Cut a stretch | `stylebrain cut START END` |
| Cut some words | `stylebrain cut-phrase "words" --transcript FILE` |
| Shorten pauses | `stylebrain tighten --transcript FILE --min-gap 0.6 --pad 0.12` |
| Move a section | `stylebrain move START END TO` |
| Swap two sections | `stylebrain swap A_START A_END B_START B_END` |
| Slow motion, or slow into a pose | `stylebrain speed --from A --to B --speed 0.5 --ramp 0.3` (silent unless `--sound`; see `docs/aesthetic-shots.md`) |
| Place a clip above | `stylebrain overlay-add NAME --source PATH --at T --duration D` |
| Undo | `stylebrain undo` |
| Go back further | `stylebrain log`, then `stylebrain goto N` |

Then run `uv run stylebrain build` and relay its report.

## After each change

Tell him in one line what changed and the new length. If overlays were removed
because their footage was cut, say which. If the build report lists problems,
lead with that.

## Do not

- Do not batch several unrelated changes into one command.
- Do not rebuild after `find` or `show`; they change nothing.
- Do not promise transitions, zooms or speed changes yet; this version cannot
  make them.

## More than one clip

- Another take or camera on the main track: `uv run stylebrain add-source FILE`
  (at the end), `--at TIME` to insert, `--from` / `--to` to use part of it.
  Everything after the insert moves later, with its graphics and sounds.
- B-roll over the talking: `uv run stylebrain broll FILE --at TIME --duration 3`
  (`--from` picks where in the b-roll to start). Picture only; his voice keeps
  playing underneath. It follows cuts like any overlay.
- `uv run stylebrain sources` lists what the edit uses. Commands that take a
  transcript need `--source NAME` once there is more than one clip.
- A clip at a different frame rate is refused: convert it first, and say why.

## Changes he made by hand in Resolve

Every build makes a new timeline from the edit list, so anything he did by hand
on the last one (a trim, a title, a resize) is not on the new one. `build`
checks the last built timeline first and prints a warning listing what he
changed. When it does:

1. Relay every line before anything else. His old timeline is untouched.
2. For each change, offer to make it part of the edit so it survives: a trim
   becomes `cut`, a resize becomes `reframe`, a title becomes an overlay.
3. It cannot see colour grades, effects or keyframes. Say so, and ask him to
   check those by eye. The safe order of work is: structure through the edit
   list first, polish by hand in Resolve last.

## J-cuts and L-cuts

A straight cut changes picture and sound together. A split edit moves the
sound's cut away from the picture's:

- `uv run stylebrain jcut TIME [--seconds 0.25]`: the next line is heard a
  moment before its picture arrives. Use it to pull the viewer into the next
  thought, or to hide a hard jump between two takes.
- `uv run stylebrain lcut TIME [--seconds 0.25]`: the last line carries on
  over the new picture. Use it when cutting to b-roll or a reaction.
- `uv run stylebrain straight-cut TIME` makes it a plain cut again.

TIME is at or near an existing cut (within a second). The length of the edit
does not change. Offer these where he asks for smoother cuts; do not add them
unasked. A J-cut needs footage before the incoming piece's start to lead in
with: after a pause was tightened, what leads in is the tail of that pause, so
listen for a breath or a click. In Resolve the picture and sound are placed
apart on V1 and A1; this has not yet been tried in real Resolve, so check the
first build by ear and relay any problem the report lists.
