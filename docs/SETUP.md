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
- [ ] `uv run stylebrain ref-fetch <a YouTube link>` downloads the video into `references/`.
- [ ] After `look-use NAME` and `build`, the clips show the LUT on their first node on the Color page.
- [ ] `uv run stylebrain transcribe <clip>` writes `<clip>.words.json` (install `mlx-whisper` first: `uv tool install mlx-whisper`).
- [ ] `uv run stylebrain auto test2 --source <clip>` runs through and builds a timeline.
- [ ] After `sfx-basics`, `sfx-auto` and `build`, the sound effects clip sits on audio track 2 and sounds right.
- [ ] `uv run stylebrain sfx-fetch whoosh` downloads sounds from Openverse.
- [ ] Audio comes along with the video on the main track.

If `build` reports problems, paste its output to Claude. The builder reads every
clip back after placing it, so the report says exactly what differed.

## Windows notes (from the first real run, 2026-11-27)

The editor runs on Windows: 100 of 101 tests passed, and the one that did not is a
test that cannot run there. Two things to know:

- Inside the Claude desktop app, `uv sync` can fail with "Missing expected target
  directory for Python minor version link". Set `UV_PYTHON_INSTALL_DIR` to a folder
  you own (for example `.uv-python` beside the repository) and run it again.
- Install the tools with winget: `yt-dlp`, `ffmpeg`, `deno` (yt-dlp needs it for
  full-quality YouTube formats) and `uv`. Open a new terminal afterwards.
