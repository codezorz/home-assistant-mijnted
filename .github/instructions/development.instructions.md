---
applyTo: "custom_components/mijnted/**,tests/**,tests_native/**,.github/**,.agents/**,.claude/**,docs/**,AGENTS.md,CLAUDE.md,CONTRIBUTING.md,pyproject.toml,uv.lock,pytest.ini"
description: Development environment policy, dependency maintenance, and change-appropriate validation.
---

# Development rules

- Follow [the development guide](../../docs/DEVELOPMENT.md) for environment
  activation, dependency installation, validation commands, and HA smoke tests.
  Use the latest stable Python 3 for CI parity and HA's required Python in HA.
- Prefer the existing shared virtual environment when its requirements are
  compatible. Keep Windows and WSL environments separate; do not copy credentials
  or environments between checkouts automatically.
- Keep fast and native environments separate; follow the
  [reporting profile setup](../../docs/DEVELOPMENT.md#ha-native-reporting-tests) for `tests_native/`.
- Keep runtime dependency inputs aligned between the HA manifest and
  `pyproject.toml`. Commit dependency inputs and `uv.lock` together. Regenerate
  the ignored pip export with `--locked`; never commit it as a second source.
- Choose checks from the guide's change-to-check table. Add meaningful tests for
  behavior changes; do not add application tests for documentation-only edits.
- Treat syntax errors and failed behavioral assertions as blocking. Resolve
  missing dependencies in the documented environment. Report genuine HA-only
  verification gaps rather than treating them as passing tests; follow the
  [issue lifecycle policy](issues.instructions.md#completion-and-beta-feedback)
  for closure and post-merge beta feedback.
- [Testing instructions](testing.instructions.md) own test design and mocks;
  [CI instructions](ci.instructions.md) own workflow constraints. Keep detailed
  setup and troubleshooting in their linked guides rather than duplicating them.
