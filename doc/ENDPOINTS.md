# MijnTed API Endpoints

This document provides an overview of all API endpoints used by the Home Assistant MijnTed integration.

## Base URLs

- **API Base URL**: `https://ted-prod-function-app.azurewebsites.net/api`
- **Authentication URL**: `https://mytedprod.b2clogin.com/mytedprod.onmicrosoft.com/b2c_1_user/oauth2/v2.0/token`

Data endpoint paths below include `/api` and are relative to the host. When
combining a path with `API_BASE_URL` (which already ends in `/api`), do not
add `/api` twice. Response examples illustrate shapes, not fixed account values.

## Authentication Lifecycle

Setup and Home Assistant reauthentication use the Azure B2C authorization-code
flow with PKCE, implemented by `OAuthUtil` and called by `MijntedAuth` through
HA's executor. This is a simulated browser login, not a password-grant request.

| Step | Endpoint / request |
|---|---|
| Initialize login | `GET` to `AUTH_AUTHORIZE_URL` with client ID, redirect URI, scope, nonce, response mode, and S256 PKCE challenge; extract CSRF/transaction values from HTML |
| Submit credentials | `POST` to `AUTH_LOGIN_URL` (`SelfAsserted`) with email/password and CSRF/transaction context |
| Confirm login | `GET` to `AUTH_CONFIRM_URL` (`api/CombinedSigninAndSignup/confirmed`) to obtain the authorization code |
| Exchange code | `POST` to the token URL with `grant_type=authorization_code`, client ID, scope, code, redirect URI, and PKCE verifier |

All auth endpoint constants are defined in `custom_components/mijnted/const.py`;
the redirect URI is `https://mijnted.nl/`.

The config entry retains client ID, username/password, access/refresh tokens,
refresh-token expiration, and residential-unit ID. The coordinator supplies
credentials for automatic reauthentication and persists rotated tokens through
its callback. Access-token refresh is attempted each polling cycle. When refresh
expiry is unknown or within the configured proactive threshold, or Azure B2C
returns `invalid_grant`, the auth layer attempts credential-based rotation.
If that rotation fails with an expired-grant error, the integration starts a
Home Assistant reauthentication flow.

## Client Method Mapping

| `MijntedApi` method | Data endpoint |
|---|---|
| `authenticate()` | Auth-layer refresh, then delivery types |
| `get_delivery_types()` | `address/deliveryTypes` (selects the first returned type for other requests) |
| `get_energy_usage(year=None)` | `residentialUnitUsage` |
| `get_last_data_update()` | `getLastSyncDate` |
| `get_filter_status()` | Latest `deviceStatuses` |
| `get_device_statuses_for_date(target_date)` | `deviceStatuses` with `fromDate` and target-date year |
| `get_usage_insight(year=None)` | `usageInsight` |
| `get_active_model()` | `activeModel` |
| `get_residential_unit_detail()` | `residentialUnitDetailItem` |
| `get_usage_per_room(year=None)` | `residentialUnitUsagePerRoom` |
| `get_unit_of_measures()` | `unitOfMeasures` |

Optional-year methods default to the current calendar year. Latest-status,
last-sync, and unit-of-measure requests also use that year. Historical device
requests catch errors, log a warning, and return an empty list.

## Authentication Endpoints

### Token Refresh
**Endpoint**: `POST https://mytedprod.b2clogin.com/mytedprod.onmicrosoft.com/b2c_1_user/oauth2/v2.0/token`

**Description**: Refreshes the access token using a refresh token (OAuth2 refresh token flow).

**Request Body** (application/x-www-form-urlencoded):
- `client_id`: The Azure AD B2C client ID
- `grant_type`: `refresh_token`
- `refresh_token`: The refresh token
- `scope`: `{client_id} openid profile offline_access`

**Response**:
```json
{
  "access_token": "...",
  "id_token": "...",
  "refresh_token": "...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token_expires_in": 86252
}
```

**Notes**:
- The `id_token` contains the residential unit ID in the `extension_ResidentialUnits` claim
- A new refresh token may be provided and should be stored for future use

---

## Data Endpoints

All data endpoints require authentication via Bearer token in the `Authorization` header.

**Headers**:
- `Authorization: Bearer {access_token}`
- `User-Agent: HomeAssistant/MijnTed`

### Get Delivery Types
**Endpoint**: `GET /api/address/deliveryTypes/{residential_unit}`

**Description**: Retrieves the available delivery types for a residential unit.

**Parameters**:
- `residential_unit` (path): The residential unit ID (e.g., "123456")

**Response**: Array of delivery type IDs
```json
[1, 2]
```

**Example**: `GET /api/address/deliveryTypes/123456`

---

### Get Energy Usage
**Endpoint**: `GET /api/residentialUnitUsage/{year}/{residential_unit}/{delivery_type}`

**Description**: Retrieves energy usage data for a specific year.

**Parameters**:
- `year` (path): The year (e.g., 2025)
- `residential_unit` (path): The residential unit ID
- `delivery_type` (path): The delivery type ID (e.g., 1)

**Response**: JSON object with energy usage data
```json
{
  "monthlyEnergyUsages": [
    {
      "totalEnergyUsage": 260.00,
      "monthYear": "1.2025",
      "unitOfMeasurement": "Eenheden",
      "averageEnergyUseForBillingUnit": 866.34
    },
    {
      "totalEnergyUsage": 267.00,
      "monthYear": "2.2025",
      "unitOfMeasurement": "Eenheden",
      "averageEnergyUseForBillingUnit": 697.39
    },
    {
      "totalEnergyUsage": 0.0,
      "monthYear": "12.2025",
      "unitOfMeasurement": "Eenheden",
      "averageEnergyUseForBillingUnit": null
    }
  ],
  "averageEnergyUseForBillingUnit": 0
}
```

**Examples**:
- `GET /api/residentialUnitUsage/2025/123456/1`
- `GET /api/residentialUnitUsage/2024/123456/1`

**Notes**:
- The `monthlyEnergyUsages` array contains monthly data for the specified year
- Total usage can be calculated by summing `totalEnergyUsage` values from all months

---

### Get Last Data Update
**Endpoint**: `GET /api/getLastSyncDate/{residential_unit}/{delivery_type}/{year}`

**Description**: Retrieves the last synchronization date for the data.

**Parameters**:
- `residential_unit` (path): The residential unit ID
- `delivery_type` (path): The delivery type ID
- `year` (path): The year

**Response**: Plain text date string
```
"18/12/2025"
```

**Content-Type**: `text/plain; charset=utf-8`

**Example**: `GET /api/getLastSyncDate/123456/1/2025`

---

### Get Filter Status
**Endpoint**: `GET /api/deviceStatuses/{residential_unit}/{delivery_type}/{year}`

**Description**: Retrieves the filter status information for devices.

**Parameters**:
- `residential_unit` (path): The residential unit ID
- `delivery_type` (path): The delivery type ID
- `year` (path): The year
- `fromDate` (query, optional): Date in format `YYYY-MM-DD` (e.g., `2026-01-03`). When provided, returns device readings for the specified date or older. The date must be equal to or older than the last update date. If not provided, returns the latest device statuses.

**Response**: JSON array of device status objects
```json
[
  {
    "measurementDeviceId": 123456,
    "room": "KA",
    "deviceId": 123456,
    "deviceNumber": "12345678",
    "currentReadingValue": 145.0000,
    "unitOfMeasure": "Einheiten",
    "deactivationDate": "",
    "radiographicMeter": true
  },
  {
    "measurementDeviceId": 789012,
    "room": "W",
    "deviceId": 789012,
    "deviceNumber": "87654321",
    "currentReadingValue": 785.0000,
    "unitOfMeasure": "Einheiten",
    "deactivationDate": "",
    "radiographicMeter": true
  }
]
```

**Examples**:
- `GET /api/deviceStatuses/123456/1/2025` - Get latest device statuses
- `GET /api/deviceStatuses/123456/1/2026?fromDate=2026-01-03` - Get device readings for a specific date

**Notes**:
- The `fromDate` parameter allows retrieving historical device readings for a specific date
- The date must be equal to or older than the last update date (`lastSyncDate`)
- When `fromDate` is not provided, the endpoint returns the most recent device statuses

---

### Get Usage Insight
**Endpoint**: `GET /api/usageInsight/{year}/{residential_unit}/{delivery_type}`

**Description**: Retrieves usage insights and analytics.

**Parameters**:
- `year` (path): The year
- `residential_unit` (path): The residential unit ID
- `delivery_type` (path): The delivery type ID

**Response**: JSON object with usage insights
```json
{
  "unitType": "Eenheden",
  "usage": 762.00,
  "billingUnitAverageUsage": 2697.18,
  "usageDifference": -1935.18,
  "deviceModel": "F71"
}
```

**Example**: `GET /api/usageInsight/2025/123456/1`

---

### Get Active Model
**Endpoint**: `GET /api/activeModel/{residential_unit}/{delivery_type}`

**Description**: Retrieves information about the active model/device.

**Parameters**:
- `residential_unit` (path): The residential unit ID
- `delivery_type` (path): The delivery type ID

**Response**: Plain text string
```
"F71"
```

**Content-Type**: `text/plain; charset=utf-8`

**Example**: `GET /api/activeModel/123456/1`

---

### Get Residential Unit Detail
**Endpoint**: `GET /api/residentialUnitDetailItem/{residential_unit}`

**Description**: Retrieves detailed information about the residential unit.

**Parameters**:
- `residential_unit` (path): The residential unit ID

**Response**: JSON object with residential unit details
```json
{
  "id": 123456,
  "billingUnitId": 7890,
  "appartmentNo": "12",
  "street": "Example Street",
  "zipCode": "1234AB",
  "residentName": "",
  "hasRegistration": true,
  "registrationId": 5678,
  "registrationComplete": true,
  "isMeterValuesExportActive": true
}
```

**Example**: `GET /api/residentialUnitDetailItem/123456`

**Notes**:
- The `street`, `appartmentNo`, and `zipCode` fields can be used to construct a human-readable address
- The address format is typically: `{street} {appartmentNo}, {zipCode}`

---

### Get Usage Per Room
**Endpoint**: `GET /api/residentialUnitUsagePerRoom/{year}/{residential_unit}/{delivery_type}`

**Description**: Retrieves energy usage data broken down by room.

**Parameters**:
- `year` (path): The year
- `residential_unit` (path): The residential unit ID
- `delivery_type` (path): The delivery type ID

**Response**: JSON object with room usage data
```json
{
  "rooms": ["KA", "W"],
  "units": "Eenheden",
  "lastYear": {
    "year": 2024,
    "values": [0.0000, 1178.0000]
  },
  "currentYear": {
    "year": 2025,
    "values": [129.0000, 633.0000]
  },
  "nextYear": {
    "year": 2026,
    "values": [0.0, 0.0]
  }
}
```

**Notes**:
- The `rooms` array contains room names (may have duplicates)
- The `values` arrays correspond to rooms by index
- Values are summed for rooms with duplicate names

**Example**: `GET /api/residentialUnitUsagePerRoom/2025/123456/1`

---

### Get Unit of Measures
**Endpoint**: `GET /api/unitOfMeasures/{residential_unit}/{delivery_type}/{year}`

**Description**: Retrieves the unit of measurement information for a residential unit.

**Parameters**:
- `residential_unit` (path): The residential unit ID
- `delivery_type` (path): The delivery type ID
- `year` (path): The year

**Response**: JSON array with unit of measure objects
```json
[
  {
    "value": "eenheid",
    "displayName": "Eenheden"
  }
]
```

**Example**: `GET /api/unitOfMeasures/123456/1/2025`

**Notes**:
- Returns an array of unit of measure objects
- Each object contains a `value` (internal identifier) and `displayName` (human-readable name)
- Typically returns a single item in the array

---

## Error Handling

All endpoints may return:
- **401 Unauthorized**: The API refreshes the token and retries the data request once. A second 401 raises an authentication error; other failed retry statuses raise an API error.
- **200 OK**: Success - response format varies (JSON or plain text)
- **Other status codes**: Error response with error message

Async data requests use `REQUEST_TIMEOUT`. Auth refresh retries client/network
errors using `RetryUtil` backoff; that is separate from the one data-request
retry after a 401. Most concurrently fetched endpoint errors become empty
defaults in the coordinator, so a partial refresh can still return successfully.
See [sensor availability/fallbacks](SENSORS.md#edge-cases-and-expected-behavior).

## Response Formats

The API returns data in two formats:
1. **JSON** (`Content-Type: application/json`): Most endpoints return JSON
2. **Plain Text** (`Content-Type: text/plain; charset=utf-8`): Some endpoints like `getLastSyncDate` return plain text

The client first parses JSON according to content type. For other content types
it attempts JSON decoding of the response text (including quoted strings);
unparseable text becomes `{"value": "..."}`. Coordinator normalization extracts
text values where required. Do not assume every plain-text response is a dict.
