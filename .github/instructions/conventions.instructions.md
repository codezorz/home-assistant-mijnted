---
applyTo: "custom_components/mijnted/**"
---

# Code conventions

- **Async**: Use `async def` and `await` for I/O. Prefer Home Assistant helpers instead of reimplementing.
- **Typing**: Use type hints for arguments and return values (`Dict[str, Any]`, `Optional[...]`, `List[...]`, etc.).
- **Logging**: `_LOGGER = logging.getLogger(__name__)`. Use `debug` for verbose, `warning` for recoverable issues, `exception` only when logging an exception.
- **Constants**: Do not hardcode URLs, timeouts, or domain. Use `const.py` (e.g. `DOMAIN`, `API_BASE_URL`, `DEFAULT_POLLING_INTERVAL`).
- **Imports**: Relative inside the integration (`from .const import DOMAIN`, `from ..utils import DateUtil`). Use `homeassistant` imports for HA APIs.
- **Config flow strings**: User-visible text must use keys from `translations/en.json`; reference the key in code.
- **Breaking changes**: Avoid renaming or removing entities or changing `unique_id` without a migration or release note.

When in doubt, match the style of the existing file you are editing.
