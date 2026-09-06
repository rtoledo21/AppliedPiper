# Architecture

## What this app does

AppliedPiper is a local text-to-speech tool: type text, get spoken audio,
entirely offline after the first voice download. It's a thin GUI and
process-management layer over [Piper](https://github.com/OHF-Voice/piper1-gpl),
which does the actual neural speech synthesis.

## Module map (current)

| Module | Responsibility |
|---|---|
| `tts.py` | Wraps the Piper CLI: validates input, builds the subprocess command, translates Piper's failures into a single `PiperError` type. This is the only module that knows Piper exists. `synthesize()` also parses inline `[pause:N]` markers, synthesizing around them and splicing in real silence via the `wave` module — see [ADR 0009](decisions/0009-InlinePauseMarkers.md). |
| `voices.py` | Lists which voices are already downloaded (`list_installed_voices`) and downloads new ones (`download_voice`), both by shelling out to Piper's CLI. Reuses `tts.PiperError` rather than defining its own — see [ADR 0001](decisions/0001-ShellOutToPiperCli.md). |
| `app.py` | Tkinter GUI, wired to `tts.py` via `perform_synthesis()`. Synthesis runs on a background thread; the result comes back to the main thread through a `queue.Queue`, never a direct cross-thread Tk call — see [ADR 0006](decisions/0006-BackgroundThreadCommunication.md). Each Play writes to a new, incrementally-numbered `output/play_N.wav` via `next_play_output_path()` — see [ADR 0008](decisions/0008-IncrementalPlayFilenames.md) — and a "Show in Finder" button reveals the last Play/Save output via `reveal_in_file_manager()` — see [ADR 0007](decisions/0007-PlayOutputLocationAndReveal.md). Tested at the view/controller seam per [ADR 0005](decisions/0005-GUITests.md), not for layout/appearance. |

*(This table grows as each subsequent piece — wiring, playback — is
added. See `decisions/` for the reasoning behind each one.)*

## Data flow (current)

1. Caller provides text, a voice id, a voices directory, and an output path.
2. `tts.synthesize()` first checks the text for inline `[pause:N]` markers
   (`parse_pause_markers()`). Text with none behaves exactly like step 3
   below, as a single Piper call. Text with markers is split around them,
   each surrounding chunk synthesized separately into a temp file, and the
   results spliced together with real silence via the `wave` module — see
   [ADR 0009](decisions/0009-InlinePauseMarkers.md).
3. Each chunk (or the whole text, if there are no markers) shells out to
   `python -m piper` as a separate process (see
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
- Play's synthesized audio lands in `output/` at the project root as
  `play_1.wav`, `play_2.wav`, ... — a fixed, gitignored directory rather
  than an OS temp path, so it's easy to find by hand (see
  [ADR 0007](decisions/0007-PlayOutputLocationAndReveal.md)). Each Play
  gets its own incrementally-numbered file rather than overwriting the
  last one, and nothing prunes old ones automatically (see
  [ADR 0008](decisions/0008-IncrementalPlayFilenames.md)).

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
- **Background threads never touch Tkinter.** A `threading.Thread` target
  may do real work and call plain Python objects, but reports back only
  through a `queue.Queue` that the main thread polls on its own timer —
  calling `self.after()` or a widget/`StringVar` directly from another
  thread is unreliable on some Tcl/Tk builds (confirmed on macOS Aqua Tk;
  see [ADR 0006](decisions/0006-BackgroundThreadCommunication.md)).
- **Convenience features fail silently; core features don't.**
  `reveal_in_file_manager()` swallows a missing OS command rather than
  raising, because failing to open Finder should never look like failing
  to synthesize speech — see
  [ADR 0007](decisions/0007-PlayOutputLocationAndReveal.md).
- **Assumptions about external data are checked, not trusted.**
  Splicing silence into Piper's output assumes 16-bit PCM WAV (true for
  every Piper voice today); `tts.py` verifies this before writing raw
  silence bytes and raises `PiperError` rather than producing corrupt
  audio if that's ever not true — see
  [ADR 0009](decisions/0009-InlinePauseMarkers.md).
