#!/usr/bin/env pwsh

# Construct the path to the .venv activation script
$activateScript = Join-Path $PSScriptRoot "..\.venv\Scripts\Activate.ps1"

# Check if the activation script exists
if (-not (Test-Path $activateScript)) {
    Write-Host "Error: Activation script not found at $activateScript"
    Write-Host "Make sure the .venv is set up correctly."
    exit 1
}

# Activate the environment
. $activateScript
Write-Host ".venv activated successfully."
