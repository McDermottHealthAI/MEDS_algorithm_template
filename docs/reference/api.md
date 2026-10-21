# Contract API

The [normative software interfaces](spec.md#9-software-interfaces) define the public classes, per-step
arguments, label-access rules and artifact compatibility requirements. The implementation of profiles
and step metadata lives once in `meds_model_core.contracts.commands`; the template's
`meds_model_contract.contract` is a compatibility import.

`meds_model_core.data.index.read_index` projects `(subject_id, prediction_time)` when reading Parquet.
`split_files` rejects missing requested splits, including ambiguous single-file inputs. Neither function
grants permission to read outcome values. Install the core's optional `data` extra to use them.

`meds-model-core-spec` prints the normative specification from the installed core wheel.
`meds-model-resolve-input <artifact> <input_argument>` exposes a producer's recorded upstream path as
an explicit orchestration argument. It checks the upstream envelope type, not scientific compatibility.

The remaining manifest, task, result and MEDS-DEV helpers are still in the template during staged
extraction. The [core package layout](../core-package.md) records what is implemented and what remains.
Model-owned adapters keep `run_e2e(tmp_path, *, profile, **inputs)` and
`prepare_meds_dev_run(meds_dev, tmp_path, *, profile)`.
