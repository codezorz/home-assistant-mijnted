---
applyTo: "custom_components/mijnted/**"
description: Useful comments and concise production docstrings for public APIs, private helpers, and data models.
---

# Comments and docstrings

- Prefer clear names and small functions. Comments explain why: invariants,
  API quirks, or workarounds, rather than narrating the next line.
- Add docstrings to classes, functions, and methods you introduce or change.
  Do not expand an unrelated change solely to retrofit every existing docstring.
- Public APIs: start with a short purpose statement; add `Args:`, `Returns:`,
  and `Raises:` where the contract needs explanation. Omit inapplicable sections.
- Private helpers: usually one concise line; allow more detail when needed
  to explain complex invariants or an important return/error contract.
- Classes: describe responsibility. Document meaningful constructor parameters
  with `Args:` or model fields with `Attributes:`, without copying field lists
  that add no explanation.
- Keep examples consistent with actual model formats: `MonthCacheEntry.month_id`
  uses `M.YYYY`, while the containing monthly-cache dictionary uses `YYYY-MM` keys.
- Test documentation conventions live in `testing.instructions.md`.

```python
def _calculate_usage_from_start_end(start, end, month_id):
    """Calculate usage, treating January as the annual counter reset."""
```
