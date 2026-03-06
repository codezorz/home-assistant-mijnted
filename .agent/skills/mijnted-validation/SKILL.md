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

