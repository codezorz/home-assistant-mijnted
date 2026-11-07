#!/usr/bin/env bash
# Print the client ID from MijnTed's public JavaScript.
set -euo pipefail

site='https://mijnted.nl'
html=$(curl --fail --silent --show-error --location --max-time 30 "$site/")
script_pattern="<script[^>]*src=['\"][^'\"]+\.js['\"]"
script_paths=$(printf '%s\n' "$html" | grep -oEi "$script_pattern" |
    sed -E "s/.*src=['\"]([^'\"]+)['\"]$/\1/" || true)
uuid='[[:xdigit:]]{8}-[[:xdigit:]]{4}-[[:xdigit:]]{4}-[[:xdigit:]]{4}-[[:xdigit:]]{12}'
quote="[\"'\`]"
client_pattern="${quote}${uuid}${quote}[[:space:]]*,[[:space:]]*${quote}MyTedprod${quote}"
client_ids=''

while IFS= read -r script_path; do
    # Only fetch application bundles hosted by MijnTed itself.
    case "$script_path" in
        /assets/*.js) script_url="$site$script_path" ;;
        assets/*.js|./assets/*.js) script_url="$site/${script_path#./}" ;;
        "$site"/assets/*.js) script_url="$script_path" ;;
        *) continue ;;
    esac
    javascript=$(curl --fail --silent --show-error --location --max-time 30 "$script_url")
    matches=$(printf '%s\n' "$javascript" | grep -oEi "$client_pattern" |
        grep -oEi "$uuid" | tr '[:upper:]' '[:lower:]' || true)
    client_ids+=$'\n'"$matches"
done <<< "$script_paths"

client_ids=$(printf '%s\n' "$client_ids" | sed '/^$/d' | sort -u)
if [[ ! "$client_ids" =~ ^[[:xdigit:]-]{36}$ ]]; then
    printf '%s\n' 'Could not identify a single MijnTed client ID. Use the browser method in the README.' >&2
    exit 1
fi
printf '%s\n' "$client_ids"
