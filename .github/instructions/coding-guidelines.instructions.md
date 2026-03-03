---
applyTo: "custom_components/mijnted/**"
---

# Coding guidelines

- **One responsibility**: Each function or class should do one thing. Split long functions; extract helpers into `utils/` when reusable and pure.
- **Names**: Use clear, consistent names. Prefer `fetch_usage_data` over `get_data`; avoid single-letter names except trivial loop indices. Constants and domain terms: match `const.py` and existing code.
- **Keep functions small**: If a function is long or nested deeply, extract steps into well-named helpers. The main flow should read like a short checklist.
- **Avoid duplication**: Same logic in multiple places → move to a shared helper (in the same module or `utils/`). Do not copy-paste blocks; refactor once and reuse.
- **Refactors**: When touching code, leave it cleaner than you found it: remove dead code, fix obvious style drift, update names that no longer match behavior. Do not mix refactors with new behavior in one PR unless necessary.

Apply these when writing or editing code in this integration.
