---
applyTo: "custom_components/mijnted/**,tests/test_localization.py,tests/test_device_naming.py,tests/ha_localization_check.py"
description: UI translation coverage, native HA fallback, dynamic labels, and language maintenance.
---

# Translations

- Translate integration-owned flows/fields/selectors/errors/success messages,
  entity/button names, supported state/attribute labels, user-visible exceptions,
  repairs when present, room context, and statistic labels.
- Ship complete matching `translations/en.json`, `nl.json`, and `de.json` files in
  the supported custom-integration schema. Use finished strings, not core-only
  `strings.json` compilation or unresolved `[%key:...%]` references.
- English is the complete fallback. Use HA's translation APIs and language selection;
  do not implement another locale loader/fallback/cache. Use `translation_key`,
  `translation_placeholders`, and `has_entity_name`; preserve grammar and acronyms
  instead of overriding names with English or mechanically capitalizing text.
- Keep IDs, keys, numeric states, canonical recorder units, API/model codes, brands,
  and user names stable. Known diagnostic descriptions use semantic enum states;
  preserve raw payloads and unknown descriptions/symbols. Developer logs, code,
  comments, and contributor docs are outside UI scope.
- Keep one room mapping in `localization.ROOM_KEYS`; human labels belong in `common`.
  Prepare dynamic placeholders outside properties. Numbering comes from `naming.py`
  and uses `common.numbered_context`, never localized text as identity.
- Use `STATISTIC_TRANSLATION_KEYS` consistently across exporters. Update existing
  metadata names without changing other fields/samples; failures must not block
  sensor setup. Retry callbacks/tasks must be entry-scoped and cleaned up on unload.
- [Language and display names](../../docs/SENSORS.md#language-and-display-names)
  owns the user-facing language/update policy and intentionally raw surfaces.
  Preserve registry user-name overrides and user-owned dashboard labels.
- To add a language, translate the complete English structure without changing keys
  or placeholders. Extend locale/entity/series coverage and run checks from the
  [development guide](../../docs/DEVELOPMENT.md#native-home-assistant-localization-checks).
