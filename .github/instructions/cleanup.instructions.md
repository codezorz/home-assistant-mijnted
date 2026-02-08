---
applyTo: "custom_components/mijnted/**"
---

# Clean coding

- **One responsibility**: Each function or class should do one thing. Split long functions; extract helpers into `utils/` when reusable and pure.
- **Names**: Use clear, consistent names. Prefer `fetch_usage_data` over `get_data`; avoid single-letter names except trivial loop indices. Constants and domain terms: match `const.py` and existing code.
- **No magic values**: Put numbers, strings, and URLs in `const.py` (or local named constants) and reference them. No raw timeouts, status codes, or API paths in the middle of logic.
- **Fail clearly**: Use exceptions from `exceptions.py`; raise with a clear message. Log at the right level (debug for flow, warning for recoverable, error/exception for failures). Do not swallow exceptions without logging.
- **Keep functions small**: If a function is long or nested deeply, extract steps into well-named helpers. The main flow should read like a short checklist.
- **Avoid duplication**: Same logic in multiple places → move to a shared helper (in the same module or `utils/`). Do not copy-paste blocks; refactor once and reuse.
- **Imports**: Group and order: standard library, then third-party, then `homeassistant`, then relative (`.const`, `.utils`, etc.). One import per line for clarity when the list is long.
- **Comments**: Prefer clear names and small functions over comments. When you do comment, explain *why* (invariants, API quirks, workarounds), not *what* the next line does.
- **Refactors**: When touching code, leave it cleaner than you found it: remove dead code, fix obvious style drift, update names that no longer match behavior. Do not mix refactors with new behavior in one PR unless necessary.

Apply these when writing or editing code in this integration.
