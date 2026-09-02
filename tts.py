"""Wraps the Piper CLI for one-shot text-to-speech synthesis.

Design decision: we shell out to Piper as a separate process (`sys.executable -m piper ...`) instead of importing its
Python classes directly. Two reasons, one technical and one legal:

  - Technical: Piper's CLI is its stable, documented public interface. Its internal Python API has already changed shape
   across recent releases. Depending on the CLI means we only break if Piper's *command-line* contract changes, which is
   a much slower-moving target.
  - Legal: Piper is GPL-3.0-or-later. Invoking it as an independent external program (separate process, communicating
   over argv and a file) sits on the weak-entanglement side of GPL's "derivative work" question, unlike `import piper`
   which links it into our process. This is genuinely a gray area in copyright law, not a bright line, but subprocess
   use is the position with the most precedent behind it (see the FSF's own GPL FAQ on invoking GPL programs via
   exec/pipe).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class PiperError(RuntimeError):
    """Raised whenever Piper can't run or fails to produce audio."""


def synthesize(text: str, voice: str, voices_dir: Path, output_path: Path) -> None:
    """Synthesize `text` with `voice` and write a WAV file to `output_path`.

    `voice` is a Piper voice id (e.g. "en_US-lessac-medium"). It must already be downloaded:
    `voices_dir / f"{voice}.onnx"` (and the matching `.onnx.json`) must exist.
    """
    if not text.strip():
        raise PiperError("No text to speak.")

    model_path = voices_dir / f"{voice}.onnx"
    if not model_path.exists():
        raise PiperError(f"Voice '{voice}' isn't downloaded (looked for {model_path}).")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "piper",
        "-m",
        voice,
        "--data-dir",
        str(voices_dir),
        "-f",
        str(output_path),
        "--",
        text,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except FileNotFoundError as exc:
        raise PiperError("Piper isn't installed in this environment.") from exc
    except subprocess.TimeoutExpired as exc:
        raise PiperError("Piper timed out.") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise PiperError(f"Piper failed:\n{detail}")

    if not output_path.exists():
        raise PiperError("Piper exited cleanly but produced no output file.")