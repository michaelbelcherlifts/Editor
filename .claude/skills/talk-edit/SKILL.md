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
| "here", "this", "from here" | Read the playhead timecode through the Resolve MCP. Subtract the timeline start to get a timeline time |
| "on the marker" | Read the markers through the Resolve MCP |
| "the part where I say ..." | `uv run stylebrain find "words" --transcript FILE` |
| a time | Use it directly |

If two readings are plausible, ask one short question before cutting.

## Making the change

| Request | Command |
| --- | --- |
| Cut a stretch | `stylebrain cut START END` |
| Cut some words | `stylebrain cut-phrase "words" --transcript FILE` |
| Shorten pauses | `stylebrain tighten --transcript FILE --min-gap 0.6 --pad 0.12` |
| Move a section | `stylebrain move START END TO` |
| Swap two sections | `stylebrain swap A_START A_END B_START B_END` |
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
