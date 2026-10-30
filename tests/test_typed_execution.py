"""A rendered implementation trains and predicts via its real CLI in separate processes."""

import os
import subprocess
import sys
from datetime import datetime

import polars as pl
import pytest
from test_render import render


def test_rendered_algorithm_runs_persisted_lifecycle_with_structured_config(tmp_path):
    dst = tmp_path / "algorithm"
    slug = render(dst, "supervised")
    package = dst / "src" / slug
    (package / "config.py").write_text("""from dataclasses import dataclass
from meds_algorithm import AlgorithmConfig

@dataclass(frozen=True)
class V2SupervisedConfig(AlgorithmConfig):
    smoothing: float = 1.0

    def validate(self):
        if self.smoothing < 0:
            raise ValueError("smoothing must be nonnegative")
""")
    # Simulate the algorithm author's implementation, retaining the generated CLI and repository factory.
    source = package / f"{slug}.py"
    source.write_text(
        source.read_text()
        + """
import polars as pl

class CompletedAlgorithm(V2Supervised):
    def preprocess_data(self, request):
        import yaml
        assert set(yaml.safe_load(request.predicates_file.read_text())["predicates"]) == {"base", "extra"}
        (request.output.directory / "payload.txt").write_text("prepared")
        return PayloadMetadata("fixture-data")

    def train_supervised(self, request):
        outcomes = request.labels.read()["boolean_value"]
        alpha = self.config.smoothing
        probability = (outcomes.sum() + alpha) / (len(outcomes) + 2 * alpha)
        (request.output.directory / "probability.txt").write_text(str(probability))
        return PayloadMetadata("fixture-algorithm")

    def predict_supervised(self, request):
        probability = float((request.fitted_algorithm.directory / "probability.txt").read_text())
        request.index.read().with_columns(
            pl.lit(probability).alias("predicted_boolean_probability")
        ).write_parquet(request.output.directory / "predictions.parquet")
        return PayloadMetadata("fixture-predictions")

IMPLEMENTATIONS["supervised"] = CompletedAlgorithm
"""
    )
    inputs = tmp_path / "meds"
    inputs.mkdir()
    labels = tmp_path / "labels"
    labels.mkdir()
    for split, ids, values in (("train", [1, 2, 3], [True, True, False]), ("held_out", [4], [False])):
        pl.DataFrame(
            {"subject_id": ids, "prediction_time": [datetime(2020, 1, 1)] * len(ids), "boolean_value": values}
        ).write_parquet(labels / f"{split}.parquet")
    config = tmp_path / "config.yaml"
    config.write_text("smoothing: 2.0\nadditional_predicates_file: extra.yaml\n")
    extra = tmp_path / "extra.yaml"
    extra.write_text("predicates:\n  extra: {code: EXTRA}\n")
    base = tmp_path / "base.yaml"
    base.write_text("predicates:\n  base: {code: BASE}\n")
    artifacts = tmp_path / "artifacts"

    def run(step, **arguments):
        return subprocess.run(
            [
                sys.executable,
                "-m",
                slug,
                step,
                f"config_file={config}",
                *(f"{key}={value}" for key, value in arguments.items()),
            ],
            cwd=dst,
            env={**os.environ, "PYTHONPATH": str(dst / "src")},
            text=True,
            capture_output=True,
        )

    data, algorithm, predictions = (artifacts / name for name in ("data", "algorithm", "predictions"))
    result = run(
        "preprocess_data", external_meds_dir=inputs, external_predicates_file=base, output_data_dir=data
    )
    assert result.returncode == 0, result.stderr
    assert (data / "resolved_feature_predicates.yaml").is_file()
    extra.unlink()  # Later CLI processes need only the persisted feature artifacts.
    result = run(
        "train_supervised",
        input_data_dir=data,
        external_labels_dir=labels,
        output_supervised_algorithm_dir=algorithm,
    )
    assert result.returncode == 0, result.stderr
    args = {
        "input_data_dir": data,
        "input_supervised_algorithm_dir": algorithm,
        "external_index_dir": labels,
        "splits": "[held_out]",
        "output_predictions_dir": predictions,
        "external_evaluation_labels_dir": labels,
    }
    result = run("predict_supervised", **args)
    assert result.returncode == 0, result.stderr
    frame = pl.read_parquet(predictions / "predictions.parquet")
    assert frame["predicted_boolean_probability"].to_list() == pytest.approx([4 / 7])
    assert frame["boolean_value"].to_list() == [False]
    from meds_algorithm import read_manifest

    assert read_manifest(algorithm)["algorithm"]["config"] == {
        "smoothing": 2.0,
        "additional_predicates_file": str(extra.resolve()),
    }
    assert (algorithm / "config.json").is_file() and (predictions / "request.json").is_file()
    config.write_text("smoothing: 3.0\nadditional_predicates_file: extra.yaml\n")
    mismatch = run("predict_supervised", **{**args, "output_predictions_dir": artifacts / "bad"})
    assert mismatch.returncode != 0 and "configuration mismatch" in mismatch.stderr
    assert not (artifacts / "bad").exists()
