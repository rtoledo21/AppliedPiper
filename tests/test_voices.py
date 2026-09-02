"""Unit tests for voices.py.

Written before voices.py exists (TDD) — these will fail with a collection error until the module and its two functions
are implemented. That's the expected 'red' state. See tts.py's test suite for why subprocess.run is mocked rather than
invoking a real Piper process.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from tts import PiperError
from voices import download_voice, list_installed_voices


# ---- list_installed_voices -------------------------------------------

def test_list_installed_voices_returns_empty_list_for_missing_dir(tmp_path):
    missing = tmp_path / "does-not-exist"
    assert list_installed_voices(missing) == []


def test_list_installed_voices_returns_empty_list_for_empty_dir(tmp_path):
    assert list_installed_voices(tmp_path) == []


def test_list_installed_voices_finds_onnx_files_by_stem(tmp_path):
    (tmp_path / "en_US-lessac-medium.onnx").touch()
    (tmp_path / "en_US-lessac-medium.onnx.json").touch()
    (tmp_path / "en_GB-alan-medium.onnx").touch()
    (tmp_path / "en_GB-alan-medium.onnx.json").touch()
    (tmp_path / "not-a-voice.txt").touch()  # should be ignored

    assert list_installed_voices(tmp_path) == [
        "en_GB-alan-medium",
        "en_US-lessac-medium",
    ]  # sorted


# ---- download_voice ----------------------------------------------------

def test_download_voice_builds_correct_command(tmp_path):
    voices_dir = tmp_path / "voices"

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("voices.subprocess.run", side_effect=fake_run) as mock_run:
        download_voice("en_US-lessac-medium", voices_dir)

    cmd = mock_run.call_args.args[0]
    assert "python" in Path(cmd[0]).name.lower()
    assert "-m" in cmd and "piper.download_voices" in cmd
    assert "en_US-lessac-medium" in cmd
    assert "--data-dir" in cmd and str(voices_dir) in cmd


def test_download_voice_creates_voices_dir_if_missing(tmp_path):
    voices_dir = tmp_path / "does" / "not" / "exist-yet"

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("voices.subprocess.run", side_effect=fake_run):
        download_voice("en_US-lessac-medium", voices_dir)

    assert voices_dir.exists()


def test_download_voice_raises_piper_error_on_failure(tmp_path):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="no such voice")

    with patch("voices.subprocess.run", side_effect=fake_run):
        with pytest.raises(PiperError, match="no such voice"):
            download_voice("bogus-voice", tmp_path / "voices")


def test_download_voice_raises_piper_error_if_piper_missing(tmp_path):
    with patch("voices.subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(PiperError):
            download_voice("en_US-lessac-medium", tmp_path / "voices")