#!/usr/bin/env pwsh

param(
    [Parameter(Mandatory=$true)]
    [string]$Username,

    [Parameter(Mandatory=$true)]
    [SecureString]$Password,

    [Parameter(Mandatory=$true)]
    [string]$ClientId
)

# Convert SecureString to plain text
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password)
$PlainTextPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

# Set environment variables
$env:MIJNTED_USERNAME = $Username
$env:MIJNTED_PASSWORD = $PlainTextPassword
$env:MIJNTED_CLIENT_ID = $ClientId

# Clear the plain text password from memory
$PlainTextPassword = $null
[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)

# Navigate to the directory containing your tests
Set-Location -Path "$PSScriptRoot\..\custom_components\mijnted"

# Run pytest
pytest tests

# Navigate back to the root directory
Set-Location -Path "$PSScriptRoot"
