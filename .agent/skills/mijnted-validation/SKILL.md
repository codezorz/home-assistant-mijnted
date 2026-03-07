---
name: mijnted-validation
description: Use when validating changes in this Home Assistant integration repo, including fast syntax checks and test guidance outside full HA runtime.
---

# Mijnted Validation

Use this skill to run practical local validation for this repository.

## Primary quick check

Run a syntax check first:

`python -m compileall custom_components/mijnted`

If sandbox mode cannot write `__pycache__`, rerun outside sandbox.

## Environment

Activate the project venv before running checks:

- Linux/macOS (`bash`/`zsh`): `source ~/.venv-home-assistant/bin/activate`
- Windows PowerShell: `& "$HOME\.venv-home-assistant\Scripts\Activate.ps1"`
- Windows cmd: `%USERPROFILE%\.venv-home-assistant\Scripts\activate.bat`

Using system Python can fail with missing test/runtime deps (for example `aiohttp` or `pytest-asyncio`).

## Test guidance

- Tests are in `tests/`, configured via `pytest.ini`.
- Test dependencies are listed in `requirements_test.txt`.
- This repo often validates outside a full Home Assistant runtime.

## Blocking vs non-blocking outcomes

- Blocking:
  - Python syntax or parse errors.
- Usually non-blocking in local validation:
  - Home Assistant runtime/environment-specific issues that require full HA context.

## Suggested order

1. `python -m compileall custom_components/mijnted`
2. If needed, run `pytest` for targeted or full tests.
3. Report what was run and any remaining gaps.

## References

- `AGENTS.md`
- `.github/instructions/testing.instructions.md`
- `requirements_test.txt`
- `pytest.ini`
