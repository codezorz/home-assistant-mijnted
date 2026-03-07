# Reporting Issues

Use this guide when opening a GitHub issue for this integration.

GitHub issue forms are available by default:
- `Bug report`
- `Feature request`
- `Question`

## Before opening an issue

1. Search existing issues first to avoid duplicates.
2. Confirm you are running the latest release of the integration.
3. Reproduce the problem at least once with debug logging enabled.
4. Remove secrets from logs and screenshots (client ID, tokens, email, passwords).

## Choose the right issue type

- Bug: Something that worked before or should work but does not.
- Feature request: New behavior or improvement.
- Question: Clarification about setup or behavior.

## What to include in a bug report

1. Short summary
2. Exact steps to reproduce
3. Expected behavior
4. Actual behavior
5. Relevant logs (full stack trace or warning block)
6. Environment details:
   - Home Assistant version
   - Integration version (`custom_components/mijnted/manifest.json`)
   - Python version (if available)
7. Screenshots (if UI-related)

## Bug report template

Copy this into a new issue and fill it in:

````md
## Summary
<!-- One sentence describing the problem -->

## Reproduction
1.
2.
3.

## Expected behavior
<!-- What should happen -->

## Actual behavior
<!-- What happens instead -->

## Logs
```text
<!-- Paste full warning/error block here -->
```

## Environment
- Home Assistant version:
- MijnTed integration version:
- Python version:

## Additional context
<!-- Screenshots, related issues, workarounds -->
````

## Suggested labels

- `bug` for failures and regressions
- `enhancement` for feature requests
- `question` for support-style issues
- Maintainers may adjust labels during triage or closure (for example: `duplicate`, `invalid`, `wontfix`).
