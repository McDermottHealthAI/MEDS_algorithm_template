"""Contract-level tests for the minimal MEDS model Copier template."""

from __future__ import annotations

import compileall
import importlib.util
import os
import subprocess
import sys
import types
from datetime import datetime
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
TEMPLATE_REPO = REPO

MODEL_PROFILES = {
    "supervised": ["preprocess_data", "supervised_train", "predict"],
    "finetune": ["preprocess_data", "pretrain", "supervised_train", "predict"],
    "probe": ["preprocess_data", "pretrain", "infer", "supervised_train", "predict"],
    "zero_shot_direct": ["preprocess_data", "pretrain", "predict"],
    "zero_shot_materialized": ["preprocess_data", "pretrain", "infer", "predict"],
    "packaged": ["preprocess_data", "predict"],
}


def render(dst: Path, profile: str, *, uses_predicates: bool = False) -> str:
    from copier import run_copy

    slug = f"v2_{profile}"
    run_copy(
        str(TEMPLATE_REPO),
        str(dst),
        data={
            "model_name": f"V2 {profile}",
            "model_slug": slug,
            "profile": profile,
            "uses_predicates": uses_predicates,
        },
        defaults=True,
        unsafe=True,
        quiet=True,
    )
    return slug


def load_integration_module(rendered: Path):
    path = rendered / "tests" / "integration.py"
    spec = importlib.util.spec_from_file_location(f"rendered_integration_{id(rendered)}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("profile", MODEL_PROFILES)
def test_renders_six_model_profiles(tmp_path, profile):
    dst = tmp_path / profile
    slug = render(dst, profile, uses_predicates=True)
    required = [
        "model.yaml",
        ".copier-answers.yml",
        "AGENTS.md",
        "SPEC.md",
        "IMPLEMENTATION_REPORT.md",
        "docs/IMPLEMENTATION_GUIDE.md",
        "requirements.txt",
        "slurm/config.sh",
        "slurm/job.sbatch",
        "slurm/submit.sh",
        "scripts/github-sync.sh",
        "tests/test_end_to_end.py",
        "tests/test_primary_behavior.py",
        "tests/signal.py",
        "tests/test_meds_dev_e2e.py",
        "tests/test_mimic_demo_e2e.py",
        "tests/e2e.py",
        "src/meds_model_contract/contract.py",
        "src/meds_model_contract/manifest.py",
        f"src/{slug}/commands.py",
    ]
    assert all((dst / path).is_file() for path in required)
    assert compileall.compile_dir(dst, quiet=1, force=True)
    assert yaml.safe_load((dst / "model.yaml").read_text())["commands"]["supervised"]["predict"]
    assert "{predicates_path}" in (dst / "model.yaml").read_text()

    env = {**os.environ, "PYTHONPATH": str(dst / "src")}
    command_list = subprocess.run(
        ["python", "-m", slug, "commands"], env=env, text=True, capture_output=True, check=True
    ).stdout.splitlines()
    assert command_list == MODEL_PROFILES[profile]

    syntax = subprocess.run(
        ["bash", "-n", "slurm/config.sh", "slurm/job.sbatch", "slurm/submit.sh", "scripts/github-sync.sh"],
        cwd=dst,
        text=True,
        capture_output=True,
    )
    assert syntax.returncode == 0, syntax.stderr


def test_copier_answers_record_portable_update_metadata(tmp_path):
    dst = tmp_path / "answers"
    render(dst, "supervised")
    answers = yaml.safe_load((dst / ".copier-answers.yml").read_text())
    assert answers["_src_path"]
    assert answers["model_slug"] == "v2_supervised"
    assert answers["profile"] == "supervised"


def test_mimic_task_prepends_pinned_meds_dev_venv_only_for_task(tmp_path, monkeypatch):
    dst = tmp_path / "mimic-path"
    render(dst, "supervised")
    calls = []

    integration = types.ModuleType("rendered_tests.integration")
    integration.RUN_TIMEOUT = 123
    integration.venv_bin = lambda checkout: checkout / ".venv" / "bin"
    integration.run = lambda command, **kwargs: calls.append(([str(value) for value in command], kwargs))
    package = types.ModuleType("rendered_tests")
    package.__path__ = [str(dst / "tests")]
    monkeypatch.setitem(sys.modules, "rendered_tests", package)
    monkeypatch.setitem(sys.modules, "rendered_tests.integration", integration)

    path = dst / "tests" / "e2e.py"
    spec = importlib.util.spec_from_file_location("rendered_tests.e2e", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    meds_dev = tmp_path / "MEDS-DEV"
    monkeypatch.delenv("MEDS_DEMO_DIR", raising=False)
    monkeypatch.setenv("PATH", "/ambient/bin")
    module.prepare_mimic_demo(meds_dev, tmp_path)

    assert len(calls) == 2
    dataset_command, dataset_kwargs = calls[0]
    task_command, task_kwargs = calls[1]
    assert dataset_command[0] == str(meds_dev / ".venv/bin/meds-dev-dataset")
    assert "env" not in dataset_kwargs
    assert task_command[0] == str(meds_dev / ".venv/bin/meds-dev-task")
    assert task_kwargs["env"]["PATH"] == f"{meds_dev / '.venv/bin'}{os.pathsep}/ambient/bin"


def test_example_signal_dataset_has_no_length_or_position_leak(tmp_path):
    import polars as pl

    dst = tmp_path / "signal-example"
    render(dst, "supervised")
    path = dst / "tests" / "signal.py"
    spec = importlib.util.spec_from_file_location("rendered_signal", path)
    signal = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(signal)

    root = signal.build_signal_dataset(tmp_path / "cohort", n_train=40, n_tuning=10, n_held_out=10)
    events = pl.scan_parquet(root / "data" / "*" / "*.parquet").collect()
    labels = pl.concat(
        [pl.read_parquet(path) for path in sorted((root / "task_labels/signal_task").glob("*.parquet"))]
    )
    observed = events.group_by("subject_id").agg(
        pl.len().alias("length"),
        (pl.col("code") == signal.SIGNAL_CODE).any().alias("has_signal"),
    )
    checked = labels.join(observed, on="subject_id")
    assert checked["boolean_value"].to_list() == checked["has_signal"].to_list()
    assert checked["length"].min() >= 5
    assert checked["length"].max() <= 10
    assert checked.filter(pl.col("boolean_value")).height > 0
    assert checked.filter(~pl.col("boolean_value")).height > 0


def test_primary_behavior_is_a_required_failing_placeholder(tmp_path):
    dst = tmp_path / "primary-behavior"
    render(dst, "supervised")
    test = (dst / "tests/test_primary_behavior.py").read_text()
    assert "pytest.fail" in test
    assert "shuffled-label negative control" in test
    assert "selected codes, vocabulary, predicates, or derived features" in test


def test_predicates_are_external_not_a_rendered_semantic_format(tmp_path):
    dst = tmp_path / "without-predicates"
    render(dst, "supervised", uses_predicates=False)
    assert not (dst / "semantics.yaml").exists()
    assert "external_predicates_file" not in (dst / "model.yaml").read_text()


def test_implementation_prompt_belongs_to_template_readme_not_rendered_repo(tmp_path):
    dst = tmp_path / "prompt-location"
    render(dst, "supervised")
    prompt_token = "<PAPER_PATH_OR_URL_AND_OR_REPOSITORY_PATH_OR_URL>"
    assert prompt_token in (TEMPLATE_REPO / "README.md").read_text()
    assert prompt_token not in (dst / "README.md").read_text()
    assert "Copyable model-implementation prompt" not in (dst / "README.md").read_text()


def test_spec_has_one_template_source_and_renders_to_root(tmp_path):
    dst = tmp_path / "single-spec"
    render(dst, "supervised")
    assert not (TEMPLATE_REPO / "SPEC.md").exists()
    assert (dst / "SPEC.md").read_text() == (TEMPLATE_REPO / "template" / "SPEC.md").read_text()


@pytest.mark.parametrize(
    ("prediction_rows", "error"),
    [
        ([(2, "2020-01-02"), (1, "2020-01-01")], None),
        ([(1, "2020-01-01")], "missing"),
        ([(1, "2020-01-01"), (2, "2020-01-02"), (3, "2020-01-03")], "extra"),
        ([(1, "2020-01-01"), (1, "2020-01-01"), (2, "2020-01-02")], "duplicate"),
    ],
)
def test_prediction_keys_are_compared_directly(tmp_path, prediction_rows, error):
    import polars as pl

    dst = tmp_path / "key-validation"
    render(dst, "supervised")
    integration = load_integration_module(dst)
    labels = tmp_path / "labels" / "held_out"
    predictions = tmp_path / "predictions"
    labels.mkdir(parents=True)
    predictions.mkdir()

    def frame(rows):
        return pl.DataFrame(
            {
                "subject_id": [row[0] for row in rows],
                "prediction_time": [row[1] for row in rows],
            }
        ).with_columns(pl.col("prediction_time").str.to_datetime())

    frame([(1, "2020-01-01"), (2, "2020-01-02")]).write_parquet(labels / "part.parquet")
    frame(prediction_rows).write_parquet(predictions / "predictions.parquet")
    if error is None:
        integration.assert_prediction_keys(predictions, labels.parent, ["held_out"])
    else:
        with pytest.raises(AssertionError, match=error):
            integration.assert_prediction_keys(predictions, labels.parent, ["held_out"])


def test_meds_dev_predicates_capability_is_explicit(tmp_path):
    dst = tmp_path / "capability"
    render(dst, "supervised")
    integration = load_integration_module(dst)
    checkout = tmp_path / "MEDS-DEV"
    config = checkout / "src/MEDS_DEV/configs/_run_model.yaml"
    implementation = checkout / "src/MEDS_DEV/models/__init__.py"
    config.parent.mkdir(parents=True)
    implementation.parent.mkdir(parents=True)
    config.write_text("predicates_path: null\n")
    implementation.write_text('format_kwargs["predicates_path"] = str(cfg.predicates_path)\n')
    integration.assert_meds_dev_predicates_capability(checkout)
    implementation.write_text("format_kwargs = {}\n")
    with pytest.raises(AssertionError, match="PR #325"):
        integration.assert_meds_dev_predicates_capability(checkout)

    with pytest.raises(AssertionError, match="PR #330"):
        integration.assert_meds_dev_task_criteria_capability(checkout)
    implementation.write_text('format_kwargs["task_criteria_path"] = str(task_criteria_path)\n')
    integration.assert_meds_dev_task_criteria_capability(checkout)


@pytest.mark.parametrize("profile", MODEL_PROFILES)
def test_only_zero_shot_meds_dev_runs_require_task_criteria(tmp_path, profile):
    dst = tmp_path / profile
    render(dst, profile)
    meds_dev_test = (dst / "tests/test_meds_dev_e2e.py").read_text()
    assert ("task_criteria=True" in meds_dev_test) == (profile in ZERO_SHOT_PROFILES)


def test_meds_dev_ref_is_checked_out_in_clone(tmp_path, monkeypatch):
    dst = tmp_path / "provisioning"
    render(dst, "supervised")
    integration = load_integration_module(dst)
    commands = []

    class Request:
        class Config:
            @staticmethod
            def getoption(name, default=""):
                assert name == "markexpr"
                return "meds_dev"

        config = Config()

    class TempPathFactory:
        @staticmethod
        def mktemp(name):
            assert name == "meds-dev"
            path = tmp_path / name
            path.mkdir()
            return path

    def fake_run(command, **kwargs):
        command = [str(value) for value in command]
        commands.append(command)
        if command[1] == "clone":
            checkout = Path(command[-1])
            config = checkout / "src/MEDS_DEV/configs/_run_model.yaml"
            implementation = checkout / "src/MEDS_DEV/models/__init__.py"
            config.parent.mkdir(parents=True)
            implementation.parent.mkdir(parents=True)
            config.write_text("predicates_path: null\n")
            implementation.write_text('format_kwargs["predicates_path"] = str(cfg.predicates_path)\n')

    monkeypatch.delenv("MEDS_DEV_DIR", raising=False)
    monkeypatch.setenv("MEDS_DEV_REF", "test-predicates-ref")
    monkeypatch.setattr(integration.shutil, "which", lambda command: f"/usr/bin/{command}")
    monkeypatch.setattr(integration, "run", fake_run)
    checkout = integration.provision_meds_dev(Request(), TempPathFactory())
    assert [
        "/usr/bin/git",
        "-C",
        str(checkout),
        "checkout",
        "--detach",
        "test-predicates-ref",
    ] in commands


def test_measurement_manifest_is_plausible(tmp_path, monkeypatch):
    dst = tmp_path / "measurement"
    render(dst, "packaged")
    monkeypatch.syspath_prepend(str(dst / "src"))
    from meds_model_contract import measured_artifact, read_manifest, write_run_result
    from meds_model_contract.meds_dev import register

    artifact = tmp_path / "artifact"
    with measured_artifact(
        artifact,
        artifact_type="patients",
        command="preprocess_data",
        producer="test",
        payload_format="test/v1",
    ) as staging:
        (staging / "payload.txt").write_text("ok")
    manifest = read_manifest(artifact)
    assert manifest["resources"]["wall_seconds"] >= 0
    memory = manifest["resources"]["memory"]
    assert memory["peak_process_tree_rss_bytes"] > 0
    if memory["source"] == "linux_proc_smaps_rollup":
        assert memory["peak_process_tree_pss_bytes"] > 0
        assert memory["includes_descendants"] is True
    assert manifest["resources"]["gpu"]["peak_allocated_bytes"] is None
    assert "semantics_digest" in manifest
    assert manifest["semantics_digest"] is None

    run_dir = tmp_path / "run"
    result = write_run_result(
        run_dir,
        repo=dst,
        artifacts={"preprocess_data": artifact},
        dataset={"name": "synthetic", "subjects": 1, "events": 1},
        task={"name": "smoke", "timepoints": 1},
    )
    assert result.is_file()
    assert (run_dir / "spec.yaml").is_file()
    assert (run_dir / "manifests/preprocess_data.yaml").is_file()

    meds_dev = tmp_path / "MEDS-DEV"
    (meds_dev / "src/MEDS_DEV/models").mkdir(parents=True)
    registered = register(dst, meds_dev, "measurement-model")
    assert (registered / "model.yaml").is_file()
    assert str(dst.resolve()) in (registered / "requirements.txt").read_text()


ZERO_SHOT_PROFILES = ["zero_shot_direct", "zero_shot_materialized"]


@pytest.mark.parametrize("profile", MODEL_PROFILES)
def test_only_zero_shot_profiles_receive_the_task(tmp_path, profile):
    dst = tmp_path / profile
    render(dst, profile)
    model_yaml = (dst / "model.yaml").read_text()
    predict = yaml.safe_load(model_yaml)["commands"]["supervised"]["predict"]
    slurm = (dst / "slurm/config.sh").read_text()
    end_to_end = (dst / "tests/test_end_to_end.py").read_text()
    if profile in ZERO_SHOT_PROFILES:
        assert "external_task_criteria_file={task_criteria_path}" in predict
        assert "TASK_CRITERIA_FILE" in slurm
        guide = (dst / "docs/IMPLEMENTATION_GUIDE.md").read_text()
        assert "Zero-shot: task in, probabilities out" in guide
        assert "test_zero_shot_artifacts_name_their_task_and_relaxations" in end_to_end
        predict_line = next(line for line in slurm.splitlines() if line.strip().startswith("predict)"))
        assert "TASK_CRITERIA_FILE" in predict_line
        if profile == "zero_shot_materialized":
            # Materialized futures are task-independent: infer never sees the task, predict applies it.
            assert "generate futures" in guide
            assert "class ZeroShotTranslator(ABC)" not in guide
            assert "input_inference_subdir=inference/default" in predict_line
            assert "input_pretrained_model_dir" not in predict_line
            infer_line = next(line for line in slurm.splitlines() if line.strip().startswith("infer)"))
            assert "TASK_CRITERIA_FILE" not in infer_line
            infer = predict.splitlines()[0]
            assert infer.startswith("meds-model infer")
            assert "task_criteria_path" not in infer, "materialized infer is task-independent"
            assert "splits=[{split}]" in infer, "materialized infer must score only the evaluated split"
        else:
            assert "class ZeroShotTranslator(ABC)" in guide, (
                "the translator shape is guidance, kept in the guide"
            )
            assert "input_pretrained_model_dir" in predict_line
        assert "flipped" not in end_to_end
    else:
        assert "task_criteria_path" not in model_yaml
        assert "TASK_CRITERIA_FILE" not in slurm
        assert "zero_shot" not in end_to_end


@pytest.mark.parametrize("profile", ZERO_SHOT_PROFILES)
def test_zero_shot_stub_rejects_a_missing_task_before_work(tmp_path, profile):
    dst = tmp_path / profile
    slug = render(dst, profile)
    env = {**os.environ, "PYTHONPATH": str(dst / "src")}
    output = tmp_path / "predictions"
    command = ["python", "-m", slug, "predict", f"output_predictions_dir={output}"]
    missing = subprocess.run(command, env=env, text=True, capture_output=True)
    assert missing.returncode != 0
    assert "external_task_criteria_file" in missing.stderr
    assert not output.exists()

    criteria = tmp_path / "task.yaml"
    criteria.write_text("predicates: {}\n")
    stub = subprocess.run(
        [*command, f"external_task_criteria_file={criteria}"], env=env, text=True, capture_output=True
    )
    assert "NotImplementedError" in stub.stderr, "a valid task reaches the model-owned body"


def test_task_spec_ledger_and_label_blind_index(tmp_path, monkeypatch):
    import polars as pl

    dst = tmp_path / "task-contract"
    render(dst, "zero_shot_direct")
    monkeypatch.syspath_prepend(str(dst / "src"))
    import meds_model_contract
    from meds_model_contract import RelaxationLedger, TaskSpec, check_decoded, read_index

    assert not hasattr(meds_model_contract, "ZeroShotTranslator"), "the translator is guidance, not contract"
    assert {
        name: {c.value for c in cs} for name, cs in meds_model_contract.ZERO_SHOT_TASK_COMMANDS.items()
    } == {
        "zero_shot_direct": {"predict"},
        "zero_shot_materialized": {"predict"},
    }, "only predict sees the task; materialized infer is task-independent"

    criteria = tmp_path / "task.yaml"
    criteria.write_text("trigger: admission\n")
    mimic, other = tmp_path / "mimic.yaml", tmp_path / "other.yaml"
    mimic.write_text("admission: {code: ADM}\n")
    other.write_text("admission: {code: ADMIT}\n")
    with pytest.raises(ValueError, match="external_task_criteria_file"):
        TaskSpec.from_arguments({})
    with pytest.raises(FileNotFoundError):
        TaskSpec(tmp_path / "missing.yaml")
    bound = TaskSpec.from_arguments(
        {"external_task_criteria_file": str(criteria), "external_predicates_file": str(mimic)}
    )
    digests = {TaskSpec(criteria).semantics_digest(), bound.semantics_digest()}
    digests.add(TaskSpec(criteria, other).semantics_digest())
    assert len(digests) == 3, "the digest must change with the criteria or the predicates bound to them"
    assert bound.semantics_digest() == TaskSpec(criteria, mimic).semantics_digest()
    assert bound.provenance()["predicates_file"]["digest"].startswith("sha256:")

    held_out = tmp_path / "labels" / "held_out"
    held_out.mkdir(parents=True)
    times = [datetime(2020, 1, 1), datetime(2020, 1, 2)]
    labels = pl.DataFrame({"subject_id": [1, 2], "prediction_time": times, "boolean_value": [True, False]})
    labels.write_parquet(held_out / "0.parquet")
    pl.DataFrame({"subject_id": [3], "prediction_time": times[:1], "boolean_value": [True]}).write_parquet(
        tmp_path / "labels" / "train.parquet"
    )
    index = read_index(tmp_path / "labels", ["held_out"])
    assert index.columns == ["subject_id", "prediction_time"]
    assert sorted(index["subject_id"]) == [1, 2]

    ledger = RelaxationLedger(
        query_language="test",
        decoded_quantity="P(death within 30d)",
        exact=False,
        steps=(
            {"name": "normalize", "kind": "label_preserving", "direction": "exact"},
            {"name": "label_only", "detail": "dropped 1 criteria branch"},  # step keys are free-form
        ),
    )
    ledger.write(tmp_path)
    assert RelaxationLedger.read(tmp_path) == ledger
    assert yaml.safe_load((tmp_path / "relaxations.yaml").read_text())["exact"] is False
    assert RelaxationLedger.read(tmp_path).steps[1] == {
        "name": "label_only",
        "detail": "dropped 1 criteria branch",
    }

    exact = tmp_path / "exact"
    exact.mkdir()
    (exact / "relaxations.yaml").write_text(
        "query_language: trajectories\ndecoded_quantity: P(y)\nexact: true\n"
    )
    assert RelaxationLedger.read(exact).steps == ()
    (exact / "relaxations.yaml").write_text("query_language: trajectories\nexact: true\n")
    with pytest.raises(ValueError, match="decoded_quantity"):
        RelaxationLedger.read(exact)
    with pytest.raises(ValueError, match="exact"):
        RelaxationLedger(query_language="q", decoded_quantity="d", exact="yes")

    predictions = index.with_columns(pl.Series("predicted_boolean_probability", [0.2, 0.9]))
    assert check_decoded(index, predictions.reverse()).height == 2
    with pytest.raises(ValueError, match="miss 1"):
        check_decoded(index, predictions.head(1))
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        check_decoded(index, predictions.with_columns(pl.lit(1.5).alias("predicted_boolean_probability")))
