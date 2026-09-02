# 5. Test the GUI's view/controller seam, not just business logic

## Status
Accepted

## Context
`app.py` is the first module in this codebase that isn't a pure function
of its inputs — it's Tkinter widgets. Two things are true at once:
visual appearance (pixel position, whether it looks right) genuinely
resists automated assertion and is better verified by running the app
and looking at it; but Tkinter widgets are also real, inspectable Python
objects — `Tk()` and its children can be constructed and asserted on
directly, and buttons expose `.invoke()` to fire their bound command
without a real click. Given this project exists specifically to
demonstrate an ability to deliver test-driven, professionally-structured
software, leaving the entire GUI module with zero coverage would be a
worse signal than the "can't test pixel layout" limitation it would be
avoiding.

## Decision
Two things:

1. `app.py` gets tests for what's actually testable: that the app
   constructs without error (a smoke test), and that its initial state
   reflects its inputs correctly (e.g. the voice picker is populated
   from `list_installed_voices()`).
2. Button handlers are split into a thin Tkinter-facing method (reads
   widget state, calls a plain function, writes the result back to a
   widget) and a plain, Tkinter-free function containing the actual
   decision logic (what to call, how to interpret success/failure). The
   plain function is unit tested normally, with dependencies like
   `synthesize()` passed in and mocked. The thin method is exercised via
   `.invoke()` on the real button, mocking only the plain function
   underneath it.

This is the standard Model-View-Controller/Presenter separation applied
to a Tkinter app: view code (widgets) stays thin and mostly untested;
everything with actual branching logic lives outside the view and is
fully tested.

## Consequences
- Pure layout (padding, geometry, colors) is still not something this
  suite verifies — that remains a manual, run-it-and-look check.
- Every button's `command=` handler should be a short, boring function
  that reads inputs, calls one thing, writes one result — if a handler
  ever grows real branching logic, that's a signal to extract it into a
  plain function per the pattern above.
- Tests that construct real `Tk()` widgets require a live display; they
  run fine locally but would need Xvfb in a headless CI environment if
  one is ever added.