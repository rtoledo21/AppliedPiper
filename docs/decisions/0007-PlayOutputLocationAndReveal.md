# 7. Play writes to a fixed project-local file; revealing it is best-effort and OS-specific

## Status

Accepted

## Context

Piece 4 originally wrote Play's output to the OS-wide temp directory
(`tempfile.gettempdir()`), a common quick-prototype pattern. In practice this
made the file nearly impossible to find by hand — macOS's temp path is a long,
hidden `/var/folders/...` directory not meant for casual browsing — with no way
to clean up old runs short of knowing exactly where to look.

## Decision

Play always writes to the same fixed path, `OUTPUT_DIR / "play.wav"`
(`OUTPUT_DIR` = `<project root>/output/`, gitignored, same pattern as
`voice_data/`), overwriting the previous run rather than accumulating
timestamped files — there's only ever one "current" Play output, so there's
nothing to clean up beyond that single file.

A "Show in Finder" button reveals whichever file was most recently produced by
either Play or Save, via a small `reveal_in_file_manager()` function that
shells out to the platform's own file manager: `open -R` on macOS, `explorer
/select,` on Windows, and `xdg-open` on the containing folder on Linux (Linux
has no universal "select this exact file" convention, so revealing the folder
is the closest equivalent). This is deliberately a plain, Tkinter-free
function, tested the same way as `perform_synthesis` (ADR 0005): mock
`subprocess.run` and `platform.system`, assert the right command per platform.

## Consequences

- Reveal is best-effort: if the relevant command isn't on `PATH` (e.g. a
  minimal Linux install without `xdg-open`), `reveal_in_file_manager` catches
  `FileNotFoundError` and does nothing rather than raising — a broken "show me
  the file" convenience should never crash a successful synthesis.
- Save As… is unaffected — it already writes exactly where the user picks via
  the native file dialog. The reveal button now also applies to the last Save
  destination, not just Play, since both paths funnel through the same
  `_on_synthesis_done`.
- Because Play always overwrites the same file, there is no history of past
  Play attempts; anyone wanting to keep a specific output must use Save As.
