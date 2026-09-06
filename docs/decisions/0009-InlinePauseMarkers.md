# 9. Inline [pause:N] markers for user-controlled silence

## Status

Accepted

## Context

Piper's own CLI has a `--sentence-silence` flag, but it only adds a fixed
amount of silence after every sentence it detects — there's no way to place
a pause at an arbitrary point of the user's choosing, or to vary how long
different pauses are within the same piece of text. The user wanted exactly
that: mark a specific spot in the text box and control how long that
particular pause is.

## Decision

Text typed into AppliedPiper may contain inline markers of the form
`[pause:N]`, where `N` is a number of seconds between `MIN_PAUSE_SECONDS`
(0.5) and `MAX_PAUSE_SECONDS` (5.0) — e.g. `[pause:2]` or `[pause:0.5]`.
`tts.synthesize()` itself is pause-aware rather than pushing this logic into
`app.py`: it parses markers via `parse_pause_markers()` (a plain function,
same testability pattern as `perform_synthesis`, per ADR 0005), and:

- Text with no markers is synthesized exactly as before this piece existed —
  one Piper call, unchanged code path, unchanged behavior.
- Text with markers is split around them; each surrounding chunk is
  synthesized into its own file in a temporary directory
  (`tempfile.TemporaryDirectory`, auto-cleaned on exit); the resulting WAV
  files are then concatenated, with real silence spliced in for each marker,
  into one final WAV at the caller's requested output path — using only
  Python's stdlib `wave` module, no new dependency.

Because this lives entirely inside `synthesize()`, `app.py`/`perform_synthesis`
needed zero changes — pause support is invisible plumbing to every existing
caller.

An out-of-range or malformed marker (e.g. `[pause:10]` or `[pause:abc]`)
raises `PiperError` naming the exact offending marker, rather than silently
clamping the value or mispronouncing the bracket text.

## Consequences

- Splicing raw silence as all-zero bytes is only correct for 16-bit PCM (for
  8-bit WAV, silence is the byte value 128, not 0). Every Piper voice
  produces 16-bit PCM today, but `tts.py` checks this explicitly before
  writing silence and raises `PiperError` rather than producing a
  corrupted/clicking WAV file if that's ever not true.
- A text made entirely of pause markers with no actual words (e.g.
  `"[pause:2]"` alone) raises `PiperError("No text to speak.")` before any
  subprocess is invoked, same as literal blank text.
- Multiple Piper subprocess calls now happen for one Play/Save when markers
  are present (one per surrounding text chunk) — no noticeable slowdown in
  practice, since Piper's own per-call startup cost dominates either way, but
  worth knowing if synthesis time is ever profiled.
- This only supports pauses *between* pieces of Piper-synthesized speech, not
  a pause enforced mid-word or mid-phoneme — the marker must sit at a point
  where splitting the text into two independent chunks still reads (and
  sounds) naturally.
- The GUI doesn't yet surface the `[pause:N]` syntax anywhere on-screen; a
  user who doesn't already know about it has no way to discover the feature.
  Worth a follow-up piece (a hint label, tooltip, or README mention).
