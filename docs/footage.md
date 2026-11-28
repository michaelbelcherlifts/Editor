# Footage: phone and camera to the editor

Everything here is free. Google Drive's free plan holds 15 GB, about 90 minutes of
4K phone video, so Drive is the **inbox**, not the archive. Footage lives in the
**footage library**: a folder on the PC for now, the SSD once it is plugged in.

## How footage moves

```
phone ──Drive app upload──▶ My Drive/Style Brain/Inbox ──footage-pull──▶ footage library (PC, later SSD)
camera card ──────────────────────────────────────────footage-pull --source──▶ footage library
export ──footage-final──▶ My Drive/Style Brain/Finals ──▶ Drive app on the phone ──▶ post
```

- **Phone to Drive:** the Google Drive app, upload into `Style Brain/Inbox`. Upload
  on Wi-Fi; the original file goes up, not a smaller copy.
- **Drive to the computer:** Google Drive for desktop, in **Stream** mode. Drive shows
  up as a drive letter (usually `G:\My Drive`) on Windows, or under
  `~/Library/CloudStorage/GoogleDrive-…/My Drive` on the Mac. Files only download when
  `footage-pull` copies them, so the PC disk does not fill with a second copy.
  (The Drive connector in Claude reads documents; it cannot hand Resolve a video file,
  so it is not used for footage.)
- **Camera:** a camera card goes straight into the computer. Its files are too big to
  route through a 15 GB Drive: `footage-pull --source E:\DCIM --name "bench day"`.
- **Finals back to the phone:** `footage-final exports/reel.mp4` puts the file in
  `Style Brain/Finals`, which the Drive app on the phone can save to the camera roll.

## The library

```
Style Brain Footage/
  2026/
    2026-11-28 bench day/
      raw/phone/IMG_1234.MOV
      raw/camera/C0001.MP4
      raw/audio/mic.wav
      raw/photos/IMG_1235.HEIC
      shoot.json        each file: where it came from, checksum, device, when recorded
  pulled.json           what has already been copied, so nothing copies twice
```

One folder per shoot day, by the date the clip was recorded (from the camera's own
clock, else the file's date). Inside, one folder per device: phone, camera, drone,
action-cam, audio, photos, other. Every copy is read back and compared with the
original before it counts.

Edit projects, renders and Resolve's cache stay out of this folder: the library is
only original footage, so it is the one thing to back up.

## Commands

| Command | What it does |
| --- | --- |
| `footage-setup [--library PATH]` | Finds Drive, makes `Style Brain/Inbox` and `Style Brain/Finals`, sets the library (default `Videos\Style Brain Footage`). Run again with `--library` when the SSD arrives. |
| `footage-status` | Folders, free space, how much is waiting in the inbox, a warning near 15 GB. |
| `footage-pull [--name "bench day"] [--source FOLDER] [--dry-run]` | Copies new footage in, sorted and checked. Files that changed in the last minute are still uploading and wait for the next pull. |
| `footage-list` | The shoots, with file counts and sizes. |
| `footage-clips "bench day" [--kind phone]` | Full paths, ready for `new --source` or `add-source`. |
| `footage-clear [--yes]` | Lists, then with `--yes` removes, inbox files that are safely in the library. They go to the Drive trash for 30 days and still count toward 15 GB until the trash is emptied. |
| `footage-final FILE` | Copies a finished export to `Style Brain/Finals`. |

## The SSD

- **Format it exFAT** so both the Windows PC and the Mac can read and write it. (A new
  SSD often comes as exFAT already. Formatting erases it, so only on an empty drive.)
- Name it `FOOTAGE` and keep the library at the top: `E:\Style Brain Footage` on the
  PC, `/Volumes/FOOTAGE/Style Brain Footage` on the Mac.
- Point each computer at it once: `footage-setup --library "E:\Style Brain Footage"`.
  The setting is per computer (`library/footage.json`, not committed).
- Moving what is already on the PC: copy the old library folder onto the SSD with
  `robocopy "<old>" "E:\Style Brain Footage" /E`, then run `footage-setup --library`.
- If the SSD is unplugged, `footage-pull` stops and says so instead of writing
  somewhere else.
- One copy is not a backup. When there is a second drive, mirror the library to it.
