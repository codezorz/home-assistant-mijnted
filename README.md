# Home Assistant MijnTed Integration

This custom component integrates MijnTed devices with Home Assistant, allowing you to monitor your energy usage and other related data within your smart home setup.

## Documentation

This README covers installation, configuration, and everyday usage. Detailed
references live in [`doc/`](doc/):

| Guide | What it covers |
|---|---|
| [Sensors and buttons](doc/SENSORS.md) | Values, attributes, missing-data behavior, statistics, and the reset button |
| [Month transitions](doc/MONTH_SWITCH.md) | API lag, month lifecycle, baseline locking, and late corrections |
| [API and authentication](doc/ENDPOINTS.md) | Endpoints, client methods, response formats, and token rotation |
| [Reporting issues](doc/ISSUE_REPORTING.md) | Diagnostic information and a bug-report template |
| [Development](doc/DEVELOPMENT.md) | Environment setup, tests, Home Assistant verification, and agent tooling |

## Installation

1. Copy the `custom_components/mijnted` folder to your Home Assistant's `custom_components` directory.
2. Restart Home Assistant.
3. Go to Settings > Devices & services > Integrations.
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
8. Go to Settings > Devices & services > Integrations.
9. Click the "+ ADD INTEGRATION" button and search for "MijnTed".
10. Follow the configuration steps.

## Configuration

To set up the MijnTed integration, you'll need:

1. Your MijnTed client ID
2. Your MijnTed username (email address)
3. Your MijnTed password

### Obtaining Your Client ID

The **Client ID** can be extracted from a browser network request:

1. Log in to the [MijnTed website](https://mijnted.nl)
2. Open your browser's developer console (F12)
3. Go to the Network tab
4. Look for a POST request to `https://mytedprod.b2clogin.com/mytedprod.onmicrosoft.com/b2c_1_user/oauth2/v2.0/token`
5. Click on the request and go to the "Payload" or "Request" tab (depending on your browser)
6. In the form parameters, you'll find:
   - **Client ID**: The value of the `client_id` parameter (typically a UUID format)

The request will look something like this:
```
POST https://mytedprod.b2clogin.com/mytedprod.onmicrosoft.com/b2c_1_user/oauth2/v2.0/token

Form Data:
- client_id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
- refresh_token: ...
- grant_type: refresh_token
- scope: openid offline_access ...
```

**Note:** The client ID is typically a UUID format (e.g., `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`).

**Polling Interval (Optional):**
- Default: 3600 seconds (1 hour)
- Range: 3600-86400 seconds (1 hour to 24 hours)
- You can configure this during setup or leave it at the default
- To change it later, open the integration's options/configure dialog in Settings > Devices & services. Saving the interval reloads the integration.

During setup, enter your client ID, username, and password. The integration handles OAuth 2.0 and retains credentials and tokens in the Home Assistant config entry for automatic reauthentication. See the [authentication reference](doc/ENDPOINTS.md#authentication-lifecycle) for details.

## Usage

Once configured, the integration will create several sensors in Home Assistant:

Detailed references: [sensor catalog](doc/SENSORS.md), [month-switch timeline](doc/MONTH_SWITCH.md), and [API/authentication](doc/ENDPOINTS.md).

- **Monthly usage** - Current calendar month's energy usage, calculated from start/end readings with annual-reset handling in January. Attributes include `start_date`, `end_date`, `days`, and `month_id`. Use the **Last update** sensor to see the date through which API readings are available.
- **Last year monthly usage** - Last year's monthly usage for the corresponding month (prefers API-provided value from previous year's data)
- **Average monthly usage** - Average usage extracted from historical monthly usage data
- **Last year average monthly usage** - Last year's average monthly usage for the corresponding month (prefers API-provided value from previous year's data)
- **Total usage** - Sum of all device readings (cumulative filter status, accumulating counter). Attributes expose aligned month payloads for `current` and `history`, including month `status` (`OPEN`, `COMPLETE_READINGS`, `FINALIZED`). Automatically injects historical data for proper history graphs.
- **Last update** - Date for which device readings are currently available from the API (often 1-2 days behind)
- **Last successful sync** - Timestamp of the most recent returned refresh payload; some individual endpoints can have failed during that refresh
- **Active model** - The active model identifier (e.g., "F71")
- **Delivery type** - Available delivery types for your residential unit
- **Residential unit** - Detailed information about your residential unit
- **Unit of measures** - Unit of measurement information
- **Latest available insight** - Month with the last available insight data including average. Displays the month name only (e.g. "January 2026"). Attributes include month_id, usage_unit, has_average.
- **Device Sensors** - Individual sensors for each device/room (dynamically created based on your setup, named by room when available)
- **Reset statistics** - Button to reset statistics tracking and trigger re-injection of historical data. See [reset behavior](doc/SENSORS.md#related-button) for what it clears.

Usage sensors request zero decimal places for display; underlying values retain their precision.

### History and Statistics

With recorder enabled, usage sensors import historical long-term statistics.
This does not backfill ordinary sensor state history. Total usage uses
`TOTAL_INCREASING`; other usage sensors use `TOTAL`. Average statistics are
state-only: use the Statistics state view for the two average entities.

Late month corrections can trigger reinjection. The reset button rebuilds the
integration cache and injection tracking; it does not delete recorder data.
See [statistics behavior](doc/SENSORS.md#statistics-injection-behavior) for the
full contract and [month-switch behavior](doc/MONTH_SWITCH.md) for boundary cases.

You can use these sensors in your automations, scripts, and dashboards to monitor and analyze your energy consumption. The sensors include additional attributes with detailed information that can be accessed in templates and automations.

## API

`MijntedApi` handles data endpoints and `MijntedAuth` manages tokens and
credential-based rotation. The [endpoint reference](doc/ENDPOINTS.md) owns the
method mapping, request/response examples, and retry details.

## Troubleshooting

If you encounter issues:

1. Check that your MijnTed client ID and login credentials are correct and that you can log in on the MijnTed website.
2. Ensure your internet connection is stable.
3. Verify that the MijnTed API is accessible.
4. Refresh-token rotation is automatic. If it fails and Home Assistant requests reauthentication, complete that flow with your client ID, username, and password; you do not need to paste a refresh token manually.
5. If readings look stale, compare **Last update** with **Last successful sync**. MijnTed readings often lag the calendar date; a recent sync can also contain partial endpoint failures. Check logs and the [sensor edge cases](doc/SENSORS.md#edge-cases-and-expected-behavior).

For more detailed error messages, enable debug logging for the MijnTed component in your Home Assistant configuration by adding the following to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.mijnted: debug
```

## Reporting issues

When opening a GitHub issue, include reproducible steps, expected vs actual behavior, logs, and environment details.

- See [issue reporting](doc/ISSUE_REPORTING.md) for a full checklist and copy/paste bug report template.
- Use the default GitHub issue forms (`Bug report`, `Feature request`, `Question`) to start with the right structure.
- For security vulnerabilities, follow the [private reporting policy](SECURITY.md) instead of opening a public issue.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

Start with the [development guide](doc/DEVELOPMENT.md) for local setup, tests,
CI, Home Assistant verification, and agent tooling. [AGENTS.md](AGENTS.md)
maps implementation instructions; [CLAUDE.md](CLAUDE.md) is the Claude entry point.
