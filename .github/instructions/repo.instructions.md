---
applyTo: "**"
---

# Repository overview

This repo is the **Home Assistant MijnTed** custom integration: Python component that talks to the MijnTed cloud API and exposes energy usage and device data as sensors and buttons.

- **Domain**: `mijnted`. **Platforms**: sensor, button.
- **Integration code**: All under `custom_components/mijnted/`. Entry: `__init__.py`. Config: `config_flow.py`. API: `api.py`. Constants: `const.py`. Sensors: `sensors/`.
- **No separate build**: Runs inside Home Assistant. Dependencies in `custom_components/mijnted/manifest.json` (aiohttp, PyJWT, pkce, requests).
- **Validation**: Manual test in a real Home Assistant instance. Copy `custom_components/mijnted` into HA `custom_components`, restart or reload the integration, check sensors and behavior. Debug: `logger` / `custom_components.mijnted: debug` in `configuration.yaml`.
- **Version**: Bump `version` in `custom_components/mijnted/manifest.json` only for integration runtime/user-facing changes in `custom_components/mijnted/**` (not for `.github/**`, docs, or tooling-only updates). Bump only when needed: if `manifest.json` already has a version higher than the latest GitHub release, do not bump again; that PR can be part of the same upcoming unreleased version. Use semantic versioning when a bump is required.

**Docs**: README.md (install, config, sensors, troubleshooting). `doc/ENDPOINTS.md` (API reference), `doc/SENSORS.md` (sensor behavior), and `doc/MONTH_SWITCH.md` (month-switch behavior). More guidance in `.github/instructions/` for the integration code.
