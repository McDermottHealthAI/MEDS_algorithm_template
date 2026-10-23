"""Model-owned profile adapters plus shared MEDS-DEV MIMIC demo provisioning."""

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class E2EResult:
    """Artifacts plus the requested evaluation index used to verify prediction keys."""

    artifacts: Mapping[str, Path]
    labels_dir: Path
    splits: Sequence[str]
    # The external inputs passed to the commands. Zero-shot profiles MUST include external_task_criteria_file
    # (and external_predicates_file when used) so tests can check which task each artifact answers.
    inputs: Mapping[str, Any] = field(default_factory=dict)
    # The exact arguments the run passed to `predict`. The label-blindness check reruns `predict` with them
    # on an index whose label columns are removed.
    predict_arguments: Mapping[str, Any] | None = None
    # The codes `tests.signal.add_split_canaries` placed in tuning and held-out subjects of the fixture.
    canaries: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MEDSDevRun:
    """MEDS-DEV invocation plus the evaluation index its predictions must cover."""

    args: Sequence[str]
    predictions_dir: Path
    labels_dir: Path
    splits: Sequence[str]


def run_e2e(tmp_path, **inputs):
    """Run the selected profile; any ``external_*`` input given here overrides the local fixture's."""
    raise NotImplementedError(
        "Prepare a small MEDS input/task, execute the selected model profile's real commands, and return "
        "E2EResult(artifacts, labels_dir, evaluated splits, external inputs used, predict_arguments, "
        "canaries from tests.signal.add_split_canaries applied to the fixture)."
    )


def fitted_codes(artifacts: Mapping[str, Path]) -> set[str]:
    """Return every code the model fitted a population statistic for: its vocabulary, frequency tables,
    selected features, or bins.

    The transductive-fitting check requires the split canaries to be absent from this set (SPEC section
    2.1). Read it from the model's own artifacts; the payload formats are model-owned.
    """
    raise NotImplementedError("Report the codes the model fitted, read from its artifacts")


def prepare_meds_dev_run(meds_dev, tmp_path):
    """Return ``MEDSDevRun(args, predictions_dir, labels_dir, splits)`` for this implementation."""
    raise NotImplementedError("Configure the selected model profile's real MEDS-DEV run")


def prepare_mimic_demo(meds_dev, tmp_path):
    """Return MEDS-DEV's ``(MIMIC demo, task labels, MIMIC predicates)`` paths.

    Use ``MEDS_DEMO_DIR`` when set; otherwise invoke MEDS-DEV's own demo builder. Pin an existing
    demo-compatible MEDS-DEV task rather than defining a task in this repository.
    """
    from .integration import RUN_TIMEOUT, run, venv_bin

    configured = os.environ.get("MEDS_DEMO_DIR")
    dataset_dir = Path(configured).resolve() if configured else tmp_path / "mimic-iv-demo"
    if not configured:
        run(
            [
                venv_bin(meds_dev) / "meds-dev-dataset",
                "dataset=MIMIC-IV",
                f"output_dir={dataset_dir}",
                "demo=true",
            ],
            timeout=RUN_TIMEOUT,
        )
    labels_dir = tmp_path / "mortality-in-icu-first-24h"
    run(
        [
            venv_bin(meds_dev) / "meds-dev-task",
            "task=mortality/in_icu/first_24h",
            "dataset=MIMIC-IV",
            f"dataset_dir={dataset_dir}",
            f"output_dir={labels_dir}",
        ],
        # MEDS-DEV's task runner launches venv-installed helpers by bare name.
        # Prepend the pinned checkout so an ambient MEDS-DEV install cannot win.
        env={"PATH": f"{venv_bin(meds_dev)}{os.pathsep}{os.environ['PATH']}"},
        timeout=RUN_TIMEOUT,
    )
    predicates_file = meds_dev / "src" / "MEDS_DEV" / "datasets" / "MIMIC-IV" / "predicates.yaml"
    return dataset_dir, labels_dir, predicates_file


def mimic_task_criteria(meds_dev) -> Path:
    """MEDS-DEV's own ACES criteria for the demo task: what a zero-shot model is asked to predict."""
    return meds_dev / "src" / "MEDS_DEV" / "tasks" / "mortality" / "in_icu" / "first_24h.yaml"
