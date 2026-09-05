"""Tests for app.py's view layer.

Per ADR 0005, this suite tests two things: that the app constructs without error, and that its initial state correctly
reflects its inputs. It does not test layout/appearance. Once piece 4 introduces button handlers with real logic, those
get tested via .invoke() against a mocked controller function — see ADR 0005 for the pattern.

Note: these construct real Tk() windows. You'll see windows flash open and close rapidly while this runs — that's
expected, not a bug.
"""

import pytest
import time

from unittest.mock import Mock

from app import App, perform_synthesis
from tts import PiperError


@pytest.fixture
def app(monkeypatch, tmp_path):
    """A real App instance pointed at an isolated, empty voice directory."""
    monkeypatch.setattr("app.VOICES_DIR", tmp_path)
    instance = App()
    yield instance
    instance.destroy()


def test_app_constructs_without_error(app):
    # If __init__ had raised, this fixture would have failed before the test body ever ran — this assertion just
    # documents the intent.
    assert app.winfo_exists()


def test_voice_picker_is_empty_when_no_voices_installed(app):
    assert not app.voice_combo["values"]
    assert app.voice_var.get() == ""


def test_voice_picker_populated_from_voices_dir(monkeypatch, tmp_path):
    (tmp_path / "en_US-lessac-medium.onnx").touch()
    (tmp_path / "en_GB-alan-medium.onnx").touch()
    monkeypatch.setattr("app.VOICES_DIR", tmp_path)

    instance = App()
    try:
        assert list(instance.voice_combo["values"]) == [
            "en_GB-alan-medium",
            "en_US-lessac-medium",
        ]
        assert instance.voice_var.get() == "en_GB-alan-medium"  # first, alphabetically
    finally:
        instance.destroy()


# def test_play_button_reports_not_wired_yet(app):
#     app.play_button.invoke()
#     assert "next piece" in app.status_var.get()


def test_perform_synthesis_raises_if_no_voice_selected(tmp_path):
    fake_synthesize = Mock()
    with pytest.raises(PiperError, match="Pick a voice"):
        perform_synthesis(
            "hello", "", tmp_path, tmp_path / "out.wav", synthesize_fn=fake_synthesize
        )
    fake_synthesize.assert_not_called()


def test_perform_synthesis_calls_synthesize_fn_with_right_args(tmp_path):
    fake_synthesize = Mock()
    out_path = tmp_path / "out.wav"
    perform_synthesis(
        "hello there", "en_US-lessac-medium", tmp_path, out_path,
        synthesize_fn=fake_synthesize,
    )
    fake_synthesize.assert_called_once_with(
        "hello there", "en_US-lessac-medium", tmp_path, out_path
    )


def test_perform_synthesis_propagates_piper_errors(tmp_path):
    fake_synthesize = Mock(side_effect=PiperError("boom"))
    with pytest.raises(PiperError, match="boom"):
        perform_synthesis(
            "hello", "en_US-lessac-medium", tmp_path, tmp_path / "out.wav",
            synthesize_fn=fake_synthesize,
        )


def test_play_button_success_updates_status_via_background_thread(monkeypatch, tmp_path):
    (tmp_path / "en_US-lessac-medium.onnx").touch()
    monkeypatch.setattr("app.VOICES_DIR", tmp_path)
    monkeypatch.setattr("app.perform_synthesis", lambda *a, **k: None)

    instance = App()
    try:
        instance.text_widget.insert("1.0", "hello")
        instance.voice_var.set("en_US-lessac-medium")
        instance.play_button.invoke()

        for _ in range(50):  # up to ~1s, polling since this crosses a real thread
            instance.update()
            if instance.status_var.get().startswith("Synthesized"):
                break
            time.sleep(0.02)

        assert instance.status_var.get().startswith("Synthesized")
        assert str(instance.play_button["state"]) == "normal"
    finally:
        instance.destroy()