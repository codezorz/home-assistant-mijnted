# Home Assistant MijnTed Integration

This custom component integrates MijnTed devices with Home Assistant, allowing you to monitor your energy usage and other related data within your smart home setup.

## Installation

1. Copy the `custom_components/mijnted` folder to your Home Assistant's `custom_components` directory.
2. Restart Home Assistant.
3. Go to Configuration > Integrations.
4. Click the "+ ADD INTEGRATION" button and search for "MijnTed".
5. Follow the configuration steps.

## Installation via HACS

1. Ensure that [HACS](https://hacs.xyz/) is installed.
2. In Home Assistant, go to HACS > Integrations.
3. Click on the three dots in the top right corner and select "Custom repositories".
4. Enter the following information:
   - URL: `https://github.com/codezorz/home-assistant-mijnted`
   - Category: Integration
5. Click "Add".
6. Search for "MijnTed" in HACS and install it.
7. Restart Home Assistant.
8. Go to Configuration > Integrations.
9. Click the "+ ADD INTEGRATION" button and search for "MijnTed".
10. Follow the configuration steps.

## Configuration

To set up the MijnTed integration, you'll need:

1. Your MijnTed client ID
2. Your MijnTed refresh token

### Obtaining Your Credentials

Both the **Client ID** and **Refresh Token** can be extracted from the same request:

1. Log in to the [MijnTed website](https://mijnted.nl)
2. Open your browser's developer console (F12)
3. Go to the Network tab
4. Look for a POST request to `https://mytedprod.b2clogin.com/mytedprod.onmicrosoft.com/b2c_1_user/oauth2/v2.0/token`
5. Click on the request and go to the "Payload" or "Request" tab (depending on your browser)
6. In the form parameters, you'll find:
   - **Client ID**: The value of the `client_id` parameter (typically a UUID format)
   - **Refresh Token**: The value of the `refresh_token` parameter

The request will look something like this:
```
POST https://mytedprod.b2clogin.com/mytedprod.onmicrosoft.com/b2c_1_user/oauth2/v2.0/token

Form Data:
- client_id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
- refresh_token: ...
- grant_type: refresh_token
- scope: openid offline_access ...
```

**Note:** The client ID is typically a UUID format (e.g., `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`). The refresh token is a longer string that may change when you log in again.

**Polling Interval (Optional):**
- Default: 3600 seconds (1 hour)
- Range: 900-86400 seconds (15 minutes to 24 hours)
- You can configure this during setup or leave it at the default

These credentials are used to authenticate with the MijnTed API. During the integration setup in Home Assistant, you'll be prompted to enter these details.

## Usage

Once configured, the integration will create several sensors in Home Assistant:

- **This Month Usage** - Current month's energy usage (calculated from total minus measured months)
- **Latest Month Usage** - Actual usage for the latest available month
- **Latest Month Last Year Usage** - Last year's usage for the latest available month (computed comparison)
- **Latest Month Average Usage** - Average usage for the latest available month
- **Latest Month Last Year Average Usage** - Last year's average usage for the latest available month (computed comparison)
- **Last Update** - Timestamp of the last data synchronization from the API
- **Last Successful Sync** - Timestamp of the last successful data synchronization from the API
- **Total Usage** - Sum of all device readings (cumulative filter status)
- **Active Model** - The active model identifier (e.g., "F71")
- **Delivery Type** - Available delivery types for your residential unit
- **Residential Unit** - Detailed information about your residential unit
- **Unit of Measures** - Unit of measurement information
- **This Year Usage** - Total energy usage for the current year (with monthly breakdown in attributes)
- **Last Year Usage** - Total energy usage for the previous year (with monthly breakdown in attributes)
- **Device Sensors** - Individual sensors for each device/room (dynamically created based on your setup, named by room when available)

All usage sensors display values with zero decimal places for a cleaner interface.

You can use these sensors in your automations, scripts, and dashboards to monitor and analyze your energy consumption. The sensors include additional attributes with detailed information that can be accessed in templates and automations.

## API

The integration uses a custom `MijntedApi` class to interact with the MijnTed API. Key methods include:

- `authenticate()`: Authenticates with the MijnTed API using refresh token and retrieves/refreshes access token
- `refresh_access_token()`: Refreshes the access token using the refresh token
- `get_energy_usage()`: Fetches the current year's energy usage data
- `get_last_data_update()`: Retrieves the timestamp of the last data update
- `get_filter_status()`: Gets filter status and device readings
- `get_usage_insight()`: Retrieves usage insights
- `get_active_model()`: Gets the active model information
- `get_delivery_types()`: Retrieves available delivery types for the residential unit
- `get_residential_unit_detail()`: Gets detailed residential unit information
- `get_usage_last_year()`: Fetches last year's energy usage data
- `get_usage_per_room()`: Gets usage data per room for the current year
- `get_unit_of_measures()`: Gets unit of measurement information

## Troubleshooting

If you encounter issues:

1. Check that your MijnTed client ID and refresh token are correct.
2. Ensure your internet connection is stable.
3. Verify that the MijnTed API is accessible.
4. If authentication fails, your refresh token may have expired. You'll need to obtain a new refresh token.
5. Check the polling interval setting - if set too low, it may cause rate limiting issues.

For more detailed error messages, enable debug logging for the MijnTed component in your Home Assistant configuration by adding the following to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.mijnted: debug
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

To set up a development environment:

1. Clone the repository
2. The integration can be tested directly in Home Assistant by copying the `custom_components/mijnted` folder to your Home Assistant's `custom_components` directory
3. Restart Home Assistant to load the custom component

The integration uses the following dependencies:
- `aiohttp` - For async HTTP requests
- `PyJWT` - For JWT token decoding

