"""Exercise the installed generator against a local tagged mirror, without publishing a real tag."""

import compileall
import os
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

import yaml

from meds_algorithm_template.cli import TEMPLATE_REPOSITORY


def main():
    source = Path(sys.argv[1]).resolve()
    release = version("meds-algorithm-template")
    command = Path(sys.executable).parent / (
        "meds-algorithm-template.exe" if sys.platform == "win32" else "meds-algorithm-template"
    )
    subprocess.run([str(command), "--version"], check=True)
    subprocess.run([str(command), "--help"], check=True, capture_output=True)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        mirror = root / "mirror"
        mirror.mkdir()
        shutil.copy2(source / "copier.yml", mirror)
        shutil.copytree(source / "template", mirror / "template")
        for args in (
            ["init"],
            ["config", "user.name", "Wheel smoke"],
            ["config", "user.email", "wheel-smoke@example.invalid"],
            ["add", "."],
            ["-c", "commit.gpgsign=false", "commit", "-m", "Local release fixture"],
            ["-c", "tag.gpgsign=false", "tag", f"v{release}"],
        ):
            subprocess.run(["git", "-C", str(mirror), *args], check=True, capture_output=True)
        env = {
            **os.environ,
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": f"url.{mirror.as_uri()}.insteadOf",
            "GIT_CONFIG_VALUE_0": TEMPLATE_REPOSITORY,
        }
        for name, profiles in (
            ("single", ["supervised"]),
            (
                "family",
                [
                    "supervised",
                    "finetune",
                    "probe",
                    "zero_shot_direct",
                    "zero_shot_materialized",
                    "predict_only",
                ],
            ),
        ):
            answers = root / f"{name}.yaml"
            answers.write_text(yaml.safe_dump({"algorithm_name": name, "profiles": profiles}))
            output = root / name
            subprocess.run(
                [str(command), str(output), "--defaults", "--trust", "--data-file", str(answers)],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            recorded = yaml.safe_load((output / ".copier-answers.yml").read_text())
            assert recorded["_src_path"] == TEMPLATE_REPOSITORY
            assert recorded["_commit"] == f"v{release}"
            assert sorted(path.name for path in (output / "algorithms").iterdir()) == sorted(profiles)
            assert compileall.compile_dir(output / "src", quiet=1)
            assert not (output / "src/meds_algorithm").exists()
    print("Installed generator: single/all-profile rendering, release tag and update source verified")


if __name__ == "__main__":
    main()
