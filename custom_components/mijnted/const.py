import logging
from homeassistant.const import Platform
from datetime import timedelta

DOMAIN = "mijnted"
BASE_URL = "https://ted-prod-function-app.azurewebsites.net/api"
AUTH_URL = "https://auth.mijnted.nl/oauth/token"
LOGGER = logging.getLogger(__package__)
PLATFORMS = [ Platform.SENSOR ]
DEFAULT_POLLING_INTERVAL = timedelta(hours=1)
UNIT_MIJNTED = "Units"
