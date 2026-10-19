"""The zero-shot task boundary: task specification, label-blind index, and relaxation ledger.

A supervised model learns *what* to predict from labels. A zero-shot model is never shown labels, so the
task definition itself must cross the contract boundary. The overall task language is ACES: a task is an
ACES criteria file plus, optionally, a dataset predicates file.

The contract fixes only the inputs (task, index, MEDS data), the final predictions, the semantics digest
that ties every artifact to the exact task it answers, and a minimal ledger of how the answered task
differs from the requested one. How a model turns the task into predictions is its own; the
implementation guide recommends an encode -> infer -> decode shape.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class RelaxationLedger:
    """What a zero-shot prediction actually estimates, written as ``relaxations.yaml``.

    Only ``query_language``, ``decoded_quantity``, and ``exact`` are required. ``steps`` is free-form: one
    mapping per rewrite or assumption between the requested and the answered task. The implementation
    guide recommends ``name``, ``kind``, ``direction``, and ``detail`` keys; the contract does not validate
    them. An exact model writes ``exact: true`` and no steps.
    """

    query_language: str
    decoded_quantity: str
    exact: bool
    steps: Sequence[Mapping[str, Any]] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in ("query_language", "decoded_quantity"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{RELAXATIONS_FILENAME} requires a non-empty {name}")
        if not isinstance(self.exact, bool):
            raise ValueError(f"{RELAXATIONS_FILENAME} requires exact: true or false")
        object.__setattr__(self, "steps", tuple(dict(step) for step in self.steps))

    def write(self, directory: Path | str) -> Path:
        path = Path(directory) / RELAXATIONS_FILENAME
        value = {
            "query_language": self.query_language,
            "decoded_quantity": self.decoded_quantity,
            "exact": self.exact,
            "steps": [dict(step) for step in self.steps],
        }
        path.write_text(yaml.safe_dump(value, sort_keys=False))
        return path

    @classmethod
    def read(cls, directory: Path | str) -> RelaxationLedger:
        path = Path(directory) / RELAXATIONS_FILENAME
        if not path.is_file():
            raise FileNotFoundError(f"{directory} has no {RELAXATIONS_FILENAME}")
        value = yaml.safe_load(path.read_text()) or {}
        missing = {"query_language", "decoded_quantity", "exact"} - set(value)
        if missing:
            raise ValueError(f"{path} lacks required fields {sorted(missing)}")
        return cls(
            query_language=value["query_language"],
            decoded_quantity=value["decoded_quantity"],
            exact=value["exact"],
            steps=value.get("steps") or (),
        )


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
