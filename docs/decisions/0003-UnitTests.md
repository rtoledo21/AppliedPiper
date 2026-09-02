# 3. Unit-test tts.py by mocking subprocess.run, not by faking a Piper binary

## Status
Accepted

## Context
Two ways to test code that shells out to an external program: (a) fake
the external program itself (e.g. put a stub `piper` package earlier on
`PYTHONPATH`) and let the real subprocess machinery run against it, or
(b) mock `subprocess.run` directly and never spawn a process at all.
Approach (a) was used informally while first building `tts.py`, before a
real Piper install was available to test against — useful as a quick
sanity check of argument-parsing and file-handling logic, but it's closer
to an integration test: it depends on there being a working Python
interpreter and process-spawning working correctly, and it's slower.

## Decision
The committed test suite (`tests/test_tts.py`) mocks `subprocess.run`
directly with `unittest.mock.patch`. Each test controls exactly what
`subprocess.run` returns (or raises) and asserts on the exact command
list `synthesize()` built, without spawning any process.

## Consequences
- Tests run in milliseconds and never depend on Piper actually being
  installed — they'd still pass in an environment with no Piper at all.
- Tests check the *shape* of the command sent to Piper (flags, ordering,
  the `--` separator, the text as the final positional argument) but
  can't catch a case where Piper itself changes what it expects — that's
  what the manual CLI smoke test (`python -m piper -m ... -- "..."`, run
  by hand) is for. Unit tests and that manual check are complementary,
  not redundant.