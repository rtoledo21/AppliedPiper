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
| `voices.py` | Lists which voices are already downloaded (`list_installed_voices`) and downloads new ones (`download_voice`), both by shelling out to Piper's CLI. Reuses `tts.PiperError` rather than defining its own — see [ADR 0001](decisions/0001-ShellOutToPiperCli.md). |
| `app.py` | Tkinter GUI shell — window layout and widgets, not yet wired to `tts.py`/`voices.py`. Tested at the view/controller seam per [ADR 0005](decisions/0005-GUITests.md), not for layout/appearance. |

*(This table grows as each subsequent piece — wiring, playback — is
added. See `decisions/` for the reasoning behind each one.)*

## Data flow (current)

1. Caller provides text, a voice id, a voices directory, and an output path.
2. `tts.synthesize()` validates both inputs before doing anything else —
   fail fast, with a message we control rather than one Piper produces.
3. It shells out to `python -m piper` as a separate process (see
   [ADR 0001](decisions/0001-ShellOutToPiperCli.md) for why) and
   waits for it to finish.
4. On success, a WAV file exists at the output path. On any failure, a
   `PiperError` is raised with Piper's own error detail attached.
5. Before synthesis, `voices.list_installed_voices()` can be used to
   check what's already downloaded, and `voices.download_voice()` to
   fetch more via `python -m piper.download_voices`.

## Where things live on disk

- Voice model files (`.onnx` / `.onnx.json`) are downloaded into
  `voice_data/` at the project root — deliberately *not* named `voices`,
  since that collides with the `voices.py` module (see
  [ADR 0004](decisions/0004-VoiceDataNaming.md)). This directory is
  gitignored; voices are re-downloaded per machine.

## Design principles this codebase follows

- **One exception type per module boundary.** Callers of `tts.py` and
  `voices.py` never need to know or catch `subprocess.CalledProcessError`,
  `FileNotFoundError`, or `subprocess.TimeoutExpired` — everything Piper
  might do wrong surfaces as `PiperError`.
- **Fail fast on preconditions we can check ourselves.** Blank text and
  missing voice files are checked before touching a subprocess, so error
  messages are ours to write rather than parsed out of a subprocess's
  stderr.
- **Depend on stable, documented interfaces, not internals.** Both
  `tts.py` and `voices.py` call Piper's command-line interface rather
  than importing its Python classes — see ADR 0001.
- **Tests never spawn a real process or need a running Piper install.**
  `subprocess.run` is mocked in every test for `tts.py`/`voices.py` — see
  [ADR 0003](decisions/0003-UnitTests.md). GUI tests use real `Tk()`
  widgets but no real synthesis — see [ADR 0005](decisions/0005-GUITests.md).