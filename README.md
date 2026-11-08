# Home Assistant MijnTed Integration

This custom component integrates MijnTed devices with Home Assistant, allowing you to monitor your energy usage and other related data within your smart home setup.

## Documentation

This README covers installation, configuration, and everyday usage. Detailed
references live in [`docs/`](docs/README.md):

| Guide | What it covers |
|---|---|
| [Sensors and buttons](docs/SENSORS.md) | Values, attributes, missing-data behavior, statistics, and the reset button |
| [Month transitions](docs/MONTH_SWITCH.md) | API lag, month lifecycle, baseline locking, and late corrections |
| [API and authentication](docs/ENDPOINTS.md) | Endpoints, client methods, response formats, and token rotation |
| [Reporting issues](docs/ISSUE_REPORTING.md) | Diagnostic information and a bug-report template |

## Installation

### Install through Marketplace

1. Open **Settings > Marketplace** as an administrator.
2. Select **Add from link** in the upper-right corner.
3. Enter `https://github.com/codezorz/home-assistant-mijnted` under **GitHub link** and select **Add**. Connect GitHub if prompted.
4. If prompted for a content type, select **Integration** and select **Add** again.
5. Open **MijnTed**, select **Install**, review the version, and confirm **Install**.
6. Follow the integration setup flow that opens after installation. If Marketplace requests a restart, restart Home Assistant first, then add **MijnTed** under **Settings > Devices & services > Add integration**.

### Manual installation

1. Download **`mijnted.zip`** from the desired [GitHub release](https://github.com/codezorz/home-assistant-mijnted/releases).
2. Extract its contents into your Home Assistant's `custom_components/mijnted` directory. The ZIP contains `manifest.json` and the integration files directly at its root.
3. Restart Home Assistant.
4. Go to Settings > Devices & services > Integrations.
5. Click the "+ ADD INTEGRATION" button and search for "MijnTed".
6. Follow the configuration steps.

Install the `mijnted.zip` release asset: it contains the stamped release version.
Repository source checkouts report the development version `0.0.0-dev.0`.

### Updates and beta versions

Marketplace installs the versioned `mijnted.zip` release asset.

Updates appear under **Settings > Updates**. Restart Home Assistant after updating
the integration to load the new code; Marketplace creates a repair reminder when
a restart is needed.

Stable releases are offered by default. To test a beta, open the MijnTed
repository's device page under
**Settings > Devices & services > Marketplace**. Enable its disabled **Pre-release**
entity, then turn on the switch. To select a specific available release, open the
MijnTed Marketplace page's three-dot menu and select **Install another version**.

## Configuration

To set up the MijnTed integration, you'll need:

1. The MijnTed client ID (see [retrieval options below](#obtaining-your-client-id))
2. Your MijnTed username (email address)
3. Your MijnTed password

You can also choose a device name, such as `Home` or `Office`. Home Assistant
uses this name as the prefix for the integration's entity names. The name and
polling interval can be changed later from the integration's configuration
options.

English, Dutch, and German are supported. See
[language and display names](docs/SENSORS.md#language-and-display-names) for language
selection, custom names, and stable numbering of duplicate device labels.

### Obtaining Your Client ID

Retrieve the client ID using either method below, then paste the result into the
**client-id** field during integration setup.

#### Retrieve with a script

Download [get_client_id.ps1](scripts/get_client_id.ps1) for PowerShell or
[get_client_id.sh](scripts/get_client_id.sh) for Bash. Save the linked file's raw
contents, then run it from the directory where you saved it:

**PowerShell (Windows PowerShell 5.1 or PowerShell 7):**

```powershell
.\get_client_id.ps1
```

**Bash (requires curl and standard Unix tools: grep, sed, sort, and tr):**

```bash
bash ./get_client_id.sh
```

Both scripts download the public MijnTed page and its JavaScript, then print the
client ID. Copy the printed value into the integration's **client-id** field.
If the script cannot identify a single ID, use the browser method.

#### Retrieve manually in a browser

To retrieve the client ID in your browser:

1. Open the [MijnTed website](https://mijnted.nl).
2. Open your browser's developer tools (F12) and select **Network**.
3. Filter by **JS**, then reload the page.
4. Select the application JavaScript file whose path starts with `/assets/index-`
   and ends in `.js`, then open its **Response** tab.
5. Search the response for `MyTedprod`. Look for a function call with a UUID
   immediately before `MyTedprod`, as in the example below. The function name and
   quotation marks may differ.
6. Copy that UUID into the integration's **client-id** field.

```javascript
someFunction("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", "MyTedprod")
```

The first argument is the client ID; `MyTedprod` identifies the authentication
tenant. The `x` characters above are placeholders, not a value to enter.

**Polling Interval (Optional):**
- Default: 3600 seconds (1 hour)
- Range: 3600-86400 seconds (1 hour to 24 hours)
- You can configure this during setup or leave it at the default
- To change it later, open the integration's options/configure dialog in Settings > Devices & services. Saving the interval reloads the integration.

During setup, enter your client ID, username, and password. The integration handles OAuth 2.0 and retains credentials, the client ID, and tokens in the Home Assistant config entry for automatic reauthentication. See the [authentication reference](docs/ENDPOINTS.md#authentication-lifecycle) for details.

## Usage

The integration provides:

- **Monthly usage** for calendar-month progress and **Published usage** for the
  latest available reading month, plus building averages and last-year comparisons.
- Total and individual meter readings, with water meters usable in the Energy dashboard.
- Diagnostic dates, model/unit information, and a **Reset statistics** button.

The [sensor reference](docs/SENSORS.md) owns values, attributes, units, availability,
and reset behavior. Usage sensors request zero displayed decimal places without
rounding the underlying values.

### History and Statistics

With recorder enabled, select the external statistics from source **mijnted**:
**Month + Mean** for monthly reports, **Day + Mean** for daily consumption.
See [graph setup and YAML](docs/SENSORS.md#monthly-usage-and-building-average-graphs).
Ordinary entity history records receipt time; the reporting series identify
consumption periods. [Month transitions](docs/MONTH_SWITCH.md) explain API lag and corrections.

## API

`MijntedApi` handles data endpoints and `MijntedAuth` manages tokens and
credential-based rotation. The [endpoint reference](docs/ENDPOINTS.md) owns the
method mapping, request/response examples, and retry details.

## Troubleshooting

If you encounter issues:

1. Check that your MijnTed client ID and login credentials are correct and that you can log in on the MijnTed website.
2. Ensure your internet connection is stable.
3. Verify that the MijnTed API is accessible.
4. Refresh-token rotation is automatic. If it fails and Home Assistant requests reauthentication, complete that flow with your client ID, username, and password; you do not need to paste a refresh token manually.
5. If readings look stale, compare **Last update** with **Last successful sync**. MijnTed readings often lag the calendar date; a recent sync can also contain partial endpoint failures. Check logs and the [sensor edge cases](docs/SENSORS.md#edge-cases-and-expected-behavior).

For more detailed error messages, enable debug logging for the MijnTed component in your Home Assistant configuration by adding the following to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.mijnted: debug
```

## Reporting issues

Use [issue reporting](docs/ISSUE_REPORTING.md) for the issue forms, diagnostic
information, and pre-submission checks. Report vulnerabilities through the
[private reporting policy](SECURITY.md).

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

Start with [CONTRIBUTING.md](CONTRIBUTING.md) for the development guidance map,
including local setup, tests, CI, and Home Assistant verification. Development
instructions live in [`.github/instructions/`](.github/instructions/README.md);
shared skills live in [`.agents/skills/`](.agents/skills/README.md).
[AGENTS.md](AGENTS.md) and [CLAUDE.md](CLAUDE.md) are the agent entry points.
