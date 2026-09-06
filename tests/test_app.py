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

from app import App, perform_synthesis, reveal_in_file_manager, next_play_output_path
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


# --- reveal_in_file_manager: a plain, Tkinter-free function (same MVC split as
# perform_synthesis, per ADR 0005) that shells out to the OS's file manager. ---

def test_reveal_in_file_manager_uses_open_dash_r_on_macos(monkeypatch, tmp_path):
    monkeypatch.setattr("app.platform.system", lambda: "Darwin")
    calls = []
    monkeypatch.setattr("app.subprocess.run", lambda cmd, **kwargs: calls.append(cmd))
    target = tmp_path / "play.wav"
    reveal_in_file_manager(target)
    assert calls == [["open", "-R", str(target)]]


def test_reveal_in_file_manager_uses_explorer_on_windows(monkeypatch, tmp_path):
    monkeypatch.setattr("app.platform.system", lambda: "Windows")
    calls = []
    monkeypatch.setattr("app.subprocess.run", lambda cmd, **kwargs: calls.append(cmd))
    target = tmp_path / "play.wav"
    reveal_in_file_manager(target)
    assert calls == [["explorer", "/select,", str(target)]]


def test_reveal_in_file_manager_uses_xdg_open_on_linux(monkeypatch, tmp_path):
    monkeypatch.setattr("app.platform.system", lambda: "Linux")
    calls = []
    monkeypatch.setattr("app.subprocess.run", lambda cmd, **kwargs: calls.append(cmd))
    target = tmp_path / "play.wav"
    reveal_in_file_manager(target)
    assert calls == [["xdg-open", str(target.parent)]]


def test_reveal_in_file_manager_swallows_missing_command(monkeypatch, tmp_path):
    monkeypatch.setattr("app.platform.system", lambda: "Darwin")

    def raise_not_found(cmd, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("app.subprocess.run", raise_not_found)
    # Must not raise: revealing a file is a convenience, not something that should
    # crash synthesis if `open`/`explorer`/`xdg-open` isn't on PATH for some reason.
    reveal_in_file_manager(tmp_path / "play.wav")


# --- GUI integration: Play's fixed output location + the reveal button. ---

def test_reveal_button_starts_disabled(app):
    assert str(app.reveal_button["state"]) == "disabled"


# --- next_play_output_path: plain, Tkinter-free, per ADR 0008. ---

def test_next_play_output_path_returns_play_1_for_missing_dir(tmp_path):
    missing_dir = tmp_path / "does_not_exist_yet"
    assert next_play_output_path(missing_dir) == missing_dir / "play_1.wav"


def test_next_play_output_path_returns_play_1_for_empty_dir(tmp_path):
    assert next_play_output_path(tmp_path) == tmp_path / "play_1.wav"


def test_next_play_output_path_increments_past_highest_existing_number(tmp_path):
    (tmp_path / "play_1.wav").touch()
    (tmp_path / "play_2.wav").touch()
    (tmp_path / "play_7.wav").touch()
    assert next_play_output_path(tmp_path) == tmp_path / "play_8.wav"


def test_next_play_output_path_ignores_unrelated_filenames(tmp_path):
    (tmp_path / "play_3.wav").touch()
    (tmp_path / "notes.txt").touch()
    (tmp_path / "play_x.wav").touch()  # non-numeric -- must not match
    (tmp_path / "saved.wav").touch()   # different prefix -- must not match
    assert next_play_output_path(tmp_path) == tmp_path / "play_4.wav"


# --- GUI integration: Play now delegates path selection to next_play_output_path. ---

def test_play_uses_next_play_output_path_and_enables_reveal(monkeypatch, tmp_path):
    (tmp_path / "en_US-lessac-medium.onnx").touch()
    monkeypatch.setattr("app.VOICES_DIR", tmp_path)

    expected_path = tmp_path / "out" / "play_3.wav"
    monkeypatch.setattr("app.next_play_output_path", lambda output_dir: expected_path)

    captured = {}

    def fake_perform_synthesis(text, voice, voices_dir, output_path):
        captured["output_path"] = output_path

    monkeypatch.setattr("app.perform_synthesis", fake_perform_synthesis)

    instance = App()
    try:
        instance.text_widget.insert("1.0", "hello")
        instance.voice_var.set("en_US-lessac-medium")
        instance.play_button.invoke()

        for _ in range(50):
            instance.update()
            if instance.status_var.get().startswith("Synthesized"):
                break
            time.sleep(0.02)

        assert captured["output_path"] == expected_path
        assert instance._last_output_path == expected_path
        assert str(instance.reveal_button["state"]) == "normal"
    finally:
        instance.destroy()


def test_reveal_button_click_calls_reveal_with_last_output_path(monkeypatch, tmp_path):
    (tmp_path / "en_US-lessac-medium.onnx").touch()
    monkeypatch.setattr("app.VOICES_DIR", tmp_path)
    monkeypatch.setattr("app.OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr("app.perform_synthesis", lambda *a, **k: None)

    revealed = []
    monkeypatch.setattr("app.reveal_in_file_manager", lambda p: revealed.append(p))

    instance = App()
    try:
        instance.text_widget.insert("1.0", "hello")
        instance.voice_var.set("en_US-lessac-medium")
        instance.play_button.invoke()

        for _ in range(50):
            instance.update()
            if str(instance.reveal_button["state"]) == "normal":
                break
            time.sleep(0.02)

        instance.reveal_button.invoke()
        assert revealed == [tmp_path / "out" / "play_1.wav"]
    finally:
        instance.destroy()
