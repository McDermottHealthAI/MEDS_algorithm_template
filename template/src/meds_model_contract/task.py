"""The zero-shot task boundary: task specification, label-blind index, translator, and relaxation ledger.

A supervised model learns *what* to predict from labels. A zero-shot model is never shown labels, so the
task definition itself must cross the contract boundary. The overall task language is ACES: a task is an
ACES criteria file plus, optionally, a dataset predicates file. A zero-shot model answers it in three
model-owned steps:

1. ``encode``: task + label-blind index -> an inference target in the model's own query language,
   together with the relaxations that reduction required;
2. ``infer``: inference target + MEDS data + pretrained model -> raw model outputs;
3. ``decode``: raw outputs -> one predicted probability per requested ``(subject_id, prediction_time)``.

The payloads of all three steps are implementation-defined. The contract fixes only the inputs (task,
index, MEDS data), the final predictions, the semantics digest that ties every artifact to the exact task
it answers, and the machine-readable ledger of how the answered task differs from the requested one.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    import polars as pl

INDEX_COLUMNS = ("subject_id", "prediction_time")
RELAXATIONS_FILENAME = "relaxations.yaml"
PREDICTED_PROBABILITY = "predicted_boolean_probability"


def _digest_file(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


@dataclass(frozen=True)
class TaskSpec:
    """A task in the overall task language: an ACES criteria file and its optional predicates file."""

    criteria_file: Path
    predicates_file: Path | None = None
    name: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "criteria_file", Path(self.criteria_file))
        if self.predicates_file is not None:
            object.__setattr__(self, "predicates_file", Path(self.predicates_file))
        for path in (self.criteria_file, self.predicates_file):
            if path is not None and not path.is_file():
                raise FileNotFoundError(f"Task file {path} does not exist")

    @classmethod
    def from_arguments(cls, arguments: Mapping[str, Any]) -> TaskSpec:
        """Read the standard ``external_task_criteria_file`` / ``external_predicates_file`` arguments."""
        criteria = arguments.get("external_task_criteria_file")
        if not criteria:
            raise ValueError(
                "zero-shot commands require external_task_criteria_file=<ACES task YAML>; without it the "
                "model cannot know what to predict"
            )
        return cls(
            criteria_file=criteria,
            predicates_file=arguments.get("external_predicates_file") or None,
            name=arguments.get("task_name") or None,
        )

    def semantics_digest(self) -> str:
        """A digest of exactly what was asked: the criteria bytes and the predicates bytes.

        Artifacts may be combined only when their semantics digests agree. The digest changes when either
        file changes, including when the same criteria are bound to another dataset's predicates.
        """
        digest = hashlib.sha256()
        for label, path in (("criteria", self.criteria_file), ("predicates", self.predicates_file)):
            digest.update(label.encode())
            digest.update(b"\0" if path is None else hashlib.sha256(path.read_bytes()).digest())
        return f"sha256:{digest.hexdigest()}"

    def provenance(self) -> dict[str, Any]:
        """The manifest ``inputs`` entry recording which task was answered."""

        def entry(path: Path | None) -> dict[str, str] | None:
            return None if path is None else {"path": str(path.resolve()), "digest": _digest_file(path)}

        return {
            "name": self.name,
            "criteria_file": entry(self.criteria_file),
            "predicates_file": entry(self.predicates_file),
        }


def read_index(labels_dir: Path | str, splits: Sequence[str] | None = None) -> pl.DataFrame:
    """Read the requested evaluation index with every label column removed.

    Zero-shot code MUST obtain its rows through this function (or an equivalent that never selects a label
    column), so label blindness is a property of the boundary rather than of reviewer attention.
    """
    import polars as pl

    root = Path(labels_dir)
    files = sorted(root.rglob("*.parquet")) if root.is_dir() else [root]
    if splits and root.is_dir():
        selected = set(splits)
        matching = [
            path
            for path in files
            if path.stem in selected or any(part in selected for part in path.relative_to(root).parts)
        ]
        files = matching or files
    frames = [
        pl.read_parquet(path, columns=list(INDEX_COLUMNS))
        for path in files
        if all(column in pl.read_parquet_schema(path) for column in INDEX_COLUMNS)
    ]
    if not frames:
        raise FileNotFoundError(f"No parquet files with {list(INDEX_COLUMNS)} under {root}")
    index = pl.concat(frames)
    if index.unique().height != index.height:
        raise ValueError("the requested evaluation index contains duplicate (subject_id, prediction_time)")
    return index


class RelaxationKind(StrEnum):
    """Where a difference between the requested and the answered task comes from."""

    label_preserving = "label_preserving"  # a rewrite that changes no label on extracted rows
    approximation = "approximation"  # a task rewrite that changes labels in a stated direction
    model_assumption = "model_assumption"  # an assumption the model's query language forces


class RelaxationDirection(StrEnum):
    exact = "exact"
    weakening = "weakening"  # the answered task accepts a superset of the requested positives
    strengthening = "strengthening"  # the answered task accepts a subset of the requested positives
    unknown = "unknown"  # the direction depends on the data distribution


@dataclass(frozen=True)
class Relaxation:
    """One step between the requested ACES task and the quantity the model actually returns."""

    name: str
    kind: RelaxationKind
    direction: RelaxationDirection
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", RelaxationKind(self.kind))
        object.__setattr__(self, "direction", RelaxationDirection(self.direction))
        if self.kind is RelaxationKind.label_preserving and self.direction is not RelaxationDirection.exact:
            raise ValueError(f"label-preserving relaxation {self.name!r} must be exact")


@dataclass(frozen=True)
class RelaxationLedger:
    """The machine-readable record of what a zero-shot prediction actually estimates."""

    query_language: str
    decoded_quantity: str
    relaxations: Sequence[Relaxation] = field(default_factory=tuple)

    @property
    def is_exact(self) -> bool:
        return all(r.direction is RelaxationDirection.exact for r in self.relaxations)

    def write(self, directory: Path | str) -> Path:
        path = Path(directory) / RELAXATIONS_FILENAME
        value = {
            "query_language": self.query_language,
            "decoded_quantity": self.decoded_quantity,
            "exact": self.is_exact,
            "relaxations": [
                {**asdict(r), "kind": r.kind.value, "direction": r.direction.value} for r in self.relaxations
            ],
        }
        path.write_text(yaml.safe_dump(value, sort_keys=False))
        return path

    @classmethod
    def read(cls, directory: Path | str) -> RelaxationLedger:
        path = Path(directory) / RELAXATIONS_FILENAME
        if not path.is_file():
            raise FileNotFoundError(f"{directory} has no {RELAXATIONS_FILENAME}")
        value = yaml.safe_load(path.read_text())
        return cls(
            query_language=value["query_language"],
            decoded_quantity=value["decoded_quantity"],
            relaxations=tuple(Relaxation(**r) for r in value["relaxations"]),
        )


class ZeroShotTranslator(ABC):
    """The model-owned encode / infer / decode triple behind a zero-shot ``predict``.

    ``zero_shot_direct`` runs all three inside ``predict``. ``zero_shot_materialized`` runs ``encode`` and
    ``infer`` in the ``infer`` command, publishing the encoded target and raw outputs as the inference
    artifact, and runs ``decode`` in ``predict``. Either way the encoded target and its relaxation ledger
    are published, and every task-conditioned artifact carries ``TaskSpec.semantics_digest()``.
    """

    @abstractmethod
    def encode(
        self, task: TaskSpec, index: pl.DataFrame, model_dir: Path, output_dir: Path
    ) -> RelaxationLedger:
        """Write the model's inference target for ``task`` over ``index`` into ``output_dir``.

        ``index`` has exactly ``subject_id`` and ``prediction_time``. Return the ledger of every rewrite or
        assumption the reduction into the model's query language required; the caller writes it. Raise
        rather than silently degrade when the task cannot be posed (for example, it is not future-only).
        """

    @abstractmethod
    def infer(self, encoded_dir: Path, data_dir: Path, model_dir: Path, output_dir: Path) -> None:
        """Run the model on the encoded target and write its raw outputs into ``output_dir``."""

    @abstractmethod
    def decode(self, encoded_dir: Path, inference_dir: Path, index: pl.DataFrame) -> pl.DataFrame:
        """Return ``index`` with ``predicted_boolean_probability`` for every row, joined by key."""


def check_decoded(index: pl.DataFrame, predictions: pl.DataFrame) -> pl.DataFrame:
    """Validate decoded predictions against the requested index by key, never by row order."""
    if PREDICTED_PROBABILITY not in predictions.columns:
        raise ValueError(f"decoded predictions lack {PREDICTED_PROBABILITY}")
    keys = list(INDEX_COLUMNS)
    if predictions.select(keys).unique().height != predictions.height:
        raise ValueError("decoded predictions contain duplicate keys")
    missing = index.select(keys).join(predictions.select(keys), on=keys, how="anti")
    extra = predictions.select(keys).join(index.select(keys), on=keys, how="anti")
    if missing.height or extra.height:
        raise ValueError(f"decoded predictions miss {missing.height} and add {extra.height} requested keys")
    probabilities = predictions[PREDICTED_PROBABILITY]
    if probabilities.null_count() or not probabilities.is_between(0.0, 1.0).all():
        raise ValueError(f"{PREDICTED_PROBABILITY} must be a non-null probability in [0, 1]")
    return predictions
