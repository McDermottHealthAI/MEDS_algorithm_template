"""Contract-level tests for the minimal MEDS model Copier template."""

from __future__ import annotations

import compileall
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
TEMPLATE_REPO = REPO

MODEL_PROFILES = {
    "supervised": ["preprocess_data", "train_supervised", "predict_supervised"],
    "finetune": ["preprocess_data", "pretrain", "train_finetune", "predict_finetune"],
    "probe": ["preprocess_data", "pretrain", "infer_embeddings", "train_probe", "predict_probe"],
    "zero_shot_direct": ["preprocess_data", "pretrain", "predict_zero_shot_direct"],
    "zero_shot_materialized": [
        "preprocess_data",
        "pretrain",
        "infer_trajectories",
        "predict_zero_shot_materialized",
    ],
    "predict_only": ["preprocess_data", "predict_only"],
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
            "profiles": [profile],
            "uses_predicates": uses_predicates,
        },
        defaults=True,
        unsafe=True,
        quiet=True,
    )
    return slug


def load_integration_module(rendered: Path):
    from meds_model_core.conformance import meds_dev

    return meds_dev


@pytest.mark.parametrize("profile", MODEL_PROFILES)
def test_renders_six_model_profiles(tmp_path, profile):
    dst = tmp_path / profile
    slug = render(dst, profile, uses_predicates=True)
    required = [
        f"models/{profile}/model.yaml",
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
        "tests/test_meds_dev_e2e.py",
        "tests/test_mimic_demo_e2e.py",
        "tests/e2e.py",
        f"src/{slug}/commands.py",
    ]
    assert all((dst / path).is_file() for path in required)
    assert not (dst / "src/meds_model_contract").exists()
    assert not (dst / "src/meds_model_core").exists()
    assert compileall.compile_dir(dst, quiet=1, force=True)
    assert yaml.safe_load((dst / "models" / profile / "model.yaml").read_text())["commands"]["supervised"][
        "predict"
    ]
    assert "{predicates_path}" in (dst / "models" / profile / "model.yaml").read_text()

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
    assert answers["profiles"] == ["supervised"]


def test_mimic_task_prepends_pinned_meds_dev_venv_only_for_task(tmp_path, monkeypatch):
    dst = tmp_path / "mimic-path"
    render(dst, "supervised")
    calls = []

    from meds_model_core.conformance import meds_dev as module

    monkeypatch.setattr(module, "venv_bin", lambda checkout: checkout / ".venv" / "bin")
    monkeypatch.setattr(
        module, "run", lambda command, **kwargs: calls.append(([str(v) for v in command], kwargs))
    )
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
    from meds_model_core.conformance import signal

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
    assert "external_predicates_file" not in (dst / "models/supervised/model.yaml").read_text()


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
    frame(prediction_rows).with_columns(pl.lit(0.5).alias("predicted_boolean_probability")).write_parquet(
        predictions / "predictions.parquet"
    )
    # A zero-shot query bundle next to the predictions is fine in a non-parquet format.
    (predictions / "bundle").mkdir()
    frame([(1, "2020-01-01"), (2, "2020-01-02")]).write_ipc(predictions / "bundle" / "index.arrow")
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
    render(dst, "predict_only")
    monkeypatch.syspath_prepend(str(dst / "src"))
    from meds_model_core import measured_artifact, read_manifest, write_run_result
    from meds_model_core.integrations.meds_dev import register

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
        profile="predict_only",
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
    model_yaml = (dst / "models" / profile / "model.yaml").read_text()
    predict = yaml.safe_load(model_yaml)["commands"]["supervised"]["predict"]
    slurm = (dst / "slurm/config.sh").read_text()
    end_to_end = (
        Path(__import__("meds_model_core.conformance.end_to_end", fromlist=["__file__"]).__file__)
    ).read_text()
    if profile in ZERO_SHOT_PROFILES:
        assert "external_task_criteria_file={task_criteria_path}" in predict
        assert "TASK_CRITERIA_FILE" in slurm
        guide = (dst / "docs/IMPLEMENTATION_GUIDE.md").read_text()
        assert "Zero-shot: task in, probabilities out" in guide
        assert "ZERO_SHOT_TASK_COMMANDS" in end_to_end and "RelaxationLedger.read" in end_to_end
        predict_line = next(
            line for line in slurm.splitlines() if line.strip().startswith(MODEL_PROFILES[profile][-1] + ")")
        )
        assert "TASK_CRITERIA_FILE" in predict_line
        if profile == "zero_shot_materialized":
            # Materialized futures are task-independent: infer never sees the task, predict applies it.
            assert "generate futures" in guide
            assert "class ZeroShotTranslator(ABC)" not in guide
            assert "input_trajectories_dir=$RUN_DIR/trajectories" in predict_line
            assert "input_pretrained_model_dir" not in predict_line
            infer_line = next(
                line for line in slurm.splitlines() if line.strip().startswith("infer_trajectories)")
            )
            assert "TASK_CRITERIA_FILE" not in infer_line
            infer = predict.splitlines()[0]
            assert infer.startswith("meds-model infer_trajectories --profile zero_shot_materialized")
            assert "task_criteria_path" not in infer, "materialized infer is task-independent"
            assert "splits=[{split}]" in infer, "materialized infer must score only the evaluated split"
            materialized_predict = predict.splitlines()[1]
            assert "external_meds_dir={dataset_dir}" in materialized_predict, (
                "the task is evaluated on real history"
            )
            assert "external_meds_dir=" in predict_line
        else:
            assert "class ZeroShotTranslator(ABC)" in guide, (
                "the translator shape is guidance, kept in the guide"
            )
            assert "input_pretrained_model_dir" in predict_line
        assert "flipped" not in end_to_end
    else:
        assert "task_criteria_path" not in model_yaml
        assert "TASK_CRITERIA_FILE" not in slurm
        assert 'if not profile.startswith("zero_shot_"):' in end_to_end


@pytest.mark.parametrize("profile", ZERO_SHOT_PROFILES)
def test_zero_shot_stub_rejects_a_missing_task_before_work(tmp_path, profile):
    dst = tmp_path / profile
    slug = render(dst, profile)
    env = {**os.environ, "PYTHONPATH": str(dst / "src")}
    output = tmp_path / "predictions"
    from meds_model_core import STEP_SPECS

    step = MODEL_PROFILES[profile][-1]
    spec = STEP_SPECS[step]
    command = [
        "python",
        "-m",
        slug,
        step,
        f"output_predictions_dir={output}",
        "splits=[held_out]",
    ]
    command.extend(f"{item.argument}=/missing/{item.argument}" for item in spec.artifact_inputs)
    command.extend(
        f"{name}=/missing/{name}" for name in spec.external_arguments if name != "external_task_criteria_file"
    )
    missing = subprocess.run(command, env=env, text=True, capture_output=True)
    assert missing.returncode != 0
    assert "external_task_criteria_file" in missing.stderr
    assert not output.exists()

    criteria = tmp_path / "task.yaml"
    criteria.write_text("predicates: {}\n")
    stub = subprocess.run(
        [*command, f"external_task_criteria_file={criteria}"], env=env, text=True, capture_output=True
    )
    assert stub.returncode != 0 and "/missing/" in stub.stderr
    assert "NotImplementedError" not in stub.stderr, "invalid inputs must not reach model code"


def test_task_spec_ledger_and_label_blind_index(tmp_path, monkeypatch):
    import polars as pl

    dst = tmp_path / "task-contract"
    render(dst, "zero_shot_direct")
    monkeypatch.syspath_prepend(str(dst / "src"))
    import meds_model_core
    from meds_model_core import RelaxationLedger, TaskSpec, attach_ground_truth, check_decoded, read_index

    assert not hasattr(meds_model_core, "ZeroShotTranslator"), "the translator is guidance, not contract"
    assert {name: {c.value for c in cs} for name, cs in meds_model_core.ZERO_SHOT_TASK_COMMANDS.items()} == {
        "zero_shot_direct": {"predict_zero_shot_direct"},
        "zero_shot_materialized": {"predict_zero_shot_materialized"},
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
    with pytest.raises(FileNotFoundError, match="tuning"):
        read_index(tmp_path / "labels", ["tuning"])  # never silently falls back to every split
    with pytest.raises(TypeError):
        read_index(tmp_path / "labels", "held_out")
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

    final = attach_ground_truth(predictions.reverse(), tmp_path / "labels", ["held_out"])
    assert dict(zip(final["subject_id"], final["boolean_value"], strict=True)) == {1: True, 2: False}
    assert final["predicted_boolean_probability"].to_list() == [0.9, 0.2], "probabilities are untouched"


@pytest.mark.parametrize("profile", MODEL_PROFILES)
def test_predictions_and_cli_lists_follow_meds_dev(tmp_path, profile):
    dst = tmp_path / profile
    slug = render(dst, profile)
    predict = yaml.safe_load((dst / "models" / profile / "model.yaml").read_text())["commands"]["supervised"][
        "predict"
    ]
    assert "output_predictions_dir={output_dir}/predictions" in predict, "never replace MEDS-DEV's output_dir"
    probe = (
        f"import sys; sys.argv = ['x']; from {slug}.__main__ import _value; "
        "print(_value('[held_out]'), _value('[train, tuning]'), _value('[]'), _value('3'), _value('a'))"
    )
    env = {**os.environ, "PYTHONPATH": str(dst / "src")}
    printed = subprocess.run(["python", "-c", probe], env=env, text=True, capture_output=True, check=True)
    assert printed.stdout.split("\n")[0] == "['held_out'] ['train', 'tuning'] [] 3 a"


def test_meds_dev_evaluates_every_parquet_under_predictions(tmp_path):
    import polars as pl

    dst = tmp_path / "glob"
    render(dst, "zero_shot_direct")
    integration = load_integration_module(dst)
    labels, predictions = tmp_path / "labels" / "held_out", tmp_path / "predictions"
    labels.mkdir(parents=True)
    (predictions / "bundle").mkdir(parents=True)
    keys = pl.DataFrame({"subject_id": [1], "prediction_time": [datetime(2020, 1, 1)]})
    keys.write_parquet(labels / "0.parquet")
    keys.with_columns(pl.lit(0.5).alias("predicted_boolean_probability")).write_parquet(
        predictions / "predictions.parquet"
    )
    keys.write_parquet(predictions / "bundle" / "index.parquet")
    with pytest.raises(AssertionError, match="MEDS-DEV evaluates every parquet"):
        integration.assert_prediction_keys(predictions, labels.parent, ["held_out"])


@pytest.mark.parametrize("profile", MODEL_PROFILES)
def test_artifacts_are_siblings_and_slurm_lists_only_profile_commands(tmp_path, profile):
    dst = tmp_path / profile
    render(dst, profile)
    model_yaml = (dst / "models" / profile / "model.yaml").read_text()
    assert "output_inference_subdir" not in model_yaml and "input_inference_subdir" not in model_yaml
    if profile in ("probe", "zero_shot_materialized"):
        kind = "embeddings" if profile == "probe" else "trajectories"
        assert f"output_{kind}_dir={{output_dir}}/{kind}" in model_yaml
    slurm = (dst / "slurm/config.sh").read_text()
    cases = {line.strip().split(")")[0] for line in slurm.splitlines() if line.strip().endswith(";;")} - {"*"}
    assert cases == set(MODEL_PROFILES[profile]), "the SLURM config lists exactly the profile's commands"
    commands = (dst / f"src/v2_{profile}/commands.py").read_text()
    assert "AlgorithmRepository" in commands


def test_contract_helpers_for_conformance_checks(tmp_path, monkeypatch):
    import polars as pl

    dst = tmp_path / "helpers"
    render(dst, "supervised")
    monkeypatch.syspath_prepend(str(dst / "src"))
    monkeypatch.syspath_prepend(str(dst))
    from meds_model_core import attach_ground_truth, digest_config
    from meds_model_core.conformance.signal import add_split_canaries, build_signal_dataset

    assert digest_config({"a": 1, "b": Path("/x")}) == digest_config({"b": "/x", "a": 1})
    assert digest_config({"a": 1}) != digest_config({"a": 2})

    unlabelled = tmp_path / "index"
    unlabelled.mkdir()
    keys = pl.DataFrame({"subject_id": [1], "prediction_time": [datetime(2020, 1, 1)]})
    keys.write_parquet(unlabelled / "held_out.parquet")
    predictions = keys.with_columns(pl.lit(0.5).alias("predicted_boolean_probability"))
    assert attach_ground_truth(predictions, unlabelled, ["held_out"]).equals(predictions), (
        "unlabelled index: unchanged"
    )

    root = build_signal_dataset(tmp_path / "meds", n_train=4, n_tuning=3, n_held_out=2)
    canaries = add_split_canaries(root)
    for split, rows in (("train", 0), ("tuning", 3), ("held_out", 2)):
        events = pl.read_parquet(root / "data" / split / "0.parquet")
        found = events.filter(pl.col("code").str.starts_with("CANARY//"))
        assert found.height == rows and found["subject_id"].n_unique() == rows
        if rows:
            assert set(found["code"]) == {canaries[split]}
            assert events.schema == pl.read_parquet(root / "data" / "train" / "0.parquet").schema
    assert "CANARY//tuning" not in set(pl.read_parquet(root / "metadata" / "codes.parquet")["code"])


def test_predict_only_reads_context_labels_never_evaluated_ones(tmp_path, monkeypatch):
    import polars as pl

    dst = tmp_path / "predict_only"
    render(dst, "predict_only")
    guide = (dst / "docs/IMPLEMENTATION_GUIDE.md").read_text()
    assert "In-context learners" in guide and "read_context_labels" in guide
    monkeypatch.syspath_prepend(str(dst / "src"))
    from meds_model_core import read_context_labels, split_files

    labels = tmp_path / "labels"
    for split, subject in (("train", 1), ("tuning", 2), ("held_out", 3)):
        (labels / split).mkdir(parents=True)
        pl.DataFrame(
            {"subject_id": [subject], "prediction_time": [datetime(2020, 1, 1)], "boolean_value": [True]}
        ).write_parquet(labels / split / "0.parquet")
    assert [p.parent.name for p in split_files(labels, ["held_out"])] == ["held_out"]
    context = read_context_labels(labels, ["train", "tuning"], ["held_out"])
    assert sorted(context["subject_id"]) == [1, 2] and "boolean_value" in context.columns
    with pytest.raises(ValueError, match="disjoint"):
        read_context_labels(labels, ["train", "held_out"], ["held_out"])
    with pytest.raises(ValueError, match="nonempty"):
        read_context_labels(labels, [], ["held_out"])


@pytest.mark.parametrize("profile", MODEL_PROFILES)
def test_label_leakage_check_strips_what_the_profile_may_not_read(tmp_path, profile):
    dst = tmp_path / profile
    render(dst, profile)
    end_to_end = (
        Path(__import__("meds_model_core.conformance.end_to_end", fromlist=["__file__"]).__file__)
    ).read_text()
    assert 'None if profile.startswith("zero_shot_") else result.splits' in end_to_end


def _dry_run(dst: Path, slug: str, tmp_path: Path, **env: str) -> subprocess.CompletedProcess:
    shim = tmp_path / "bin" / "meds-model"
    shim.parent.mkdir(parents=True, exist_ok=True)
    shim.write_text(f'#!/bin/sh\nexec {sys.executable} -m {slug} "$@"\n')
    shim.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{shim.parent}{os.pathsep}{os.environ['PATH']}",
        "PYTHONPATH": str(dst / "src"),
        "MEDS_ROOT": "/meds",
        "LABELS_DIR": "/labels/task",
        "INDEX_DIR": "/index/task",
        "TASK_CRITERIA_FILE": "/tasks/task.yaml",
        "PREDICATES_FILE": "/predicates/dataset.yaml",
        **env,
    }
    return subprocess.run(
        ["bash", "slurm/submit.sh", "--dry-run"], cwd=dst, env=environment, text=True, capture_output=True
    )


def test_submit_stages_reuse_shared_task_independent_artifacts(tmp_path):
    dst = tmp_path / "materialized"
    slug = render(dst, "zero_shot_materialized", uses_predicates=True)
    result = _dry_run(
        dst,
        slug,
        tmp_path,
        STAGES="predict_zero_shot_materialized,infer_trajectories",
        RUN_ROOT="/runs",
        RUN_ID="task-a",
        SHARED_DIR="/runs/shared/artifacts",
        TASK_PREDICATES_FILE="/predicates/task-suite.yaml",
    )
    assert result.returncode == 0, result.stderr
    args = [line for line in result.stdout.splitlines() if line.startswith("# ")]
    assert [line.split(":")[0] for line in args if ": " in line] == ["# infer_trajectories"] * 5 + [
        "# predict_zero_shot_materialized"
    ] * 8
    assert "# infer_trajectories: input_pretrained_model_dir=/runs/shared/artifacts/pretrained" in args
    assert (
        "# infer_trajectories: output_trajectories_dir="
        "/runs/task-a/zero_shot_materialized/artifacts/trajectories" in args
    )
    assert (
        "# infer_trajectories: splits=[held_out]" in args
        and "# predict_zero_shot_materialized: splits=[held_out]" in args
    )
    assert "# predict_zero_shot_materialized: input_data_dir=/runs/shared/artifacts/data" in args
    assert "# predict_zero_shot_materialized: external_predicates_file=/predicates/task-suite.yaml" in args
    assert not any("preprocess_data" in line or "pretrain:" in line for line in args)

    shared = _dry_run(dst, slug, tmp_path, STAGES="preprocess_data", RUN_ROOT="/runs", RUN_ID="shared")
    assert "# preprocess_data: external_predicates_file=/predicates/dataset.yaml" in shared.stdout
    assert (
        "# preprocess_data: output_data_dir=/runs/shared/zero_shot_materialized/artifacts/data"
        in shared.stdout
    )

    typo = _dry_run(dst, slug, tmp_path, STAGES="infer,supervised_train")
    assert typo.returncode == 2 and "not a command of this profile" in typo.stderr


def test_submit_overrides_resources_args_and_sbatch_flags_from_the_environment(tmp_path):
    dst = tmp_path / "overrides"
    slug = render(dst, "zero_shot_materialized", uses_predicates=True)
    result = _dry_run(
        dst,
        slug,
        tmp_path,
        STAGES="infer_trajectories",
        MEMORY="96G",
        TIME_GPU="24:00:00",
        ARGS_infer_trajectories="n_trajectories=8 max_new_tokens=4096",
        SBATCH_EXTRA="--exclude=c0103,c0607",
    )
    assert result.returncode == 0, result.stderr
    assert "# infer_trajectories: n_trajectories=8" in result.stdout
    assert "# infer_trajectories: max_new_tokens=4096" in result.stdout
    sbatch = next(line for line in result.stdout.splitlines() if line.startswith("sbatch "))
    assert (
        "--mem=96G" in sbatch
        and "--time=24:00:00" in sbatch
        and "--exclude=c0103" in sbatch
        and "c0607" in sbatch
    )
    default = _dry_run(dst, slug, tmp_path, STAGES="infer_trajectories")
    assert "--mem=16G" in default.stdout and "--exclude" not in default.stdout
