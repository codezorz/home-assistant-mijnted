# Home Assistant MijnTed Integration

This custom component integrates MijnTed devices with Home Assistant, allowing you to monitor your energy usage and other related data within your smart home setup.

## Features

- Authenticate with MijnTed API
- Retrieve energy usage data
- Get last data update timestamp
- Automatic data refresh

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

1. Your MijnTed username
2. Your MijnTed password
3. Your MijnTed client ID

To obtain the client ID:
1. Log in to the [MijnTed website](https://mijnted.nl)
2. Open your browser's developer console
3. Search for a request to `https://auth.mijnted.nl/authorize`
4. In the URL, find the `client_id` parameter
5. The value after `client_id=` is your client ID

For example, the client ID might look like: `AbCdEfGhIjKlMnOpQrStUvWxYz123456`

These credentials are used to authenticate with the MijnTed API. During the integration setup in Home Assistant, you'll be prompted to enter these details.

## Usage

Once configured, the integration will create several sensors in Home Assistant:

- Energy usage sensor
- Last data update sensor

You can use these sensors in your automations, scripts, and dashboards to monitor and analyze your energy consumption.

## API

The integration uses a custom `MijntedApi` class to interact with the MijnTed API. Key methods include:

- `authenticate()`: Logs in to the MijnTed API and retrieves an access token
- `get_energy_usage()`: Fetches the current energy usage data
- `get_last_data_update()`: Retrieves the timestamp of the last data update

## Troubleshooting

If you encounter issues:

1. Check that your MijnTed credentials are correct.
2. Ensure your internet connection is stable.
3. Verify that the MijnTed API is accessible.

For more detailed error messages, enable debug logging for the MijnTed component in your Home Assistant configuration.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

To set up a development environment:

1. Clone the repository
2. The integration can be tested directly in Home Assistant by copying the `custom_components/mijnted` folder to your Home Assistant's `custom_components` directory

For running unit tests (optional), you'll need to set up a Python environment with Home Assistant and pytest. Note that this requires Python 3.13.x and can be complex on Windows due to build tool requirements.

