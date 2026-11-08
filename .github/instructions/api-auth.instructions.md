---
applyTo: "custom_components/mijnted/api.py,custom_components/mijnted/auth.py,custom_components/mijnted/config_flow.py,custom_components/mijnted/exceptions.py,custom_components/mijnted/utils/oauth_util.py"
description: HTTP client boundaries, credential authentication, token rotation, and API documentation.
---

# API and auth

- **API**: Data endpoint calls go through `api.py` (`MijntedApi`). Add new data methods there; keep shared base URLs and timeouts in `const.py` and endpoint construction in the API layer.
- **Auth**: Token refresh lives in `auth.py` (`MijntedAuth`). Credential login uses the authorization-code/PKCE flow in `utils/oauth_util.py`; its synchronous `requests` calls run through `hass.async_add_executor_job`, never directly on the event loop.
- **Persistence**: Config entry data stores username/password, client ID, tokens,
  expiration, and residential-unit ID. The credentials callback uses stored
  credentials for rotation; preserve this storage/rotation contract in auth changes.
- **Token lifecycle**: Authentication refreshes the access token each polling cycle. Expiring/invalid refresh grants trigger credential-based rotation; token updates are persisted through the callback. Keep the one-retry-on-401 behavior in the API layer separate from auth backoff.
- **Errors**: Use exceptions from `exceptions.py` (e.g. `MijntedApiError`, `MijntedAuthenticationError`). Let the coordinator or config flow catch them and show user-friendly messages or retries.
- **UI text**: Follow [translation instructions](translations.instructions.md) for configuration/reauthentication text and user-visible HA errors.
- **Documentation**: Follow `.github/instructions/documentation.instructions.md`; `docs/ENDPOINTS.md` owns endpoint and authentication behavior.
