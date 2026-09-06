"""Unit tests for tts.py.

subprocess.run is patched out in every test here — these never invoke a real Piper process. That's deliberate: this
suite checks tts.py's own logic (validation order, command construction, error translation), not whether Piper itself
works. We already confirmed that by hand with the raw CLI and a real synthesize() call.
"""

import subprocess
import wave
from pathlib import Path
from unittest.mock import patch

import pytest

from tts import PiperError, synthesize, parse_pause_markers, MIN_PAUSE_SECONDS, MAX_PAUSE_SECONDS


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

# --- parse_pause_markers: plain, no subprocess involved. See ADR 0009. ---

def test_parse_pause_markers_returns_whole_text_when_no_markers():
    assert parse_pause_markers("hello world") == [("text", "hello world")]


def test_parse_pause_markers_splits_around_a_marker():
    assert parse_pause_markers("hello [pause:2] world") == [
        ("text", "hello "),
        ("pause", 2.0),
        ("text", " world"),
    ]


def test_parse_pause_markers_handles_marker_at_start():
    assert parse_pause_markers("[pause:1.5]hello") == [
        ("pause", 1.5),
        ("text", "hello"),
    ]


def test_parse_pause_markers_handles_marker_at_end():
    assert parse_pause_markers("hello[pause:1]") == [
        ("text", "hello"),
        ("pause", 1.0),
    ]


def test_parse_pause_markers_handles_back_to_back_markers():
    assert parse_pause_markers("[pause:1][pause:2]") == [
        ("pause", 1.0),
        ("pause", 2.0),
    ]


def test_parse_pause_markers_accepts_boundary_values():
    assert parse_pause_markers(f"a[pause:{MIN_PAUSE_SECONDS}]b") == [
        ("text", "a"), ("pause", MIN_PAUSE_SECONDS), ("text", "b"),
    ]
    assert parse_pause_markers(f"a[pause:{MAX_PAUSE_SECONDS}]b") == [
        ("text", "a"), ("pause", MAX_PAUSE_SECONDS), ("text", "b"),
    ]


def test_parse_pause_markers_rejects_too_short_duration():
    with pytest.raises(PiperError, match="outside the allowed"):
        parse_pause_markers("hi [pause:0.1] there")


def test_parse_pause_markers_rejects_too_long_duration():
    with pytest.raises(PiperError, match="outside the allowed"):
        parse_pause_markers("hi [pause:10] there")


def test_parse_pause_markers_rejects_non_numeric_duration():
    with pytest.raises(PiperError, match="isn't a valid pause marker"):
        parse_pause_markers("hi [pause:abc] there")


# --- synthesize() with pause markers: chunked Piper calls + wave-module splicing. ---

def _write_fake_wav(path: Path, seconds: float = 0.1, framerate: int = 22050, sampwidth: int = 2) -> None:
    """A minimal real WAV file — unlike the fake 'RIFF....' bytes used above, this one is actually
    readable by the wave module, which the pause-splicing code needs to do to read chunks back."""
    n_frames = int(seconds * framerate)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(sampwidth)
        w.setframerate(framerate)
        w.writeframes(b"\x00" * (n_frames * sampwidth))


def test_synthesize_without_pause_markers_calls_subprocess_once(voices_dir, tmp_path):
    out_path = tmp_path / "out.wav"

    def fake_run(cmd, **kwargs):
        out_path.write_bytes(b"RIFF....fake-wav-bytes")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("tts.subprocess.run", side_effect=fake_run) as mock_run:
        synthesize("hello there", "en_US-lessac-medium", voices_dir, out_path)

    assert mock_run.call_count == 1


def test_synthesize_with_single_pause_marker_produces_correct_total_duration(voices_dir, tmp_path):
    out_path = tmp_path / "out.wav"

    def fake_run(cmd, **kwargs):
        chunk_path = Path(cmd[cmd.index("-f") + 1])
        _write_fake_wav(chunk_path, seconds=0.1)
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("tts.subprocess.run", side_effect=fake_run) as mock_run:
        synthesize("hello [pause:1] world", "en_US-lessac-medium", voices_dir, out_path)

    assert mock_run.call_count == 2  # one Piper call per text chunk -- none for the pause itself
    texts_sent_to_piper = [call.args[0][-1] for call in mock_run.call_args_list]
    assert texts_sent_to_piper == ["hello ", " world"]

    assert out_path.exists()
    with wave.open(str(out_path), "rb") as w:
        total_seconds = w.getnframes() / w.getframerate()
    # 0.1s + 0.1s of (fake) speech plus a full 1s pause, give or take rounding.
    assert total_seconds == pytest.approx(1.2, abs=0.01)


def test_synthesize_with_pause_marker_propagates_chunk_failure(voices_dir, tmp_path):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="boom")

    with patch("tts.subprocess.run", side_effect=fake_run):
        with pytest.raises(PiperError, match="boom"):
            synthesize("hello [pause:1] world", "en_US-lessac-medium", voices_dir, tmp_path / "out.wav")


def test_synthesize_with_only_a_pause_marker_and_no_text_raises(voices_dir, tmp_path):
    with patch("tts.subprocess.run") as mock_run:
        with pytest.raises(PiperError, match="No text to speak"):
            synthesize("[pause:1]", "en_US-lessac-medium", voices_dir, tmp_path / "out.wav")
    mock_run.assert_not_called()


def test_synthesize_with_pause_marker_rejects_non_16bit_chunks(voices_dir, tmp_path):
    def fake_run(cmd, **kwargs):
        chunk_path = Path(cmd[cmd.index("-f") + 1])
        _write_fake_wav(chunk_path, seconds=0.1, sampwidth=1)  # 8-bit -- not what Piper actually produces
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("tts.subprocess.run", side_effect=fake_run):
        with pytest.raises(PiperError, match="16-bit PCM"):
            synthesize("hello [pause:1] world", "en_US-lessac-medium", voices_dir, tmp_path / "out.wav")
