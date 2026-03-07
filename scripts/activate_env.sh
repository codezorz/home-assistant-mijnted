#!/usr/bin/env bash

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "Run this script with:"
    echo "  source scripts/activate_env.sh"
    exit 1
fi

venv_path="${MIJNTED_VENV_PATH:-$HOME/.venv-home-assistant}"
activate_script="${venv_path}/bin/activate"

if [[ ! -f "${activate_script}" ]]; then
    echo "Error: activation script not found at ${activate_script}"
    echo "Set MIJNTED_VENV_PATH to your virtual environment path and try again."
    return 1
fi

# shellcheck disable=SC1090
source "${activate_script}"
echo "Activated virtual environment: ${venv_path}"
