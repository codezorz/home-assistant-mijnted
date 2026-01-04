from homeassistant.const import Platform
from datetime import timedelta

DOMAIN = "mijnted"
API_BASE_URL = "https://ted-prod-function-app.azurewebsites.net/api"
AUTH_URL = "https://mytedprod.b2clogin.com/mytedprod.onmicrosoft.com/b2c_1_user/oauth2/v2.0/token"
PLATFORMS = [Platform.SENSOR]
DEFAULT_POLLING_INTERVAL = timedelta(hours=1)
UNIT_MIJNTED = "Units"

# API constants
REQUEST_TIMEOUT = 10  # seconds
TOKEN_REFRESH_MAX_RETRIES = 3  # Maximum number of retry attempts for token refresh
TOKEN_REFRESH_RETRY_DELAY = 10  # Delay in seconds between token refresh retry attempts

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
MIN_POLLING_INTERVAL = 3600  # 1 hour in seconds
MAX_POLLING_INTERVAL = 86400  # 24 hours in seconds

# Refresh token expiration constants
REFRESH_TOKEN_PROACTIVE_REFRESH_THRESHOLD_SECONDS = 900  # 15 minutes in seconds - refresh when less time remains
REFRESH_TOKEN_DEFAULT_EXPIRATION_SECONDS = 86400  # 24 hours in seconds - default expiration when not provided

# Sensor calculation constants
CALCULATION_YEAR_MONTH_SORT_MULTIPLIER = 100  # Multiplier for creating sortable year-month keys (year * 100 + month)
CALCULATION_AVERAGE_PER_DAY_DECIMAL_PLACES = 2  # Number of decimal places for average_per_day calculations

# Cache constants
CACHE_HISTORY_MONTHS = 12  # Number of months to store in historical readings cache

# Sensor and calculation constants
MONTH_YEAR_PARTS_COUNT = 2  # Expected number of parts when parsing month.year format (e.g., "1.2025")
DEFAULT_START_VALUE = 0.0  # Default start value for device readings at year start
ENTITY_REGISTRATION_DELAY_SECONDS = 0.1  # Delay in seconds to ensure entity is fully registered before statistics injection

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
