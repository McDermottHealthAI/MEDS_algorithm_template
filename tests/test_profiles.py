"""Exercise coexistence, command boundaries, and descriptor wiring across profiles."""

import importlib
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from copier import run_copy
from test_render import MODEL_PROFILES, TEMPLATE_REPO, _dry_run


@pytest.fixture
def multi(tmp_path, monkeypatch):
    dst = tmp_path / "multi"
    run_copy(
        str(TEMPLATE_REPO),
        str(dst),
        data={"model_slug": "multi_model", "profiles": list(MODEL_PROFILES), "uses_predicates": True},
        defaults=True,
        unsafe=True,
        quiet=True,
    )
    monkeypatch.syspath_prepend(str(dst / "src"))
    return dst


def cli(dst, *args):
    return subprocess.run(
        [sys.executable, "-m", "multi_model", *args],
        env={**os.environ, "PYTHONPATH": str(dst / "src")},
        capture_output=True,
        text=True,
    )


def test_all_profiles_coexist_and_selection_is_required(multi):
    assert cli(multi, "profiles").stdout.splitlines() == list(MODEL_PROFILES)
    assert not (multi / "model.yaml").exists()
    assert cli(multi, "commands").returncode != 0
    for profile, steps in MODEL_PROFILES.items():
        assert cli(multi, "commands", "--profile", profile).stdout.splitlines() == steps
    cross = cli(multi, "predict_probe", "--profile", "supervised")
    assert cross.returncode != 0 and "not part of" in cross.stderr
    assert cli(multi, "commands", "--profile", "packaged").returncode != 0
    source = (multi / "src/multi_model/commands.py").read_text()
    assert source.count("class PreprocessData(") == 1
    assert source.count("class Pretrain(") == 1


def test_descriptors_dispatch_only_their_profile_with_complete_arguments(multi):
    from meds_model_contract import MODEL_PROFILES as profiles
    from meds_model_contract import STEP_SPECS, CommandName

    main = importlib.import_module("multi_model.__main__")
    for profile in profiles:
        descriptor = yaml.safe_load((multi / "models" / profile / "model.yaml").read_text())
        commands = descriptor["commands"]
        seen = set()
        for group in commands.values():
            for block in group.values():
                for line in (block or "").splitlines():
                    argv = shlex.split(line)
                    assert argv[:1] == ["meds-model"]
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
    from meds_model_contract.meds_dev import register

    dev = tmp_path / "MEDS-DEV"
    (dev / "src/MEDS_DEV/models").mkdir(parents=True)
    with pytest.raises(ValueError, match="Select --profile"):
        register(multi, dev, "model")
    for profile in MODEL_PROFILES:
        path = register(multi, dev, "model", profile)
        assert path.name == f"model__{profile}"
        assert (path / "model.yaml").read_bytes() == (multi / "models" / profile / "model.yaml").read_bytes()
        assert str(multi.resolve()) in (path / "requirements.txt").read_text()
    with pytest.raises(ValueError):
        register(multi, dev, "../escape", "probe")
    with pytest.raises(ValueError):
        register(multi, dev, "model", "missing")


def test_registry_and_request_validation_reject_ambiguous_or_malformed_inputs(multi):
    from meds_model_contract import Command, CommandName, ModelRepository

    calls = []

    class Preprocess(Command):
        name = CommandName.preprocess_data

        def run(self, arguments):
            calls.append(arguments)
            return Path(arguments["output_data_dir"])

    class Predict(Command):
        name = CommandName.predict_only

        def run(self, arguments):
            calls.append(arguments)
            return Path(arguments["output_predictions_dir"])

    registry = {Preprocess.name: Preprocess, Predict.name: Predict}
    repository = ModelRepository(["predict_only"], registry)
    for profiles in ([], ["predict_only", "predict_only"], ["packaged"], "predict_only"):
        with pytest.raises(ValueError):
            ModelRepository(profiles, registry)
    with pytest.raises(ValueError):
        ModelRepository(["predict_only"], {Preprocess.name: Preprocess})
    with pytest.raises(ValueError):
        ModelRepository(["predict_only"], {Preprocess.name: Predict, Predict.name: Predict})
    good = {"external_meds_dir": "/meds", "output_data_dir": "/data"}
    assert repository.run("preprocess_data", good) == Path("/data")
    for bad in ({}, {**good, "do_overwrite": "false"}, {**good, "external_task_criteria_file": "/task"}):
        with pytest.raises(ValueError):
            repository.run("preprocess_data", bad)
    assert len(calls) == 1, "invalid arguments must not reach model code"
    prediction = {
        "input_data_dir": "/data",
        "external_index_dir": "/index",
        "output_predictions_dir": "/out",
    }
    for splits in (None, [], "held_out", ["train", "train"], [123]):
        with pytest.raises(ValueError, match="splits"):
            repository.run("predict_only", {**prediction, "splits": splits})


def test_slurm_selects_one_profile_and_isolates_default_outputs(multi, tmp_path):
    for profile, steps in MODEL_PROFILES.items():
        result = _dry_run(multi, "multi_model", tmp_path, PROFILE=profile, RUN_ID="same", RUN_ROOT="/runs")
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
    invalid = _dry_run(multi, "multi_model", tmp_path, PROFILE="probe", STAGES="infer_trajectories")
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
    for profile in MODEL_PROFILES:
        for test in (
            "test_end_to_end",
            "test_primary_behavior",
            "test_meds_dev_runs_model_yaml",
            "test_full_dag_on_mimic_iv_demo",
        ):
            assert f"{test}[{profile}]" in result.stdout


def test_recorded_upstream_inputs_become_explicit_arguments(multi, tmp_path):
    from meds_model_contract import measured_artifact
    from meds_model_contract.artifact_inputs import resolve_input

    data = tmp_path / "data"
    with measured_artifact(
        data, artifact_type="patients", command="preprocess_data", producer="test", payload_format="test/v1"
    ):
        pass
    model = tmp_path / "model"
    with measured_artifact(
        model,
        artifact_type="supervised_model",
        command="train_supervised",
        producer="test",
        payload_format="test/v1",
        inputs={"input_data_dir": {"path": str(data)}},
    ):
        pass
    assert resolve_input(model, "input_data_dir") == data.resolve()
    with pytest.raises(ValueError, match="not an artifact input"):
        resolve_input(model, "input_embeddings_dir")


def test_rendered_spec_points_to_core_and_contract_is_not_copied(multi):
    from meds_model_contract import CommandName
    from meds_model_core.contracts.commands import CommandName as CoreCommandName

    assert CommandName is CoreCommandName
    assert "meds-model-core-spec" in (multi / "SPEC.md").read_text()
    assert not (multi / "docs/SOFTWARE_CONTRACT.md").exists()
