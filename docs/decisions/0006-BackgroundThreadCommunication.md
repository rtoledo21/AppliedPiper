# 6. Background threads report results through a queue, never through direct Tk calls

## Status

Accepted

## Context

Piece 4 wired the Play/Save buttons to run `perform_synthesis()` on a background
`threading.Thread` so a multi-second Piper subprocess call doesn't freeze the Tkinter
event loop. The worker thread needs to tell the GUI when it's done — update the status
bar, re-enable the buttons. The obvious-looking approach, and the one most
Tkinter-plus-threading tutorials show, is to call `self.after(0, callback)` directly from
inside the worker thread, relying on CPython's `_tkinter` module to marshal that call onto
the main thread via `Tcl_ThreadQueueEvent`.

That's what piece 4 originally did, and `test_play_button_success_updates_status_via_background_thread`
failed deterministically because of it — not flaky, identical failure on three consecutive
runs, `status_var` stuck at `"Synthesizing…"` no matter how long the test polled with
`instance.update()`. The queued `after()` callback simply never fired. This tracks a known
rough edge in macOS's Aqua Tk build: a background thread's queued Tcl event doesn't
reliably wake the main thread's Cocoa-integrated event notifier the way it does on
X11/Win32 Tk builds. The "safe cross-thread `after()`" pattern isn't actually safe on
every platform it's commonly used on.

## Decision

The background worker thread never touches any Tkinter object or method — not
`self.after`, not a `StringVar`, nothing. It only puts a `(kind, payload)` tuple onto a
`queue.Queue` (thread-safe via the GIL, no Tcl involvement whatsoever). All Tk interaction
— draining the queue, updating `status_var`, re-enabling buttons — happens on the main
thread only, driven by a self-rescheduling `self.after(50, self._poll_result_queue)` loop
that the main thread sets up itself and keeps renewing every 50ms until it finds a result.

## Consequences

- One extra queue attribute and one small polling method
  (`_poll_result_queue`), in exchange for behavior that doesn't depend on how a given
  platform's Tcl/Tk build happens to handle cross-thread event posting.
- Status updates land up to ~50ms after the worker actually finishes rather than
  immediately — imperceptible given Piper synthesis itself takes hundreds of
  milliseconds to seconds.
- `test_play_button_success_updates_status_via_background_thread` needed no changes: it
  already polls via `instance.update()` in a loop, and now actually observes the update,
  because the `after()` callback it's waiting on is scheduled from the main thread, never
  queued from a background thread.
- General rule going forward for this codebase: a `threading.Thread` target function may
  do real work and call plain Python objects (queues, files, subprocess), but must never
  call a Tk widget method, a `tkinter.Variable`, or `self.after()` directly.
