"""Exercise the retrieval scripts against public-page fixtures without network I/O."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
CLIENT_ID = "60e8b8d3-1644-4013-837f-5dc29eb93c70"
OTHER_CLIENT_ID = "11111111-2222-3333-4444-555555555555"

BASH_WRAPPER = r'''
curl() {
    if [[ "$MIJNTED_TEST_FAILURE" == 1 ]]; then
        return 22
    fi
    case "${!#}" in
        https://mijnted.nl/) printf '%s' "$MIJNTED_TEST_PAGE" ;;
        https://mijnted.nl/assets/app.js) printf '%s' "$MIJNTED_TEST_BUNDLE" ;;
        *) printf 'Unexpected URL: %s\n' "${!#}" >&2; return 99 ;;
    esac
}
source "$1"
'''

POWERSHELL_WRAPPER = r'''
function Invoke-WebRequest {
    param($Uri, [switch]$UseBasicParsing, $TimeoutSec)
    if ($env:MIJNTED_TEST_FAILURE -eq '1') { throw 'HTTP failure' }
    switch ($Uri.ToString()) {
        'https://mijnted.nl/' { return [PSCustomObject]@{Content = $env:MIJNTED_TEST_PAGE} }
        'https://mijnted.nl/assets/app.js' { return [PSCustomObject]@{Content = $env:MIJNTED_TEST_BUNDLE} }
        default { throw "Unexpected URL: $Uri" }
    }
}
& $env:MIJNTED_TEST_SCRIPT
'''


@pytest.fixture(params=["bash", "powershell", "pwsh"])
def run_script(request):
    """Run each installed shell with mocked website responses."""
    shell = shutil.which(request.param)
    if shell is None:
        pytest.skip(f"{request.param} is not installed")

    def run(bundle, page=None, failure=False):
        """Execute one fixture and capture stdout, stderr, and exit status."""
        extension = "sh" if request.param == "bash" else "ps1"
        script = SCRIPTS / f"get_client_id.{extension}"
        env = {
            **os.environ,
            "MIJNTED_TEST_PAGE": page or '<script type="module" src="/assets/app.js"></script>',
            "MIJNTED_TEST_BUNDLE": bundle,
            "MIJNTED_TEST_FAILURE": "1" if failure else "0",
            "MIJNTED_TEST_SCRIPT": str(script),
        }
        if request.param == "bash":
            # Git Bash accepts forward-slash drive paths when run by Windows Python.
            command = [shell, "-c", BASH_WRAPPER, "--", script.as_posix()]
        else:
            command = [shell, "-NoProfile", "-NonInteractive", "-Command", POWERSHELL_WRAPPER]
        return subprocess.run(command, env=env, capture_output=True, text=True, timeout=30)

    return run


@pytest.mark.parametrize("quote", ['"', "'", "`"])
def test_extracts_one_application_id_and_ignores_unrelated_ids(run_script, quote):
    """Repeated application ID and unrelated UUID -> one unambiguous application ID."""
    application = f"factory({quote}{CLIENT_ID}{quote}, {quote}MyTedprod{quote})"
    bundle = f'other("{OTHER_CLIENT_ID}");{application};{application}'

    result = run_script(bundle)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == CLIENT_ID


@pytest.mark.parametrize("bundle", [
    "no application configuration here",
    f'factory("{CLIENT_ID}","MyTedprod");factory("{OTHER_CLIENT_ID}","MyTedprod")',
])
def test_missing_or_ambiguous_application_id_fails(run_script, bundle):
    """Missing or conflicting IDs -> fail instead of printing a guessed ID."""
    result = run_script(bundle)

    assert result.returncode != 0
    assert not result.stdout.strip()
    assert "Could not identify a single MijnTed client ID" in result.stderr


def test_ignores_third_party_scripts(run_script):
    """Third-party script URL -> no request is sent to that host."""
    result = run_script("", page='<script src="https://example.com/assets/app.js"></script>')

    assert result.returncode != 0
    assert "Unexpected URL" not in result.stderr


def test_http_failure_is_reported(run_script):
    """HTTP failure -> nonzero exit status and no application ID."""
    result = run_script("", failure=True)

    assert result.returncode != 0
    assert not result.stdout.strip()
