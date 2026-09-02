# 2. MIT license for this project's own code

## Status
Accepted

## Context
Piper itself is GPL-3.0-or-later. This project's own code (the GUI, the
`tts.py` wrapper, tests, docs) is a separate body of work. Because
[ADR 0001](0001-ShellOutToPiperCli.md) invokes Piper only as an
external subprocess rather than linking it in-process, this project's
own source isn't a GPL-derivative/combined work, and isn't obligated to
carry the GPL forward.

Voice models downloaded at runtime carry their own separate licenses
(commonly MIT or CC0, but not universally — each voice's `MODEL_CARD` on
Hugging Face states its own terms) and are never committed to this repo.

## Decision
This repository's own code is licensed MIT (see `/LICENSE`).

## Consequences
- Anyone can reuse this project's code freely, with attribution.
- If a future change imports Piper's Python API directly instead of
  shelling out to its CLI, this decision should be revisited — see the
  consequences section of [ADR 0001](0001-ShellOutToPiperCli.md#consequences).
- End users are still responsible for checking the license of whichever
  specific voice model they download and use.