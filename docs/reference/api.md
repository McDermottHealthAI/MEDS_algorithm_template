# Contract API

Every generated repository ships the `meds_model_contract` package. It is backend-neutral: its runtime
dependency is PyYAML, and functions that read parquet import Polars lazily.

## Profiles and commands

```python
from meds_model_contract import (
    MODEL_PROFILES, ZERO_SHOT_TASK_COMMANDS, CommandName, ArtifactType, Command, ModelRepository,
)
```

| Name | What it is |
|---|---|
| `CommandName` | the command vocabulary: `preprocess_data`, `pretrain`, `infer`, `supervised_train`, `predict` |
| `ArtifactType` | `patients`, `pretrained_model`, `inference`, `supervised_model`, `predictions` |
| `MODEL_PROFILES` | profile name → commands in dependency order (see [Choosing a profile](../profiles.md)) |
| `ZERO_SHOT_TASK_COMMANDS` | zero-shot profile → commands that receive the task; `predict` in both profiles |
| `Command` | base class of a model-owned command: implement `run(arguments) -> Path` and return the published artifact directory |
| `ModelRepository(profile, commands)` | validates that a repository registers exactly its profile's commands, and dispatches `run(name, arguments)` |

## Publishing artifacts

```python
from meds_model_contract import digest_config, measured_artifact, read_manifest

with measured_artifact(
    output_dir,
    artifact_type="predictions",
    command="predict",
    producer="my_model.commands.Predict",
    payload_format="my-model-predictions/v1",
    config_digest=digest_config({**arguments, **resolved_settings}),
    inputs={...},                      # optional extra input identifiers
    semantics_digest=task.semantics_digest(),   # zero-shot task-conditioned artifacts
    external_predicates_file=predicates_path,   # recorded with its digest
    overwrite=do_overwrite,
) as staging:
    ...  # write the payload into `staging`
```

`measured_artifact` creates a staging directory next to the destination, samples memory while the block
runs, writes `manifest.yaml` last, and then replaces the destination atomically. If the block raises,
the staging directory is removed and nothing is published. Without `overwrite`, an existing destination
is an error. `digest_config(config)` hashes canonical JSON (sorted keys, paths as strings), so the same
configuration always gives the same digest. `read_manifest(directory)` loads and validates a manifest (it
must declare `contract_version: "2"`).

## Tasks and predictions

```python
from meds_model_contract import TaskSpec, read_index, RelaxationLedger, check_decoded, attach_ground_truth
```

| Name | Use |
|---|---|
| `TaskSpec(criteria_file, predicates_file=None, name=None)` | the task specification; both files must exist |
| `TaskSpec.from_arguments(arguments)` | reads `external_task_criteria_file` and `external_predicates_file`; raises if the criteria are missing, so a zero-shot command fails before doing work |
| `TaskSpec.semantics_digest()` | `sha256:` over the criteria bytes and the predicates bytes |
| `TaskSpec.provenance()` | `{name, criteria_file: {path, digest}, predicates_file: {path, digest} or null}` for the manifest's `inputs.task` |
| `read_index(labels_dir, splits=None)` | the requested keys `(subject_id, prediction_time)` with **no label column**. Raises if a requested split has no files (it never falls back to every split), if `splits` is a bare string, or if keys are duplicated |
| `RelaxationLedger(query_language, decoded_quantity, exact, steps=())` | the zero-shot ledger. `.write(dir)` writes `relaxations.yaml`; `.read(dir)` validates the three required fields. `steps` are free-form mappings |
| `check_decoded(index, predictions)` | checks `predicted_boolean_probability` by key: no missing, extra or duplicate keys, and every value a non-null probability in [0, 1] |
| `attach_ground_truth(predictions, labels_dir, splits=None)` | joins `boolean_value` onto **final** predictions by key, for meds-evaluation; the one sanctioned label read on the prediction path |

## Run results and MEDS-DEV

| Name | Use |
|---|---|
| `write_run_result(run_dir, *, repo, artifacts, dataset, task, external_predicates_file=None, status="complete")` | writes `spec.yaml`, `result.yaml` and copies of every manifest for `scripts/github-sync.sh` |
| `meds_model_contract.meds_dev.register(repo, meds_dev, name)` / `meds-model-add-to-meds-dev` | copies `model.yaml` (and `predicates.yaml` if present) into a MEDS-DEV checkout, rewriting `requirements.txt` to install this repository |

## Test hooks in a generated repository

These live in the generated `tests/` package, not in `meds_model_contract`; the model owns their bodies.

| Name | Use |
|---|---|
| `tests.e2e.run_e2e(tmp_path, **inputs)` | runs the real profile and returns `E2EResult(artifacts, labels_dir, splits, inputs, predict_arguments, canaries)` |
| `tests.e2e.fitted_codes(artifacts)` | every code the model fitted a population statistic for, read from its artifacts |
| `tests.e2e.prepare_meds_dev_run(meds_dev, tmp_path)` | the MEDS-DEV invocation and the index its predictions must cover |
| `tests.signal.add_split_canaries(root)` | gives every tuning and held-out subject of a fixture a canary code found in no other split; returns the canaries |
| `tests.integration.assert_prediction_keys` / `assert_prediction_schema` | compare written keys with the requested index (every parquet in the predictions artifact counts), and validate the meds-evaluation schema |

