---
applyTo: "custom_components/mijnted/**,tests/test_localization.py,tests/ha_localization_check.py"
description: Authoritative UI localization coverage, native HA fallback, dynamic names, statistic metadata, and adding languages.
---

# Translations

- Translate integration-owned setup/options/reauthentication text, fields,
  selector choices when present, errors, abort/success messages, sensor/button
  names, supported state/attribute labels, and user-visible HA exceptions/repairs.
  Ship complete matching `translations/en.json`, `nl.json`, and `de.json` files.
  Use supported custom-integration sections and finished strings; core-only
  `strings.json` compilation and `[%key:...%]` references do not apply here.
- English is the complete fallback. Use HA's translation APIs and server-language
  selection; do not implement another locale loader, fallback chain, or cache.
  `localization.py` loads installation-language resources during platform setup.
  Use entity `translation_key`, `translation_placeholders`, and `has_entity_name`.
  Do not override names with English strings or mechanically capitalize labels.
- Keep entity/unique/device/statistic IDs, translation keys, raw API codes,
  attribute keys, numeric states, recorder units, model identifiers, brands, and
  user-supplied names stable. Frontend attribute labels do not rename raw keys.
  Developer logs, identifiers, comments, and contributor docs are outside UI scope.
- Known human-readable diagnostic unit descriptions use semantic enum states
  and HA state translations. Keep their API identifier/label alias mapping in
  `sensors/diagnostics.py`; preserve unknown descriptions/symbols verbatim and
  the original payload in attributes. Document raw-state compatibility changes;
  never use this presentation mapping to change numeric sensors' recorder units.
- `localization.ROOM_KEYS` is the single room-code-to-semantic-key mapping.
  Human labels belong in `common`; resolve them with HA's translated resources.
  Preserve unknown codes and arbitrary names verbatim. Missing rooms use the
  device number. Prepare dynamic placeholders outside properties, refreshing
  HA's cached name on coordinator updates without changing identity.
- Entity defaults follow HA's platform setup/registry lifecycle, including for
  existing entries. Reload/restart after a server-language change refreshes
  defaults; never replace registry user-name overrides or regenerate entity IDs.
- External-statistic names are installation-level stored metadata. Resolve all
  five reporting series through `STATISTIC_TRANSLATION_KEYS`, independently of
  their exporter and enabled standalone entities. The calendar Monthly usage
  entity and Published usage series deliberately have different semantic names.
  On setup, update existing names with metadata-only external imports, preserving
  every non-name field and all samples. Normal imports use the same resolver.
  Metadata failures must not block sensor setup; retry on later successful
  coordinator updates, with one task in flight and listener/task cleanup on unload.
- [Language and display names](../../docs/SENSORS.md#language-and-display-names) owns user-visible behavior and
  explicit exceptions for raw diagnostic states and nested payloads. Do not
  localize raw states just to make their presentation prettier.
- To add a language, copy the complete English structure, translate all text,
  retain keys and placeholder names, and keep natural grammar/acronyms. Add it to
  locale completeness checks and run the local suite plus native HA checks from
  [the native-check guide](../../docs/DEVELOPMENT.md#native-home-assistant-localization-checks). Cover new
  entities/series and dynamic cases in the same change.
