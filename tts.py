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

import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path


class PiperError(RuntimeError):
    """Raised whenever Piper can't run or fails to produce audio."""


MIN_PAUSE_SECONDS = 0.5
MAX_PAUSE_SECONDS = 5.0

_PAUSE_MARKER_PATTERN = re.compile(r"\[pause:([^\]]*)\]", re.IGNORECASE)


def parse_pause_markers(text: str) -> list[tuple[str, "str | float"]]:
    """Split `text` around `[pause:N]` markers into an ordered list of ("text", str) / ("pause", float).

    N must be a number of seconds between MIN_PAUSE_SECONDS and MAX_PAUSE_SECONDS inclusive, e.g.
    [pause:2] or [pause:0.5]. Raises PiperError, naming the offending marker, for anything malformed
    or out of range. Deliberately plain — no Piper, no Tkinter — so it's fully testable on its own.
    See ADR 0009.
    """
    segments: list[tuple[str, "str | float"]] = []
    pos = 0
    for match in _PAUSE_MARKER_PATTERN.finditer(text):
        before = text[pos:match.start()]
        if before:
            segments.append(("text", before))

        raw_value = match.group(1).strip()
        try:
            seconds = float(raw_value)
        except ValueError:
            raise PiperError(
                f"'{match.group(0)}' isn't a valid pause marker — expected a number of seconds, "
                f"like [pause:2] or [pause:1.5]."
            )
        if not (MIN_PAUSE_SECONDS <= seconds <= MAX_PAUSE_SECONDS):
            raise PiperError(
                f"Pause duration {seconds}s in '{match.group(0)}' is outside the allowed "
                f"{MIN_PAUSE_SECONDS}-{MAX_PAUSE_SECONDS} second range."
            )
        segments.append(("pause", seconds))
        pos = match.end()

    remaining = text[pos:]
    if remaining or not segments:
        segments.append(("text", remaining))
    return segments


def synthesize(text: str, voice: str, voices_dir: Path, output_path: Path) -> None:
    """Synthesize `text` with `voice` and write a WAV file to `output_path`.

    `voice` is a Piper voice id (e.g. "en_US-lessac-medium"). It must already be downloaded:
    `voices_dir / f"{voice}.onnx"` (and the matching `.onnx.json`) must exist.

    `text` may contain inline `[pause:N]` markers (N seconds, between MIN_PAUSE_SECONDS and
    MAX_PAUSE_SECONDS) — each one inserts real silence at that point rather than being spoken
    aloud. Text with no markers behaves exactly as a single Piper call, unchanged from before
    markers existed. See ADR 0009.
    """
    segments = parse_pause_markers(text)
    if len(segments) == 1 and segments[0][0] == "text":
        _synthesize_one_shot(text, voice, voices_dir, output_path)
        return
    _synthesize_with_pauses(segments, voice, voices_dir, output_path)


def _synthesize_one_shot(text: str, voice: str, voices_dir: Path, output_path: Path) -> None:
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


def _synthesize_with_pauses(segments, voice: str, voices_dir: Path, output_path: Path) -> None:
    """Synthesize each text segment separately, then splice the results with real silence per pause."""
    if not any(kind == "text" and value.strip() for kind, value in segments):
        raise PiperError("No text to speak.")

    with tempfile.TemporaryDirectory(prefix="appliedpiper_chunks_") as tmp_dir:
        pieces: list[tuple[str, "Path | float"]] = []
        for index, (kind, value) in enumerate(segments):
            if kind == "text":
                if not value.strip():
                    continue
                chunk_path = Path(tmp_dir) / f"chunk_{index}.wav"
                _synthesize_one_shot(value, voice, voices_dir, chunk_path)
                pieces.append(("audio", chunk_path))
            else:
                pieces.append(("silence", value))

        _stitch_wav_pieces(pieces, output_path)


def _stitch_wav_pieces(pieces, output_path: Path) -> None:
    """Concatenate synthesized-audio pieces and silence pieces into one WAV file at `output_path`."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    first_audio_path = next((value for kind, value in pieces if kind == "audio"), None)
    if first_audio_path is None:
        raise PiperError("No text to speak.")

    with wave.open(str(first_audio_path), "rb") as probe:
        nchannels = probe.getnchannels()
        sampwidth = probe.getsampwidth()
        framerate = probe.getframerate()

    if sampwidth != 2:
        raise PiperError(
            f"Unexpected audio format ({sampwidth * 8}-bit); pause insertion assumes 16-bit PCM, "
            f"which is what every Piper voice produces by default."
        )

    with wave.open(str(output_path), "wb") as out_wav:
        out_wav.setnchannels(nchannels)
        out_wav.setsampwidth(sampwidth)
        out_wav.setframerate(framerate)

        for kind, value in pieces:
            if kind == "audio":
                with wave.open(str(value), "rb") as in_wav:
                    if (in_wav.getnchannels(), in_wav.getsampwidth(), in_wav.getframerate()) != (
                        nchannels, sampwidth, framerate,
                    ):
                        raise PiperError(
                            "Synthesized chunks have mismatched audio formats; can't splice them together."
                        )
                    out_wav.writeframes(in_wav.readframes(in_wav.getnframes()))
            else:
                n_frames = int(value * framerate)
                out_wav.writeframes(b"\x00" * (n_frames * sampwidth * nchannels))