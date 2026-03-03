---
applyTo: "custom_components/mijnted/**"
---

# Comments and docstrings

## Comments

Prefer clear names and small functions over comments. When you do comment, explain *why* (invariants, API quirks, workarounds), not *what* the next line does.

## Docstrings

Every method and class must have a docstring. The style differs by visibility:

### Public methods

Multi-line docstring with `Args:`, `Returns:`, and `Raises:` sections where applicable:

```python
def fetch_usage_data(self, month: int, year: int) -> UsageResult:
    """Fetch usage data for the given month from the API.

    Args:
        month: Calendar month (1-12).
        year: Four-digit year.

    Returns:
        UsageResult with device readings and totals.

    Raises:
        MijntedApiError: If the API call fails.
    """
```

### Private methods

Single-line docstring only — the name itself should convey the purpose:

```python
def _build_device_map(self, devices):
    """Map device IDs to their latest readings."""
```

### Classes

Multi-line docstring describing purpose, with an `Args:` section for constructor parameters or an `Attributes:` section for dataclass/NamedTuple fields:

```python
class MonthCacheEntry:
    """Cached usage data for a single calendar month.

    Attributes:
        month_id: Key in "YYYY-MM" format.
        year: Four-digit year.
        month: Calendar month (1-12).
        devices: List of device readings for the month.
        finalized: True when the month is complete and locked.
    """
```

### What NOT to do

- Do not omit docstrings entirely — every method must have at least a one-liner.
- Do not write multi-line docstrings for private methods; keep them to a single line.
- Do not repeat the function name in prose ("This function does ...").
