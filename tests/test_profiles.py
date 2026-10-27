"""Exercise coexistence, command boundaries, and descriptor wiring across profiles."""

import importlib
import os
import shlex
import subprocess
import sys

import pytest
import yaml
from copier import run_copy
from test_render import ALGORITHM_PROFILES, TEMPLATE_REPO, _dry_run


def test_algorithm_name_controls_module_classes_exports_and_command(tmp_path):
    import tomllib

    dst = tmp_path / "retain"
    run_copy(
        str(TEMPLATE_REPO),
        str(dst),
        data={"algorithm_name": "RETAIN", "algorithm_slug": "retain", "algorithm_class": "RETAIN"},
        defaults=True,
        unsafe=True,
        quiet=True,
    )
    assert (dst / "src/retain/retain.py").is_file()
    assert not (dst / "src/retain/commands.py").exists()
    scripts = tomllib.loads((dst / "pyproject.toml").read_text())["project"]["scripts"]
    assert scripts["retain"] == scripts["meds-algorithm"] == "retain.__main__:main"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from retain import RETAIN, RETAINConfig; "
            "from retain.retain import RETAIN as Direct; "
            "assert RETAIN is Direct; assert RETAIN.__module__ == 'retain.retain'; "
            "assert RETAIN(RETAINConfig()).name == 'retain'",
        ],
        env={**os.environ, "PYTHONPATH": str(dst / "src")},
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "answer",
    [
        {"algorithm_slug": "../retain"},
        {"algorithm_slug": "retain-v2"},
        {"algorithm_slug": "class"},
        {"algorithm_slug": "config"},
        {"algorithm_class": "bad name"},
        {"algorithm_class": "AlgorithmRepository"},
    ],
)
def test_invalid_or_colliding_algorithm_names_are_rejected(tmp_path, answer):
    with pytest.raises(ValueError):
        run_copy(
            str(TEMPLATE_REPO), str(tmp_path / "bad"), data=answer, defaults=True, unsafe=True, quiet=True
        )


@pytest.fixture
def multi(tmp_path, monkeypatch):
    dst = tmp_path / "multi"
    run_copy(
        str(TEMPLATE_REPO),
        str(dst),
        data={
            "algorithm_slug": "multi_algorithm",
            "profiles": list(ALGORITHM_PROFILES),
            "uses_predicates": True,
        },
        defaults=True,
        unsafe=True,
        quiet=True,
    )
    monkeypatch.syspath_prepend(str(dst / "src"))
    return dst


def cli(dst, *args):
    return subprocess.run(
        [sys.executable, "-m", "multi_algorithm", *args],
        env={**os.environ, "PYTHONPATH": str(dst / "src")},
        capture_output=True,
        text=True,
    )


def test_all_profiles_coexist_and_selection_is_required(multi):
    assert cli(multi, "profiles").stdout.splitlines() == list(ALGORITHM_PROFILES)
    assert not (multi / "model.yaml").exists()
    assert cli(multi, "commands").returncode != 0
    for profile, steps in ALGORITHM_PROFILES.items():
        assert cli(multi, "commands", "--profile", profile).stdout.splitlines() == steps
    cross = cli(multi, "predict_probe", "--profile", "supervised")
    assert cross.returncode != 0 and "not part of" in cross.stderr
    assert cli(multi, "commands", "--profile", "packaged").returncode != 0
    source = (multi / "src/multi_algorithm/multi_algorithm.py").read_text()
    assert source.count("def preprocess_data(") == 1
    assert source.count("def pretrain(") == 1


def test_descriptors_dispatch_only_their_profile_with_complete_arguments(multi):
    from meds_algorithm_core import ALGORITHM_PROFILES as profiles
    from meds_algorithm_core import STEP_SPECS, CommandName

    main = importlib.import_module("multi_algorithm.__main__")
    for profile in profiles:
        descriptor = yaml.safe_load((multi / "algorithms" / profile / "model.yaml").read_text())
        commands = descriptor["commands"]
        seen = set()
        for group in commands.values():
            for block in group.values():
                for line in (block or "").splitlines():
                    argv = shlex.split(line)
                    assert argv[:1] == ["meds-algorithm"]
                    assert argv[2:4] == ["--profile", profile]
                    step = CommandName(argv[1])
                    assert step in profiles[profile]
                    pairs = [item.split("=", 1) for item in argv[4:]]
                    assert len(pairs) == len({key for key, _ in pairs}), "duplicate argument"
                    arguments = {key: main._value(value) for key, value in pairs}
                    STEP_SPECS[step].validate(arguments)
                    seen.add(step)
        assert seen == set(profiles[profile])
        if profile == "predict_only":
            assert commands["supervised"]["train"] is None
            assert "unsupervised" not in commands
        if profile == "probe":
            assert "splits=[train,tuning,held_out]" in commands["supervised"]["train"]
            assert "input_embeddings_dir=" in commands["supervised"]["predict"]


def test_registration_keeps_profile_descriptors_separate(multi, tmp_path):
    from meds_algorithm_core.integrations.meds_dev import register

    dev = tmp_path / "MEDS-DEV"
    (dev / "src/MEDS_DEV/models").mkdir(parents=True)
    with pytest.raises(ValueError, match="Select --profile"):
        register(multi, dev, "algorithm")
    for profile in ALGORITHM_PROFILES:
        path = register(multi, dev, "algorithm", profile)
        assert path.name == f"algorithm__{profile}"
        assert (path / "model.yaml").read_bytes() == (
            multi / "algorithms" / profile / "model.yaml"
        ).read_bytes()
        assert str(multi.resolve()) in (path / "requirements.txt").read_text()
    with pytest.raises(ValueError):
        register(multi, dev, "../escape", "probe")
    with pytest.raises(ValueError):
        register(multi, dev, "algorithm", "missing")


def test_generated_requests_reject_unknown_arguments(multi):
    main = importlib.import_module("multi_algorithm.__main__")
    repository = main.create_repository()
    assert repository.profiles == tuple(ALGORITHM_PROFILES)
    with pytest.raises(ValueError, match="Unknown or forbidden"):
        repository.run(
            "preprocess_data",
            {
                "external_meds_dir": "/meds",
                "output_data_dir": "/data",
                "invented_option": True,
            },
            profile="supervised",
        )


def test_slurm_selects_one_profile_and_isolates_default_outputs(multi, tmp_path):
    for profile, steps in ALGORITHM_PROFILES.items():
        result = _dry_run(
            multi, "multi_algorithm", tmp_path, PROFILE=profile, RUN_ID="same", RUN_ROOT="/runs"
        )
        assert result.returncode == 0, result.stderr
        printed_steps = list(
            dict.fromkeys(
                line[2:].split(":")[0] for line in result.stdout.splitlines() if line.startswith("# ")
            )
        )
        assert printed_steps == steps
        assert f"/runs/same/{profile}/artifacts" in result.stdout
        if profile == "probe":
            assert "# infer_embeddings: splits=[train,tuning,held_out]" in result.stdout
    invalid = _dry_run(multi, "multi_algorithm", tmp_path, PROFILE="probe", STAGES="infer_trajectories")
    assert invalid.returncode != 0 and "sbatch" not in invalid.stdout


def test_generated_acceptance_tests_cover_every_profile(multi):
    report = (multi / "IMPLEMENTATION_REPORT.md").read_text()
    assert "## Zero-shot task translation" in report
    assert "## Zero-shot materialization" in report
    env = {**os.environ, "PYTHONPATH": str(multi / "src")}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=multi,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for profile in ALGORITHM_PROFILES:
        for test in (
            "test_end_to_end",
            "test_primary_behavior",
            "test_meds_dev_runs_algorithm_yaml",
            "test_full_dag_on_mimic_iv_demo",
        ):
            assert f"{test}[{profile}]" in result.stdout


def test_recorded_upstream_inputs_become_explicit_arguments(multi, tmp_path):
    from meds_algorithm_core import measured_artifact
    from meds_algorithm_core.artifacts.inputs import resolve_input

    data = tmp_path / "data"
    with measured_artifact(
        data, artifact_type="patients", command="preprocess_data", producer="test", payload_format="test/v1"
    ):
        pass
    algorithm = tmp_path / "algorithm"
    with measured_artifact(
        algorithm,
        artifact_type="supervised_algorithm",
        command="train_supervised",
        producer="test",
        payload_format="test/v1",
        inputs={"input_data_dir": {"path": str(data)}},
    ):
        pass
    assert resolve_input(algorithm, "input_data_dir") == data.resolve()
    with pytest.raises(ValueError, match="not an artifact input"):
        resolve_input(algorithm, "input_embeddings_dir")


def test_rendered_spec_points_to_core_and_contract_is_not_copied(multi):
    from meds_algorithm_core import CommandName
    from meds_algorithm_core.contracts.commands import CommandName as CoreCommandName

    assert CommandName is CoreCommandName
    assert not (multi / "src/meds_algorithm_contract").exists()
    assert not (multi / "src/meds_algorithm_core").exists()
    assert "meds-algorithm-core-spec" in (multi / "SPEC.md").read_text()
    assert not (multi / "docs/SOFTWARE_CONTRACT.md").exists()


def test_rendered_report_gate_checks_completed_profile_with_other_stubs(multi):
    script = """
import importlib.util
from pathlib import Path
from multi_algorithm.multi_algorithm import STUB_PROFILES
spec = importlib.util.spec_from_file_location('report_gate', Path('tests/test_report.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.test_completed_algorithm_has_a_completed_report()
STUB_PROFILES.remove('supervised')
module.test_completed_algorithm_has_a_completed_report()
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=multi,
        env={**os.environ, "PYTHONPATH": str(multi / "src")},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Incomplete implementation report: Source" in result.stderr
