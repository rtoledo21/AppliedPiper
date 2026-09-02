# 1. Shell out to Piper's CLI instead of importing it as a library

## Status
Accepted

## Context
Piper (the `piper-tts` package) can be used two ways: importing its
Python classes directly (`from piper.voice import PiperVoice`), or
invoking its command-line interface as a subprocess
(`python -m piper ...`). Two considerations pushed the decision:

**Technical.** Piper's internal Python API has changed shape across
recent releases (confirmed by comparing older tutorials, which show a
different import structure, against the current 1.7.0 source). Its CLI
is the documented, versioned public contract instead.

**Legal.** Piper is licensed GPL-3.0-or-later. GPL's copyleft applies to
*combined/derivative works* — code that is linked or imported into a
single running program. Whether invoking a GPL program as a separate
process (communicating over argv and files, not linked in-process)
constitutes a "combined work" is genuinely unsettled as a matter of
general copyright doctrine, but the FSF's own GPL FAQ treats
exec/pipe-style invocation of a separate program as the weak-entanglement
end of that question, distinct from linking. Importing Piper's Python
classes directly would put this application's own licensing on much
shakier ground the moment it's distributed.

*(Not legal advice — a genuinely unsettled area, weighed here as a
reasonable design position rather than a certainty.)*

## Decision
`tts.py` invokes Piper only via `sys.executable -m piper` and
`sys.executable -m piper.download_voices` as subprocesses. No code in
this project imports anything from the `piper` package directly.

## Consequences
- Upgrading Piper is safe as long as its CLI flags don't change; an
  internal API change in Piper can't break this app.
- Every Piper interaction costs a process spawn (milliseconds — not
  meaningful at this app's scale of "synthesize one utterance at a
  time").
- Testing `tts.py` means mocking `subprocess.run` rather than mocking a
  Piper object — see [ADR 0003](0003-UnitTests.md).
- This project's own code can be licensed independently of Piper's GPL
  (see [ADR 0002](0002-MitLicense.md)).