"""Unit tests for tts.py.

subprocess.run is patched out in every test here — these never invoke a real Piper process. That's deliberate: this
suite checks tts.py's own logic (validation order, command construction, error translation), not whether Piper itself
works. We already confirmed that by hand with the raw CLI and a real synthesize() call.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from tts import PiperError, synthesize


@pytest.fixture
def voices_dir(tmp_path: Path) -> Path:
    """A voices directory with a fake 'installed' model already in it."""
    d = tmp_path / "voices"
    d.mkdir()
    (d / "en_US-lessac-medium.onnx").touch()
    (d / "en_US-lessac-medium.onnx.json").touch()
    return d


def test_blank_text_raises_without_touching_subprocess(voices_dir, tmp_path):
    with patch("tts.subprocess.run") as mock_run:
        with pytest.raises(PiperError, match="No text"):
            synthesize("   ", "en_US-lessac-medium", voices_dir, tmp_path / "out.wav")
    mock_run.assert_not_called()


def test_missing_voice_raises_without_touching_subprocess(tmp_path):
    empty_voices_dir = tmp_path / "voices"
    empty_voices_dir.mkdir()
    with patch("tts.subprocess.run") as mock_run:
        with pytest.raises(PiperError, match="isn't downloaded"):
            synthesize("hello", "en_US-lessac-medium", empty_voices_dir, tmp_path / "out.wav")
    mock_run.assert_not_called()


def test_successful_synthesis_builds_correct_command(voices_dir, tmp_path):
    out_path = tmp_path / "out.wav"

    def fake_run(cmd, **kwargs):
        # A real Piper process would write this file; simulate that so synthesize()'s post-condition check passes.
        out_path.write_bytes(b"RIFF....fake-wav-bytes")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("tts.subprocess.run", side_effect=fake_run) as mock_run:
        synthesize("Hello there.", "en_US-lessac-medium", voices_dir, out_path)

    assert out_path.exists()
    cmd = mock_run.call_args.args[0]
    assert "python" in Path(cmd[0]).name.lower()   # sys.executable
    assert "-m" in cmd and "piper" in cmd
    assert "--data-dir" in cmd and str(voices_dir) in cmd
    assert cmd[-2] == "--"             # separator immediately before the text
    assert cmd[-1] == "Hello there."   # text is the final positional arg


def test_nonzero_exit_code_raises_with_stderr_detail(voices_dir, tmp_path):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="model load failed")

    with patch("tts.subprocess.run", side_effect=fake_run):
        with pytest.raises(PiperError, match="model load failed"):
            synthesize("hello", "en_US-lessac-medium", voices_dir, tmp_path / "out.wav")


def test_missing_output_file_after_success_raises(voices_dir, tmp_path):
    def fake_run(cmd, **kwargs):
        # Piper reports success but wrote nothing — the defensive check.
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("tts.subprocess.run", side_effect=fake_run):
        with pytest.raises(PiperError, match="produced no output file"):
            synthesize("hello", "en_US-lessac-medium", voices_dir, tmp_path / "out.wav")


def test_piper_not_installed_raises_piper_error(voices_dir, tmp_path):
    with patch("tts.subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(PiperError, match="isn't installed"):
            synthesize("hello", "en_US-lessac-medium", voices_dir, tmp_path / "out.wav")


def test_piper_timeout_raises_piper_error(voices_dir, tmp_path):
    with patch("tts.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="piper", timeout=120)):
        with pytest.raises(PiperError, match="timed out"):
            synthesize("hello", "en_US-lessac-medium", voices_dir, tmp_path / "out.wav")