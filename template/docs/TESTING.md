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

## Shared acceptance suite and local adapters

`tests/test_conformance.py` inherits eight acceptance checks from
`meds_algorithm.conformance.suite.AlgorithmConformanceTests`. Their implementation and
[what/why inventory](https://mcdermotthealthai.github.io/MEDS_algorithm_template/reference/tests/#downstream-acceptance-suite)
live in the shared package. The matching installed inventory is available in Python through
`meds_algorithm.spec.validation_guide()`.

`tests/conftest.py` supplies an `AlgorithmCase` fixture and a `profile` fixture parametrized from
`create_repository().profiles`. Supply representative concrete configurations, including required
constructor arguments. Reuse `profile` in local scientific tests. There is no second profile list
in the test wiring and no automatically loaded pytest plugin.

`tests/e2e.py` remains algorithm-owned: implement `run_e2e`, `fitted_codes` and
`prepare_meds_dev_run`. Honor external input overrides and read fitted features from saved artifacts.
Keep the shared acceptance methods inherited rather than overriding them to suppress failures.
Updating the pinned `meds-algorithm[conformance]` dependency updates their checks without regenerating
this repository; rerun acceptance after every such update.

`tests/test_primary_behavior.py::test_primary_behavior` remains a required failing placeholder.
Replace it with positive-signal and shuffled-label control runs of the real algorithm, proving that
the signal reaches its actual features. It runs for every registered profile, including stubs.
Structural conformance cannot establish scientific behavior or fidelity to a paper.

## Algorithm-specific tests to add

Add source-backed tests for numerical behavior, temporal cutoffs, feature selection, frozen pretrained
weights where applicable, payload compatibility, configuration effects and fresh-process reconstruction.
Neural configuration tests should prove that capacity, learning rate, batch size, weight decay and dropout
control the intended code. The generated config round-trip test alone does not prove that.

Keep a short what/why entry here for each added scientific test. Report exact pass/skip counts and
explain remaining skips. Completing another profile must not mask missing evidence in an existing one.
