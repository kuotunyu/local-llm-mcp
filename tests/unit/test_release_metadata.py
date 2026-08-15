from __future__ import annotations

import json
import tomllib
from pathlib import Path

import local_llm_mcp

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_VERSION = "0.2.0"


def test_release_version_is_consistent_across_public_metadata() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    assert pyproject["project"]["version"] == EXPECTED_VERSION
    assert local_llm_mcp.__version__ == EXPECTED_VERSION
    assert manifest["version"] == EXPECTED_VERSION
    assert pyproject["project"]["urls"]["Release"].endswith(
        f"/releases/tag/v{EXPECTED_VERSION}"
    )


def test_release_metadata_keeps_external_boundary_explicit() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    project_description = pyproject["project"]["description"].lower()
    manifest_description = manifest["description"].lower()
    assert "opt-in" in project_description and "cloud" in project_description
    assert "opt-in" in manifest_description and "cloud" in manifest_description
