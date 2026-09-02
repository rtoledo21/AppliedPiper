"""Voice management: listing what's downloaded, and downloading more.

Like tts.py, this shells out to Piper's CLI (`python -m piper.download_voices`) rather than importing Piper internals —
see docs/decisions/0001-shell-out-to-piper-cli.md for why. Failures raise tts.PiperError rather than a separate
exception type, so callers only ever need to catch one thing regardless of which module triggered it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tts import PiperError


def list_installed_voices(voices_dir: Path) -> list[str]:
    """Return the ids of voices already downloaded into `voices_dir`.

    A missing or empty directory returns an empty list — "no voices yet" is a normal state, not an error.
    """
    if not voices_dir.exists():
        return []
    return sorted(p.stem for p in voices_dir.glob("*.onnx"))


def download_voice(voice: str, voices_dir: Path, timeout: int = 300) -> None:
    """Download a Piper voice by id into `voices_dir`.

    Delegates voice resolution, checksums, and licensing entirely to Piper's own `piper.download_voices` module — this
    project never hardcodes a Hugging Face URL.
    """
    voices_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "piper.download_voices",
        voice,
        "--data-dir",
        str(voices_dir),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise PiperError("Piper isn't installed in this environment.") from exc
    except subprocess.TimeoutExpired as exc:
        raise PiperError("Voice download timed out.") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise PiperError(
            f"Couldn't download voice '{voice}':\n{detail}\n\n"
            "Double-check the exact voice id at "
            "https://huggingface.co/rhasspy/piper-voices/tree/main"
        )