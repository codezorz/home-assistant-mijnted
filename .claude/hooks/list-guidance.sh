#!/usr/bin/env bash
# Claude SessionStart: advertise shared headers, never full guidance bodies.
set -euo pipefail
export LC_ALL=C

root="$(git -C "${CLAUDE_PROJECT_DIR:-.}" rev-parse --show-toplevel 2>/dev/null)" || exit 0
[ -n "$root" ] || exit 0
shopt -s nullglob

# Repository metadata uses one-line scalars; see agent-tooling.instructions.md.
fm() {
  local key="$1" file="$2" val
  val="$(awk -v key="$key" '
    { sub(/\r$/, "") }
    NR == 1 { if ($0 != "---") exit; next }
    $0 == "---" { exit }
    index($0, key ":") == 1 {
      sub("^" key ":[[:space:]]*", "")
      sub(/[[:space:]]*$/, "")
      print
      exit
    }
  ' "$file")"
  if [[ "$val" == \"*\" || "$val" == \'*\' ]]; then
    val="${val:1:${#val}-2}"
  fi
  printf '%s' "$val"
}

printf '## Repository guidance (relative to the active checkout root)\n\n'

skills=("$root"/.agents/skills/*/SKILL.md)
if ((${#skills[@]})); then
  printf '### Shared skills\nRead each matching SKILL.md in full before that kind of work.\n\n'
  for f in "${skills[@]}"; do
    name="$(fm name "$f")"
    desc="$(fm description "$f")"
    folder="$(basename "$(dirname "$f")")"
    if [[ ! "$name" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ || "$name" != "$folder" || -z "$desc" ]]; then
      printf 'Invalid skill metadata: %s\n' "${f#"$root"/}" >&2
      continue
    fi
    printf -- '- %s — %s — %s\n' "$name" "${f#"$root"/}" "$desc"
  done
  printf '\n'
fi

instructions=("$root"/.github/instructions/*.instructions.md)
if ((${#instructions[@]})); then
  printf '### Scoped instructions\nRead all matching applyTo files, including global ** rules, before editing.\nResolve contradictions explicitly; do not assume a more specific file cancels another rule.\n\n'
  for f in "${instructions[@]}"; do
    scope="$(fm applyTo "$f")"
    desc="$(fm description "$f")"
    if [[ -z "$scope" || -z "$desc" ]]; then
      printf 'Invalid instruction metadata: %s\n' "${f#"$root"/}" >&2
      continue
    fi
    printf -- '- %s — applyTo: %s — %s\n' "${f#"$root"/}" "$scope" "$desc"
  done
fi
