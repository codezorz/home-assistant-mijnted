---
applyTo: "**"
description: Project purpose and entry points for repository policies and validation.
---

# Repository overview

This repo is the Home Assistant MijnTed custom integration. It talks to the
MijnTed cloud API and exposes energy usage and device data as sensors/buttons.

- Domain: `mijnted`; runtime code: `custom_components/mijnted/`.
- No separate build; runtime dependencies are declared in `manifest.json`.
- Start with `AGENTS.md` for the instruction map and `README.md` for user setup.
- Follow `doc/DEVELOPMENT.md` for environment setup and validation.
- Follow `.github/instructions/git-workflow.instructions.md` for Git/version policy.
- Follow `.github/instructions/documentation.instructions.md` for doc ownership.
