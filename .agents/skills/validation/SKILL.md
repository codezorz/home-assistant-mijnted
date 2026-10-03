---
name: validation
description: Use when validating changes in this Home Assistant integration repo, including fast syntax checks and test guidance outside full HA runtime.
---

# Validation

Follow `doc/DEVELOPMENT.md` for environment setup, commands, CI expectations,
and the distinction between local tests and Home Assistant runtime checks.
Read `.github/instructions/testing.instructions.md` when editing tests.

1. Choose checks appropriate to the changes, using the preferred environment.
2. Treat syntax errors and failed behavioral assertions as blocking. Diagnose
   missing dependencies and HA runtime limitations rather than reporting a pass.
3. For runtime-sensitive changes, perform or describe the needed HA smoke test.
4. Report commands, results, and any verification that could not be performed.
