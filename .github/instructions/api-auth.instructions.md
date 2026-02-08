---
applyTo: "custom_components/mijnted/api.py,custom_components/mijnted/auth.py,custom_components/mijnted/exceptions.py"
---

# API and auth

- **API**: All HTTP calls to MijnTed go through `api.py` (class `MijntedApi`). Add new endpoints as methods there. Keep URLs and timeouts in `const.py`, not in `api.py`.
- **Auth**: OAuth2 and token refresh live in `auth.py` (`MijnTedAuth`). The API uses the auth layer; do not store raw passwords in config entry data—only tokens and identifiers.
- **Errors**: Use exceptions from `exceptions.py` (e.g. `MijntedApiError`, `MijntedAuthenticationError`). Let the coordinator or config flow catch them and show user-friendly messages or retries.
- **Documentation**: When changing or adding API methods, check **ENDPOINTS.md** first (it documents all endpoints), then update it so URLs, parameters, and response shape stay accurate.
