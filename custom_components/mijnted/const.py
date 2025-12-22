import logging
from homeassistant.const import Platform
from datetime import timedelta

DOMAIN = "mijnted"
BASE_URL = "https://ted-prod-function-app.azurewebsites.net/api"
AUTH_URL = "https://mytedprod.b2clogin.com/mytedprod.onmicrosoft.com/b2c_1_user/oauth2/v2.0/token"
LOGGER = logging.getLogger(__package__)
PLATFORMS = [Platform.SENSOR]
DEFAULT_POLLING_INTERVAL = timedelta(hours=1)
UNIT_MIJNTED = "Units"

# API constants
REQUEST_TIMEOUT = 10  # seconds
TOKEN_REFRESH_MAX_RETRIES = 3  # Maximum number of retry attempts for token refresh
TOKEN_REFRESH_RETRY_DELAY = 10  # Delay in seconds between token refresh retry attempts
RESIDENTIAL_UNITS_CLAIM = "https://ted-prod-function-app.azurewebsites.net/residential_units"
RESIDENTIAL_UNITS_CLAIM_ALT = "extension_ResidentialUnits"
USER_AGENT = "HomeAssistant/MijnTed"

# HTTP status codes
HTTP_STATUS_OK = 200
HTTP_STATUS_UNAUTHORIZED = 401

# Polling interval constants
MIN_POLLING_INTERVAL = 900  # 15 minutes in seconds
MAX_POLLING_INTERVAL = 86400  # 24 hours in seconds

# Refresh token expiration constants
REFRESH_TOKEN_PROACTIVE_REFRESH_THRESHOLD_SECONDS = 43200  # 12 hours in seconds - refresh when less time remains

# Sensor calculation constants
YEAR_TRANSITION_MULTIPLIER = 2.0  # Multiplier for detecting year transition issues
YEAR_MONTH_SORT_MULTIPLIER = 100  # Multiplier for creating sortable year-month keys (year * 100 + month)
