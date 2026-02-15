---
applyTo: "custom_components/mijnted/**,README.md,ENDPOINTS.md"
---

# Keep documentation in sync

When you change behavior that users or developers rely on, update the docs in the same change.

- **API methods** (`api.py`, endpoints, request/response shape): Check and update **ENDPOINTS.md**. It is the reference for all MijnTed API calls used by the integration. Add new endpoints, fix URLs or parameters, document response structure.
- **Sensors** (new sensor, renamed entity, changed attributes, state class, or meaning): Check and update **README.md**. The "Usage" section lists sensors and their meaning (e.g. monthly usage, total usage, last update). Add new sensors there; fix descriptions if behavior or attributes change. When changing sensor behavior patterns (e.g. how sensors handle missing or unavailable data), also update **.github/instructions/sensors.instructions.md**.
- **Config flow** (new options, changed steps, new strings): Ensure **translations/en.json** has the keys and that README reflects any new or changed configuration.
- **Version or requirements**: Bump `manifest.json` version for user-facing or behavior changes; README or release notes if you maintain them.

Before finishing a change to API or sensors, open the relevant doc and update it.
