"""Tests for app.py's view layer.

Per ADR 0006, this suite tests two things: that the app constructs without error, and that its initial state correctly
reflects its inputs. It does not test layout/appearance. Once piece 4 introduces button handlers with real logic, those
get tested via .invoke() against a mocked controller function — see ADR 0006 for the pattern.

Note: these construct real Tk() windows. You'll see windows flash open and close rapidly while this runs — that's
expected, not a bug.
"""

import pytest

from app import App


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


def test_play_button_reports_not_wired_yet(app):
    app.play_button.invoke()
    assert "next piece" in app.status_var.get()