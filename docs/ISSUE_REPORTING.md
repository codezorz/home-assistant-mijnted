# Reporting Issues

Use this guide when opening a GitHub issue for this integration.

Choose the appropriate GitHub issue form:
- [Bug report](https://github.com/codezorz/home-assistant-mijnted/issues/new?template=bug_report.yml): reproducible faulty behavior.
- [Feature request](https://github.com/codezorz/home-assistant-mijnted/issues/new?template=feature_request.yml): a new capability or improvement.
- [Question](https://github.com/codezorz/home-assistant-mijnted/issues/new?template=question.yml): setup or behavior clarification.

## Before opening an issue

1. Search existing issues first to avoid duplicates.
2. Check the latest releases and note the exact release or beta you tested.
3. For bugs, reproduce the problem with debug logging enabled.
4. Remove secrets from logs and screenshots (client ID, tokens, email, passwords).

Use [SECURITY.md](../SECURITY.md) for private vulnerability reports instead of
public issues. Enable logging as described in [README.md](../README.md#troubleshooting).

## Diagnostic context

The forms define the required report fields. Include screenshots for UI problems
and the complete relevant warning or traceback when reporting errors.

For stale readings or month-boundary issues, also include the **Last update**
and **Last successful sync** values, the affected month IDs/statuses from Total
usage attributes, and whether the issue survives a reload/restart. A successful
sync timestamp does not guarantee that every endpoint succeeded. See
[sensor behavior](SENSORS.md) and [month transitions](MONTH_SWITCH.md).

Maintainers choose labels during triage. Select the issue form that best matches
your report; you do not need to assign labels yourself.

For maintainer issue creation, completion, and beta feedback, follow the
[issue instructions](../.github/instructions/issues.instructions.md).
