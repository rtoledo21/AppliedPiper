"""AppliedPiper GUI shell.

This piece is intentionally just layout: a window with the widgets the app needs, wired to nothing yet. Button clicks
currently just report to the status bar. Piece 4 replaces the button handlers with real calls into tts.synthesize() /
voices.download_voice(), off the main thread so the window doesn't freeze during synthesis.
"""

from __future__ import annotations

import platform
import queue
import subprocess
import tempfile
import threading
import tkinter as tk

from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tts import PiperError, synthesize
from voices import list_installed_voices

VOICES_DIR = Path(__file__).resolve().parent / "voice_data"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

def perform_synthesis(
    text: str,
    voice: str,
    voices_dir: Path,
    output_path: Path,
    synthesize_fn=synthesize,
) -> None:
    """GUI-level precondition check, then delegate to Piper.

    Raises PiperError either for a GUI-specific precondition (no voice selected) or whatever synthesize_fn itself
    raises. Deliberately plain — no Tkinter — so it's testable without constructing any widget. See ADR 0005 for why
    this split exists.
    """
    if not voice:
        raise PiperError("Pick a voice first — none is selected.")
    synthesize_fn(text, voice, voices_dir, output_path)

def reveal_in_file_manager(path: Path) -> None:
    """Open the OS file manager with `path` selected/highlighted, best-effort.

    Revealing a file is a convenience, not something synthesis should ever fail over —
    if the underlying command isn't available on this platform/PATH, this quietly does
    nothing rather than raising. Plain function, no Tkinter, same reasoning as
    perform_synthesis (see ADR 0005): testable without constructing any widget.
    """
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["open", "-R", str(path)])
        elif system == "Windows":
            subprocess.run(["explorer", "/select,", str(path)])
        else:
            subprocess.run(["xdg-open", str(path.parent)])
    except FileNotFoundError:
        pass

class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AppliedPiper")
        self.geometry("640x480")
        self.minsize(480, 360)

        self._result_queue: queue.Queue = queue.Queue()
        self._last_output_path: Path | None = None
        self._build_widgets()

    def _build_widgets(self) -> None:
        pad = {"padx": 10, "pady": 6}

        # --- text input ---------------------------------------------------
        text_frame = ttk.Frame(self)
        text_frame.pack(fill="both", expand=True, **pad)

        ttk.Label(text_frame, text="Text to speak").pack(anchor="w")

        text_container = ttk.Frame(text_frame)
        text_container.pack(fill="both", expand=True, pady=(4, 0))

        self.text_widget = tk.Text(text_container, wrap="word", height=12, undo=True)
        scrollbar = ttk.Scrollbar(text_container, command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=scrollbar.set)
        self.text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- voice picker ---------------------------------------------------
        voice_frame = ttk.Frame(self)
        voice_frame.pack(fill="x", **pad)

        ttk.Label(voice_frame, text="Voice:").pack(side="left")
        self.voice_var = tk.StringVar()
        installed = list_installed_voices(VOICES_DIR)
        self.voice_combo = ttk.Combobox(
            voice_frame,
            textvariable=self.voice_var,
            values=installed,
            state="readonly",  # forces picking from the list — no typing an
            width=32,          # id that was never actually downloaded
        )
        if installed:
            self.voice_var.set(installed[0])
        self.voice_combo.pack(side="left", padx=(6, 10))

        ttk.Button(voice_frame, text="Manage Voices…", command=self._not_wired_yet).pack(
            side="left"
        )

        # --- action buttons ---------------------------------------------------
        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", **pad)

        self.play_button = ttk.Button(button_frame, text="▶ Play", command=self._on_play_clicked)
        self.play_button.pack(side="left")

        self.save_button = ttk.Button(button_frame, text="Save As…", command=self._on_save_clicked)
        self.save_button.pack(side="left", padx=(8, 0))

        self.reveal_button = ttk.Button(
            button_frame, text="Show in Finder", command=self._on_reveal_clicked, state="disabled"
        )
        self.reveal_button.pack(side="left", padx=(8, 0))

        # --- status bar ---------------------------------------------------
        self.status_var = tk.StringVar(value="Layout only — nothing is wired up yet.")
        status_bar = ttk.Label(
            self, textvariable=self.status_var, anchor="w", relief="sunken", padding=(6, 3)
        )
        status_bar.pack(fill="x", side="bottom")

    def _on_play_clicked(self) -> None:
        text = self.text_widget.get("1.0", "end")
        voice = self.voice_var.get()
        output_path = OUTPUT_DIR / "play.wav"
        self._run_synthesis(text, voice, output_path, on_success_message=f"Synthesized to {output_path}")

    def _on_save_clicked(self) -> None:
        dest = filedialog.asksaveasfilename(
            defaultextension=".wav", filetypes=[("WAV audio", "*.wav")]
        )
        if not dest:
            return
        text = self.text_widget.get("1.0", "end")
        voice = self.voice_var.get()
        output_path = Path(dest)
        self._run_synthesis(text, voice, output_path, on_success_message=f"Saved to {output_path}")

    def _run_synthesis(self, text: str, voice: str, output_path: Path, on_success_message: str) -> None:
        self.play_button.configure(state="disabled")
        self.save_button.configure(state="disabled")
        self.status_var.set("Synthesizing…")

        def worker() -> None:
            # Do NOT touch self.after / any widget / any StringVar from here — this runs on a
            # background thread, and calling into Tk cross-thread is unreliable on some Tcl/Tk
            # builds (confirmed: it silently never fired on macOS Aqua Tk). Only ever hand data
            # to the plain, non-Tk queue below; the main thread does all the Tk work. See ADR 0006.
            try:
                perform_synthesis(text, voice, VOICES_DIR, output_path)
            except PiperError as exc:
                self._result_queue.put(("error", exc, None))
            else:
                self._result_queue.put(("done", on_success_message, output_path))

        threading.Thread(target=worker, daemon=True).start()
        self.after(50, self._poll_result_queue)

    def _poll_result_queue(self) -> None:
        """Runs only on the main thread, on its own self-rescheduled timer.

        This is the only place that reacts to the worker thread finishing. Because it's driven
        by self.after() called from the main thread (never from worker()), it never depends on
        cross-thread Tcl event delivery — it just checks a plain queue every 50ms.
        """
        try:
            kind, payload, output_path = self._result_queue.get_nowait()
        except queue.Empty:
            self.after(50, self._poll_result_queue)
            return

        if kind == "done":
            self._on_synthesis_done(payload, output_path)
        else:
            self._on_synthesis_error(payload)

    def _on_synthesis_done(self, message: str, output_path: Path) -> None:
        self.status_var.set(message)
        self.play_button.configure(state="normal")
        self.save_button.configure(state="normal")
        self._last_output_path = output_path
        self.reveal_button.configure(state="normal")

    def _on_synthesis_error(self, exc: PiperError) -> None:
        self.status_var.set("Error — see dialog.")
        self.play_button.configure(state="normal")
        self.save_button.configure(state="normal")
        messagebox.showerror("Synthesis failed", str(exc))

    def _on_reveal_clicked(self) -> None:
        if self._last_output_path is not None:
            reveal_in_file_manager(self._last_output_path)

    def _not_wired_yet(self) -> None:
        self.status_var.set("Not wired up yet — that's the next piece.")

def main() -> int:
    App().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())