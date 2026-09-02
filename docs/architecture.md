# Architecture

## What this app does

AppliedPiper is a local text-to-speech tool: type text, get spoken audio,
entirely offline after the first voice download. It's a thin GUI and
process-management layer over [Piper](https://github.com/OHF-Voice/piper1-gpl),
which does the actual neural speech synthesis.

## Module map (current)

| Module | Responsibility |
|---|---|
| `tts.py` | Wraps the Piper CLI: validates input, builds the subprocess command, translates Piper's failures into a single `PiperError` type. This is the only module that knows Piper exists. |

*(This table grows as each subsequent piece — voice management, the GUI,
playback — is added. See `decisions/` for the reasoning behind each one.)*

## Data flow (current)

1. Caller provides text, a voice id, a voices directory, and an output path.
2. `tts.synthesize()` validates both inputs before doing anything else —
   fail fast, with a message we control rather than one Piper produces.
3. It shells out to `python -m piper` as a separate process (see
   [ADR 0001](decisions/0001-shell-out-to-piper-cli.md) for why) and
   waits for it to finish.
4. On success, a WAV file exists at the output path. On any failure, a
   `PiperError` is raised with Piper's own error detail attached.

## Design principles this codebase follows

- **One exception type per module boundary.** Callers of `tts.py` never
  need to know or catch `subprocess.CalledProcessError`,
  `FileNotFoundError`, or `subprocess.TimeoutExpired` — everything Piper
  might do wrong surfaces as `PiperError`. This keeps the "what can go
  wrong" surface area small and documented in one place.
- **Fail fast on preconditions we can check ourselves.** Blank text and
  missing voice files are checked before touching a subprocess, so error
  messages are ours to write rather than parsed out of a subprocess's
  stderr.
- **Depend on stable, documented interfaces, not internals.** `tts.py`
  calls Piper's command-line interface rather than importing its Python
  classes — see ADR 0001.