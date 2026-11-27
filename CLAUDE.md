# Style Brain: rules for Claude Code

This folder lets Michael talk through a video edit in DaVinci Resolve Studio.
The edit is kept as an edit list in `.stylebrain/`; Resolve timelines are built
from it. Read `.claude/skills/talk-edit/SKILL.md` before editing.

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
  were not asked for.

## Layout

- `src/stylebrain/edl.py`: the edit list and its operations
- `src/stylebrain/transcript.py`: phrase search and pause finding
- `src/stylebrain/store.py`: saved versions and undo
- `src/stylebrain/resolve_builder.py`: builds and verifies a Resolve timeline
- `src/stylebrain/cli.py`: the `stylebrain` command

## Development

Run `uv run pytest` after any code change. Tests must not need Resolve; use
`tests/fake_resolve.py`.
