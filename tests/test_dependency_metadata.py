"""Keep the security-scanning dependency graph aligned with HA runtime inputs."""

import json
from pathlib import Path
import tomllib

from packaging.requirements import Requirement


def test_locked_project_includes_manifest_runtime_requirements():
    """Every HA runtime requirement is mirrored, including its version constraints."""
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "custom_components/mijnted/manifest.json").read_text(encoding="utf-8"))
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))

    assert {Requirement(value) for value in manifest["requirements"]} == {
        Requirement(value) for value in project["project"]["dependencies"]
    }


def test_native_profile_includes_runtime_inputs_and_matching_ha_fixtures():
    """The isolated native lock covers integration inputs and a paired HA/fixture target."""
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "custom_components/mijnted/manifest.json").read_text(encoding="utf-8"))
    profile = tomllib.loads((root / "tests_native/pyproject.toml").read_text(encoding="utf-8"))
    requirements = {Requirement(value) for value in profile["project"]["dependencies"]}
    assert {Requirement(value) for value in manifest["requirements"]} <= requirements
    by_name = {requirement.name.lower(): requirement for requirement in requirements}
    assert by_name["homeassistant"].specifier == by_name["pytest-homeassistant"].specifier
