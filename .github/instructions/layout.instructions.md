---
applyTo: "custom_components/mijnted/**"
description: Integration module layout and the correct registration points for platforms, entities, and config changes.
---

# Project layout

```
custom_components/mijnted/
├── __init__.py          # Setup, coordinator, platform setup, cache load/save
├── api.py               # MijntedApi: cloud data endpoint calls
├── auth.py              # MijntedAuth: token refresh / credential rotation
├── config_flow.py       # Config flow UI and validation
├── const.py             # Domain, URLs, timeouts, platforms, all constants
├── exceptions.py        # MijntedApiError, MijntedAuthenticationError, etc.
├── manifest.json        # Metadata, version, requirements
├── sensor.py            # Sensor platform: creates sensor entities from coordinator
├── button.py            # Button platform
├── sensors/
│   ├── __init__.py      # Exports all sensor/button classes
│   ├── base.py          # MijnTedSensor base; statistics injection; device_info
│   ├── models.py        # StatisticsTracking, MonthCacheEntry, DeviceReading, etc.
│   ├── usage.py         # Usage sensors (monthly, total, average, last year)
│   ├── device.py        # Per-device/room sensors
│   ├── diagnostics.py   # Last update, active model, delivery types, etc.
│   └── button.py        # Reset statistics button
├── utils/               # Helpers, including OAuthUtil's synchronous credential flow
└── translations/
    └── en.json          # UI strings for config flow
```

**Where to change what:**

| Change | Files |
|--------|--------|
| New sensor | `sensors/usage.py`, `device.py`, or `diagnostics.py`; then `sensors/__init__.py` and the entity list in `sensor.py` (sensors) or `button.py` (buttons) |
| New data API call | `api.py`; shared URLs/constants in `const.py` |
| Credential login or token handling | `auth.py`, `utils/oauth_util.py`, `config_flow.py`; callbacks in `__init__.py` |
| Cache lifecycle or month calculations | `__init__.py`, `sensors/base.py`, `sensors/models.py`, `utils/date_util.py` |
| New constant | `const.py` |
| Config flow | `config_flow.py`, `translations/en.json` |
| Version | `manifest.json` |

Repository-level instructions and tooling are mapped in `AGENTS.md`; document
ownership is defined in `documentation.instructions.md`.
