from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "mijnted"
API_BASE_URL = "https://ted-prod-function-app.azurewebsites.net/api"
AUTH_URL = "https://mytedprod.b2clogin.com/mytedprod.onmicrosoft.com/b2c_1_user/oauth2/v2.0/token"
PLATFORMS = [Platform.SENSOR, Platform.BUTTON]
DEFAULT_POLLING_INTERVAL = timedelta(hours=1)
UNIT_MIJNTED = "Units"

# API constants
REQUEST_TIMEOUT = 10
TOKEN_REFRESH_MAX_RETRIES = 3
TOKEN_REFRESH_RETRY_DELAY = 10

# ID token claim constants
ID_TOKEN_CLAIM_RESIDENTIAL_UNITS = "extension_ResidentialUnits"
ID_TOKEN_CLAIM_OCCUPANT_ID = "extension_OccupantID"
ID_TOKEN_CLAIM_BILLING_UNITS = "extension_BillingUnits"
ID_TOKEN_CLAIM_USER_ROLE = "extension_UserRole"

# HTTP status codes
HTTP_STATUS_OK = 200
HTTP_STATUS_BAD_REQUEST = 400
HTTP_STATUS_UNAUTHORIZED = 401

# Polling interval constants
MIN_POLLING_INTERVAL = 3600
MAX_POLLING_INTERVAL = 86400

# Refresh token expiration constants
REFRESH_TOKEN_PROACTIVE_REFRESH_THRESHOLD_SECONDS = 900
REFRESH_TOKEN_DEFAULT_EXPIRATION_SECONDS = 86400

# Sensor calculation constants
CALCULATION_YEAR_MONTH_SORT_MULTIPLIER = 100
CALCULATION_AVERAGE_PER_DAY_DECIMAL_PLACES = 2

# Cache constants
CACHE_HISTORY_MONTHS = 16
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}_monthly_cache"

# Sensor and calculation constants
MONTH_YEAR_PARTS_COUNT = 2
DEFAULT_START_VALUE = 0.0

# Date format for API requests and storage
API_DATE_FORMAT = "%Y-%m-%d"
API_LAST_SYNC_DATE_FORMAT = "%d/%m/%Y"
DISPLAY_MONTH_YEAR_FORMAT = "%B %Y"
TIMESTAMP_FORMAT_ISO = "%Y-%m-%dT%H:%M:%S"
TIMESTAMP_FORMAT_ISO_Z = "%Y-%m-%dT%H:%M:%SZ"

# Config flow schema keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_POLLING_INTERVAL = "polling_interval"

# Azure B2C authentication constants
AUTH_TENANT_NAME = "mytedprod"
AUTH_TENANT_ID = "mytedprod.onmicrosoft.com"
AUTH_POLICY = "B2C_1_user"
AUTH_BASE_URL = f"https://{AUTH_TENANT_NAME}.b2clogin.com/{AUTH_TENANT_ID}/{AUTH_POLICY}"
AUTH_AUTHORIZE_URL = f"{AUTH_BASE_URL}/oauth2/v2.0/authorize"
AUTH_TOKEN_URL = f"{AUTH_BASE_URL}/oauth2/v2.0/token"
AUTH_LOGIN_URL = f"{AUTH_BASE_URL}/SelfAsserted"
AUTH_CONFIRM_URL = f"{AUTH_BASE_URL}/api/CombinedSigninAndSignup/confirmed"
AUTH_REDIRECT_URI = "https://mijnted.nl/"
AUTH_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# OAuth 2.0 constants
OAUTH_SCOPE = "openid profile offline_access"
OAUTH_GRANT_TYPE_AUTHORIZATION_CODE = "authorization_code"
OAUTH_GRANT_TYPE_REFRESH_TOKEN = "refresh_token"
OAUTH_RESPONSE_TYPE_CODE = "code"
OAUTH_CODE_CHALLENGE_METHOD = "S256"
OAUTH_RESPONSE_MODE = "query"
OAUTH_ERROR_INVALID_GRANT = "invalid_grant"
OAUTH_REQUEST_TYPE_RESPONSE = "RESPONSE"
OAUTH_REMEMBER_ME_FALSE = "false"

# HTTP headers and content types
CONTENT_TYPE_JSON = "application/json"
CONTENT_TYPE_FORM_URLENCODED = "application/x-www-form-urlencoded; charset=UTF-8"
HEADER_X_REQUESTED_WITH = "XMLHttpRequest"
AUTHORIZATION_SCHEME_BEARER = "Bearer"
USER_AGENT = "HomeAssistant/MijnTed"
