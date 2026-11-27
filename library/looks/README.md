# Saved looks

One `.cube` LUT per look, made with `uv run stylebrain look-make NAME --reference REF --footage MINE`.

Or from a measured style, without a reference video: `uv run stylebrain look-from-style NAME --style STYLE`
(a saved style name or a profile `.json`). Add `--footage MINE` to measure his clip first, which is more accurate.

The `creator-*` looks were made this way from the creator study (browser samples, approximate),
assuming a typical phone clip, at strength 0.8. They match overall tone, brightness, saturation
and balance only. Check each on his own footage with `look-preview` before using it.
