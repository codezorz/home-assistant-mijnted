import aiohttp
import async_timeout
from datetime import datetime
from .const import BASE_URL, AUTH_URL

class MijntedApi:
    def __init__(self, username, password, client_id):
        self.username = username
        self.password = password
        self.client_id = client_id
        self.session = None
        self.access_token = None
        self.auth_url = AUTH_URL
        self.base_url = BASE_URL
        self.residential_unit = None
        self.delivery_type = None
        self.residential_units_claim = "https://ted-prod-function-app.azurewebsites.net/residential_units"

    async def authenticate(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

        data = {
            "client_id": self.client_id,
            "response_type": "code",
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
            "scope": "openid profile email"
        }

        async with async_timeout.timeout(10):
            async with self.session.post(self.auth_url, data=data) as response:
                if response.status == 200:
                    result = await response.json()
                    self.access_token = result["access_token"]
                    payload = result.get("__access_token_payload")
                    if payload:
                        self.residential_unit = payload.get(self.residential_units_claim, [None])[0]
                    else:
                        raise Exception("Access token payload missing")
                else:
                    raise Exception(f"Authentication failed: {response.status}")

        await self.get_delivery_types()

    async def get_delivery_types(self):
        url = f"{self.base_url}/address/deliveryTypes/{self.residential_unit}"
        async with async_timeout.timeout(10):
            async with self.session.get(url, headers=self._headers()) as response:
                if response.status == 200:
                    result = await response.json()
                    self.delivery_type = result[0]
                else:
                    raise Exception(f"Failed to get delivery types: {response.status}")

    async def get_energy_usage(self):
        current_year = datetime.now().year
        url = f"{self.base_url}/residentialUnitUsage/{current_year}/{self.residential_unit}/{self.delivery_type}"
        async with async_timeout.timeout(10):
            async with self.session.get(url, headers=self._headers()) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Failed to get energy usage: {response.status}")

    async def get_last_data_update(self):
        url = f"{self.base_url}/getLastSyncDate/{self.residential_unit}/{self.delivery_type}/{datetime.now().year}"
        async with async_timeout.timeout(10):
            async with self.session.get(url, headers=self._headers()) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Failed to get last data update: {response.status}")

    async def get_filter_status(self):
        url = f"{self.base_url}/deviceStatuses/{self.residential_unit}/{self.delivery_type}/{datetime.now().year}"
        async with async_timeout.timeout(10):
            async with self.session.get(url, headers=self._headers()) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Failed to get filter status: {response.status}")

    async def get_usage_insight(self):
        url = f"{self.base_url}/usageInsight/{datetime.now().year}/{self.residential_unit}/{self.delivery_type}"
        async with async_timeout.timeout(10):
            async with self.session.get(url, headers=self._headers()) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Failed to get usage insight: {response.status}")

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": "HomeAssistant/MijnTed"
        }

    async def close(self):
        if self.session:
            await self.session.close()
