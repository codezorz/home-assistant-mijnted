#!/usr/bin/env pwsh

# Construct the path to the mijnted_env activation script
$activateScript = Join-Path $PSScriptRoot "..\mijnted_env\Scripts\Activate.ps1"

# Check if the activation script exists
if (-not (Test-Path $activateScript)) {
    Write-Host "Error: Activation script not found at $activateScript"
    Write-Host "Make sure the mijnted_env is set up correctly."
    exit 1
}

# Activate the environment
. $activateScript
Write-Host "mijnted_env activated successfully."
