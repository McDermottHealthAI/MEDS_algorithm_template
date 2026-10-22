# Contract API

The [normative software interfaces](spec.md#9-software-interfaces) define the public classes, arguments,
label-access rules and artifact compatibility requirements. Import them directly from `meds_model_core`.
There is no generated compatibility package.

| Module | Responsibility |
|---|---|
| `contracts.commands` | Profile registry, step metadata and dispatch |
| `artifacts` | Manifests, publication with rollback, upstream references and run results |
| `runtime` | Explicit model provenance, memory measurement and subprocess execution |
| `data` | Strict split selection, key-only index reads and permitted context targets |
| `tasks.spec` | Task identity and relaxation ledgers |
| `evaluation.predictions` | Keyed probabilities and post-score truth attachment |
| `integrations.meds_dev` | Per-profile registration |
| `conformance` | Reusable assertions, synthetic fixtures and explicitly selected integration tests |

Pass the model checkout as `repo=` to `measured_artifact`; unavailable provenance is recorded as null.
Use explicit `splits` for outcome attachment. Install the `data` extra for dataframe helpers and the
`conformance` extra for shared tests. The base package does not import data or model frameworks.

`meds-model-core-spec` prints the installed specification. `meds-model-resolve-input <artifact>
<input_argument>` resolves a recorded upstream path and checks its envelope type; the consumer still
validates scientific compatibility. Core also supplies `meds-model-add-to-meds-dev`.

Model-owned adapters remain `run_e2e(tmp_path, *, profile, **inputs)`, `fitted_codes(artifacts)`, and
`prepare_meds_dev_run(meds_dev, tmp_path, *, profile)`. The shared lifecycle check reruns the selected
profile with evaluated labels removed and fresh outputs; adapters must honor those input overrides.
