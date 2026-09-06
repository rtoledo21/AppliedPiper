# 8. Play output filenames increment instead of overwriting

## Status

Accepted. Supersedes [ADR 0007](0007-PlayOutputLocationAndReveal.md)'s
"always overwrite `play.wav`" decision; the fixed `output/` directory and the
reveal-button design from that ADR are unchanged.

## Context

ADR 0007 deliberately had every Play overwrite the same `output/play.wav`,
specifically so there'd be nothing to accumulate or clean up. In practice,
always overwriting the previous take turned out to be a real limitation:
there's no way to compare two takes, or keep a specific one, without
immediately using Save As before clicking Play again.

## Decision

Each Play now writes to a new, incrementally-numbered file:
`output/play_1.wav`, `output/play_2.wav`, and so on. The next number is
computed by `next_play_output_path()`, a plain, Tkinter-free function (same
testability pattern as `perform_synthesis` and `reveal_in_file_manager`, per
ADR 0005) that scans `output/` for existing `play_N.wav` files and returns
one past the highest `N` found, starting at 1 if none exist. It recomputes
from what's actually on disk every time rather than keeping an in-memory
counter, so it stays correct across app restarts and self-heals if files are
deleted by hand.

No automatic cap or cleanup was added: `output/` is allowed to accumulate
indefinitely, and the existing "Show in Finder" button (ADR 0007) is
considered sufficient for reviewing and deleting old takes by hand. This is a
deliberate simplicity choice, not an oversight — an automatic "keep only the
last N" policy would add real complexity (what N, on which trigger, what
happens if a file is open elsewhere) for a problem that hasn't come up yet.

## Consequences

- Play no longer destroys the previous take — multiple synthesis attempts can
  be compared by listening to sequential files in `output/`.
- `output/` grows by one file per Play click, unbounded, until cleaned out by
  hand (it's gitignored, so this never touches the repo).
- The status bar message and the reveal button both already referenced
  "whatever `output_path` was passed to `_run_synthesis`," so neither needed
  to change — only the path-selection logic in `_on_play_clicked` did.
- Save As… is entirely unaffected — the user always names that file
  explicitly via the native save dialog.
