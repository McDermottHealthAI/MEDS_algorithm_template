# Tests in an algorithm repository

This guide explains the acceptance tests generated with every algorithm repository. It is independent
of the shared package's unit tests and of the template's rendering tests. Algorithms must implement their
own scientific checks; generic contract checks cannot prove fidelity to a paper or clinical validity.

## Running and interpreting tests

```bash
uv sync --extra test
uv run pytest -rs
uv run pytest -m meds_dev -rs
uv run pytest -m real_data -rs
```

The default run does not authorize or provision clinical data or cluster work. `meds_dev` explicitly opts
in to the isolated MEDS-DEV integration; `real_data` opts in to the MIMIC-IV demo. Follow the approval gates
in the implementation guide before the demo or a full-data run. Marked integration fixtures can skip if
not explicitly selected. Every `algorithm_stub` skip identifies unfinished implementation, not success.
The primary-behavior placeholder intentionally **fails**, including in a freshly generated repository.

## Acceptance inventory

| File and test | What it checks | Why it exists |
|---|---|---|
| `test_contract.py::test_profile_implementations_match_contract` | Compares each registered profile's commands with the core lifecycle. | Detect incorrect profile registration or dispatch wiring. |
| `test_contract.py::test_algorithm_configuration_roundtrips` | Saves and reloads the concrete config. | Preserve exact settings across independent processes; extend with algorithm-specific invalid-value tests. |
| `test_end_to_end.py::test_end_to_end` | Runs the algorithm-owned adapter for every profile and shared lifecycle checks, including fresh outputs and label-blind reruns. | Verify persisted artifacts, prediction coverage and permitted label use through the whole pipeline. |
| `test_primary_behavior.py::test_primary_behavior` | Starts as a required failure; replace it with real positive-signal execution and a shuffled-label negative control, proving that the signal reaches actual algorithm features. | Require evidence of the algorithm's intended scientific behavior rather than only valid output files. |
| `test_report.py::test_completed_algorithm_has_a_completed_report` | Validates implementation-report evidence for completed profiles. | Keep completion claims tied to source-fidelity and validation evidence. |
| `test_operations.py::test_algorithm_yaml_is_a_meds_dev_descriptor` | Checks each profile descriptor's required structure. | Catch packaging errors before launching an integration run. |
| `test_operations.py::test_slurm_dry_run_is_non_mutating` | Runs each profile's launcher in dry-run mode and checks files and listed commands. | Make execution plans inspectable without submitting a job or modifying the repository. |
| `test_meds_dev_e2e.py::test_meds_dev_runs_algorithm_yaml` | Registers each completed profile, executes it through MEDS-DEV, and checks output schema, keys, manifest and memory evidence. | Prove the declared descriptor works in the isolated integration environment. Requires explicit `meds_dev` selection. |
| `test_mimic_demo_e2e.py::test_full_dag_on_mimic_iv_demo` | Executes each completed profile on the prepared MIMIC-IV demo task and checks prediction schema/keys, artifacts and recorded evidence. | Exercise the complete real-data boundary before a full dataset. Requires explicit `real_data` selection and the implementation-guide approval gate. |

Tests with a `profile` parameter run for every declared profile. `tests/e2e.py` supplies algorithm-owned
adapters, not additional pytest tests: it defines how to run the implementation and inspect fitted
features. Implement these adapters instead of modifying shared checks to accommodate an error.

## Algorithm-specific tests to add

Add source-backed tests for numerical behavior, temporal cutoffs, feature selection, frozen pretrained
weights where applicable, payload compatibility, configuration effects and fresh-process reconstruction.
Neural configuration tests should prove that capacity, learning rate, batch size, weight decay and dropout
control the intended code. The generated config round-trip test alone does not prove that.

Keep a short what/why entry here for each added scientific test. Report exact pass/skip counts and
explain remaining skips. Completing another profile must not mask missing evidence in an existing one.
