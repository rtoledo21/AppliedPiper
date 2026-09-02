# 4. Never name a runtime data directory the same as a source module

## Status
Accepted

## Context
While writing `tests/test_voices.py` before `voices.py` existed, running
the suite produced a confusing error:

    ImportError: cannot import name 'download_voice' from 'voices' (unknown location)

instead of the expected `ModuleNotFoundError: No module named 'voices'`.
The cause: an earlier manual smoke test had run
`python -m piper.download_voices en_US-lessac-medium --data-dir voices`,
which created a real directory named `voices/` at the project root to
hold the downloaded model files. With no `voices.py` yet, Python's
import system found that bare directory (no `__init__.py`) and — per
PEP 420 — treated it as an empty namespace package instead of failing
cleanly. `(unknown location)` is what a namespace package reports, since
it has no single `__file__`.

Once `voices.py` exists, Python's finder does prioritize a real module
file over a same-named bare directory in the same folder, so the
collision would have resolved itself silently. That's the actual
problem: depending on obscure import-resolution precedence to make a
same-named file and directory coexist is fragile and non-obvious to
anyone reading the repo later, even when it technically works.

## Decision
Runtime data directories are never named identically to a source module.
The downloaded-voice-models directory is `voice_data/`, not `voices/`,
specifically so it can't collide with `voices.py`.

## Consequences
- One less class of confusing import error, now and for any future
  module.
- Slight naming asymmetry (the module is `voices.py`, the data lives in
  `voice_data/`) — an acceptable, deliberate tradeoff against import
  ambiguity.
- General rule going forward: before naming a new top-level directory
  (data, config, cache, whatever), check it doesn't shadow — or get
  shadowed by — a same-named module.