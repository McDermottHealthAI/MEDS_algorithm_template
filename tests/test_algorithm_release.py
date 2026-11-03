"""Generated releases must work without the checkout and reject incomplete publication."""

import os
import subprocess
import sys
import tarfile
import tomllib
import zipfile

import pytest
import yaml
from copier import run_copy
from test_render import REPO


def release_project(tmp_path, profiles):
    destination = tmp_path / "algorithm"
    run_copy(
        str(REPO),
        destination,
        data={
            "algorithm_slug": "release_example",
            "algorithm_class": "ReleaseExample",
            "package_name": "different-pypi-name",
            "algorithm_description": 'An "auditable" algorithm',
            "repository_url": "https://github.com/example/algorithm",
            "license_expression": "MIT",
            "profiles": profiles,
        },
        defaults=True,
        unsafe=True,
        quiet=True,
    )
    return destination


@pytest.mark.parametrize("profiles", [["supervised"], ["finetune", "probe"]])
def test_generated_distribution_installs_without_checkout(tmp_path, profiles):
    destination = release_project(tmp_path, profiles)
    (destination / "LICENSE").write_text("MIT License\nCopyright Test fixture\n")
    for name in ("datasets", "runs"):
        (destination / name).mkdir()
        (destination / name / "private-fixture.txt").write_text("Must not be distributed")
    # Run the exact gate used by generated CI/publishing, including sdist -> wheel and both installs.
    result = subprocess.run(
        ["bash", "scripts/check_distribution.sh"],
        cwd=destination,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    project = tomllib.loads((destination / "pyproject.toml").read_text())["project"]
    assert project["name"] == "different-pypi-name"
    assert project["description"] == 'An "auditable" algorithm'
    with zipfile.ZipFile(next((destination / "dist").glob("*.whl"))) as wheel:
        assert "release_example/resources/runs/run.yaml" in wheel.namelist()
        for profile in profiles:
            assert f"release_example/resources/algorithms/{profile}/model.yaml" in wheel.namelist()
        assert not any(name.startswith(("tests/", "runs/", "slurm/")) for name in wheel.namelist())
    with tarfile.open(next((destination / "dist").glob("*.tar.gz"))) as archive:
        assert any(name.endswith("/configs/runs/run.yaml") for name in archive.getnames())
        assert not any("private-fixture.txt" in name for name in archive.getnames())
    workflow = yaml.safe_load((destination / ".github/workflows/publish.yml").read_text())
    assert workflow["jobs"]["publish"]["needs"] == "build"
    assert workflow["jobs"]["publish"]["permissions"] == {"id-token": "write"}
    assert workflow["jobs"]["publish"]["environment"]["name"] == "${{ inputs.index }}"


def test_generated_release_gate_rejects_incomplete_projects_and_wrong_tags(tmp_path):
    destination = release_project(tmp_path, ["supervised"])
    environment = {**os.environ, "PYTHONPATH": str(destination / "src")}
    environment.pop("GITHUB_REF", None)

    def check():
        return subprocess.run(
            [sys.executable, "scripts/check_release.py"],
            cwd=destination,
            env=environment,
            text=True,
            capture_output=True,
        )

    assert "LICENSE" in check().stderr
    (destination / "LICENSE").write_text("MIT License\n")
    assert "Finish declared profiles" in check().stderr
    implementation = destination / "src/release_example/release_example.py"
    implementation.write_text(
        implementation.read_text().replace("STUB_PROFILES = set(PROFILES)", "STUB_PROFILES = set()")
    )
    assert check().returncode == 0
    environment["GITHUB_REF"] = "refs/heads/main"
    assert "matching" in check().stderr
    environment["GITHUB_REF"] = "refs/tags/v9.9.9"
    assert "matching" in check().stderr
    environment["GITHUB_REF"] = "refs/tags/v0.1.0"
    assert check().returncode == 0
    metadata = destination / "pyproject.toml"
    original = metadata.read_text()
    metadata.write_text(
        original.replace('Repository = "https://github.com/example/algorithm"', 'Repository = ""')
    )
    assert "Repository" in check().stderr
    metadata.write_text(original.replace('"pyyaml>=6"', '"example @ https://example.org/example.whl"'))
    assert "index-installable" in check().stderr
