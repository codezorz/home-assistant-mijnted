---
applyTo: "custom_components/mijnted/**,icon.svg,icon.png"
description: Integration module layout, entity registration points, and brand artwork maintenance.
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
├── reconciliation.py    # Published monthly totals and pending boundary repair
├── manifest.json        # Metadata, version, requirements
├── sensor.py            # Sensor platform: creates sensor entities from coordinator
├── button.py            # Button platform
├── sensors/
│   ├── __init__.py      # Exports all sensor/button classes
│   ├── base.py          # MijnTedSensor base; statistics injection; device_info
│   ├── models.py        # StatisticsTracking, MonthCacheEntry, DeviceReading, etc.
│   ├── usage.py         # Usage sensors (monthly, total, average, last year)
│   ├── device.py        # Per-device/room sensors
│   ├── water.py         # Water (m³) meter and monthly usage sensors for extra delivery types
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
| Cache lifecycle or month calculations | `__init__.py`, `reconciliation.py`, `sensors/base.py`, `sensors/models.py`, `utils/date_util.py` |
| New constant | `const.py` |
| Config flow | `config_flow.py`, `translations/en.json` |
| Version | `manifest.json` |

Repository-level instructions and tooling are mapped in `AGENTS.md`; document
ownership is defined in `documentation.instructions.md`.

## Brand artwork

The root [`icon.svg`](../../icon.svg) is a scalable trace of the original 128 x 128
favicon from <https://mijnted.nl/favicon@128.png>. It preserves the red
house/heart artwork and transparent background, with smoothed outer heart and
hand curves on the right edge to remove favicon clipping artifacts. Export the
SVG when updating the PNG images: root [`icon.png`](../../icon.png) and
`custom_components/mijnted/brand/icon.png` at 256 x 256, and the integration's
`icon@2x.png` at 512 x 512. Home Assistant uses the integration's PNG exports,
not the SVG.

For example, with Inkscape installed, run from the checkout root:

```sh
inkscape icon.svg --export-width=256 --export-height=256 --export-filename=icon.png
inkscape icon.svg --export-width=256 --export-height=256 --export-filename=custom_components/mijnted/brand/icon.png
inkscape icon.svg --export-width=512 --export-height=512 --export-filename=custom_components/mijnted/brand/icon@2x.png
```
