# Setup on the Mac

1. **Resolve.** DaVinci Resolve Studio 21.1 or later. In Preferences > System >
   General, set External scripting to **Local**.
2. **Claude.** Install the Claude desktop app, open the Code tab, and choose to run
   locally on this computer.
3. **Official Resolve connection.** In Resolve, run File > Setup AI Assistants and
   choose Claude. This lets Claude read the playhead, markers and transcripts.
4. **Tools.** Install [uv](https://docs.astral.sh/uv/) and ffmpeg (for example
   `brew install uv ffmpeg`). Claude Code can do this for you if you ask.
5. **This folder.** Clone the repository, open the folder in Claude Code, and say
   "set up Style Brain". Claude runs `uv sync --all-extras`,
   `uv run playwright install chromium` and `uv run pytest`.

## First run checklist

These have not been confirmed on a real machine yet. Run them once and note the
results:

- [ ] `uv run stylebrain new test --source <a short clip>` reads the frame rate and length.
- [ ] `uv run stylebrain cut 1 2` then `uv run stylebrain build` creates a timeline
      named "test v2" in the open Resolve project, and reports "all checked".
- [ ] The cut lands on the right frame when you look at it in Resolve.
- [ ] `overlay-add` puts a clip on V2 at the right place.
- [ ] A rendered animation (`stylebrain render caption_pop ...`) imports into Resolve
      with its transparency intact.
- [ ] Audio comes along with the video on the main track.

If `build` reports problems, paste its output to Claude. The builder reads every
clip back after placing it, so the report says exactly what differed.
