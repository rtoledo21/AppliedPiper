"""AppliedPiper GUI shell.

This piece is intentionally just layout: a window with the widgets the app needs, wired to nothing yet. Button clicks
currently just report to the status bar. Piece 4 replaces the button handlers with real calls into tts.synthesize() /
voices.download_voice(), off the main thread so the window doesn't freeze during synthesis.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from voices import list_installed_voices

VOICES_DIR = Path(__file__).resolve().parent / "voice_data"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AppliedPiper")
        self.geometry("640x480")
        self.minsize(480, 360)

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

        self.play_button = ttk.Button(button_frame, text="▶ Play", command=self._not_wired_yet)
        self.play_button.pack(side="left")

        self.save_button = ttk.Button(button_frame, text="Save As…", command=self._not_wired_yet)
        self.save_button.pack(side="left", padx=(8, 0))

        # --- status bar ---------------------------------------------------
        self.status_var = tk.StringVar(value="Layout only — nothing is wired up yet.")
        status_bar = ttk.Label(
            self, textvariable=self.status_var, anchor="w", relief="sunken", padding=(6, 3)
        )
        status_bar.pack(fill="x", side="bottom")

    def _not_wired_yet(self) -> None:
        self.status_var.set("Not wired up yet — that's the next piece.")


def main() -> int:
    App().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())