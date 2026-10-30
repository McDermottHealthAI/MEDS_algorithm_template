"""Require an index-released shared dependency before publishing the template generator."""

import json
import re
import tomllib
from pathlib import Path
from urllib.request import urlopen


def main():
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text())
    generated = (root / "template/pyproject.toml.jinja").read_text()
    development = project["dependency-groups"]["dev"]
    if "git+" in generated or any("meds-algorithm" in item and "git+" in item for item in development):
        raise SystemExit(
            "Publish meds-algorithm first, then replace template and dev Git pins with PyPI pins."
        )
    pins = re.findall(r"meds-algorithm\[[^\]]+\]==([0-9A-Za-z.]+)", generated)
    if len(pins) != 2 or len(set(pins)) != 1:
        raise SystemExit(
            "Generated data and conformance dependencies must pin the same meds-algorithm version."
        )
    release = pins[0]
    if f"meds-algorithm[conformance]=={release}" not in development:
        raise SystemExit(
            "The template dev dependency must use the same released version as generated projects."
        )
    with urlopen(f"https://pypi.org/pypi/meds-algorithm/{release}/json", timeout=30) as response:
        metadata = json.load(response)
    if not metadata.get("urls"):
        raise SystemExit("The pinned meds-algorithm release has no downloadable files on PyPI.")
    print(f"Release prerequisite verified: meds-algorithm=={release} is on PyPI")


if __name__ == "__main__":
    main()
