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
