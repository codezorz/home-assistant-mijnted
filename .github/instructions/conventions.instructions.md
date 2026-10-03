---
applyTo: "custom_components/mijnted/**"
description: Python imports, typing, async I/O, logging, constants, translations, and entity compatibility.
---

# Code conventions

- **Async**: Use async APIs for I/O; run unavoidable synchronous work in HA's executor. Declaring `async def` alone does not make blocking calls safe. Prefer Home Assistant helpers instead of reimplementing.
- **Typing**: Use type hints for arguments and return values (`Dict[str, Any]`, `Optional[...]`, `List[...]`, etc.).
- **Error handling**: Use exceptions from `exceptions.py`; raise with a clear message. Log at the right level (debug for flow, warning for recoverable, error/exception for failures). Do not swallow exceptions without logging.
- **Logging**: `_LOGGER = logging.getLogger(__name__)`. Use `debug` for verbose, `warning` for recoverable issues, `exception` only when logging an exception.
- **Constants**: Use `const.py` for shared URLs, timeouts, domain, status codes, and configuration defaults. Keep endpoint paths in the API/auth layers; do not spread HTTP details through coordinators or entities.
- **Imports**: Relative inside the integration (`from .const import DOMAIN`, `from ..utils import DateUtil`). Use `homeassistant` imports for HA APIs. Group and order: standard library, then third-party, then `homeassistant`, then relative (`.const`, `.utils`, etc.).
- **Config flow strings**: User-visible text must use keys from `translations/en.json`; reference the key in code.
- **Entity compatibility**: Preserve existing `unique_id` values, device identifiers, and registry identity. Naming/identity changes need an explicit migration or compatibility plan and release documentation; a release note alone does not migrate existing entities.

When in doubt, match the style of the existing file you are editing.
