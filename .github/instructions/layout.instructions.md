---
applyTo: "custom_components/mijnted/**"
---

# Project layout

```
custom_components/mijnted/
├── __init__.py          # Setup, coordinator, platform setup, cache load/save
├── api.py               # MijntedApi: all HTTP calls to MijnTed API
├── auth.py              # MijnTedAuth: OAuth2 / token refresh (Azure B2C)
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
├── utils/               # Helpers (api_util, data_util, date_util, jwt_util, etc.)
└── translations/
    └── en.json          # UI strings for config flow
```

**Where to change what:**

| Change | Files |
|--------|--------|
| New sensor | `sensors/usage.py`, `device.py`, or `diagnostics.py`; then `sensors/__init__.py` and the entity list in `__init__.py` / `sensor.py` |
| New API call | `api.py`; URLs/constants in `const.py` |
| New constant | `const.py` |
| Config flow | `config_flow.py`, `translations/en.json` |
| Version | `manifest.json` |
