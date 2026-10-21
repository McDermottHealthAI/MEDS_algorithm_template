# Minimal MEDS model template

This repository is a self-contained [Copier](https://copier.readthedocs.io) template for minimal,
contract-first MEDS model repositories.

Shared contracts and the canonical specification live in
[`meds-model-core`](https://github.com/florian6973/meds-model-core). This template and generated projects pin commit
`bfa347d13270bd29899671974d819e3c6c6f7ba8` directly from Git, so no PyPI release is required.
The core README documents implemented modules and planned extractions.

The template fixes the external contract—MEDS input, six model profiles and standard arguments, typed
artifact manifests, final MEDS predictions, measurements, MEDS-DEV, SLURM, and GitHub result exchange—while
leaving preprocessing, featurization, intermediate formats, frameworks, batching, and model execution to
the generated repository.

## Documentation

This README is written for coding agents that port models. For a human-oriented explanation of the
contract (concepts, choosing a profile, zero-shot models, the gate workflow, running, and reference), read
the documentation site: https://florian6973.github.io/MEDS_model_template/ (built from `docs/` by
`.github/workflows/docs.yml`). Preview it locally with:

```bash
uv run --group docs mkdocs serve
```

## Render a repository

From the root of this checkout:

```bash
uv tool install copier
copier copy . ../my-meds-model
```

The rendered repository commits `.copier-answers.yml`, which records its template source, revision, and
answers. To bring later template changes into that repository, review its working tree and run:

```bash
cd ../my-meds-model
copier update --trust
```

For portable updates across machines, copy from the Git repository URL rather than from a local checkout;
Copier records that source in the answers file.

For a reproducible non-interactive render, first create `profiles.yml` containing
`profiles: [probe]` (or several profile names), then run:

```bash
copier copy --defaults --trust \
  --data model_name="My MEDS Model" \
  --data model_slug=my_meds_model \
  --data-file profiles.yml \
  --data uses_predicates=true \
  --data implementation_source=https://github.com/example/source-model \
  . ../my-meds-model
```

`--trust` is safe but currently unnecessary because the template defines no post-copy tasks. It is included
so the command remains usable if formatting/bootstrap tasks are added later.

### Copier questions

| Question | Meaning |
|---|---|
| `model_name` | Human-readable model name. |
| `model_slug` | Importable Python package and MEDS-DEV model identifier. |
| `profiles` | Nonempty list of supported profiles; each gets its own MEDS-DEV YAML. |
| `model_description` | Short description rendered into README and `models/<profile>/model.yaml`. |
| `author_name`, `author_email` | MEDS-DEV contact metadata. |
| `uses_predicates` | Whether generated MEDS-DEV commands pass `external_predicates_file`. The model still owns interpretation. |
| `implementation_source` | Paper path/URL, source repository path/URL, or both; prefilled into generated guidance and the report. |

Profiles are `supervised`, `finetune`, `probe`, `zero_shot_direct`, `zero_shot_materialized`, and
`predict_only`. A model profile selects required commands, not an architecture or execution backend.

The two zero-shot profiles also receive the task itself: an ACES criteria file passed as
`external_task_criteria_file` (`{task_criteria_path}` in `models/<profile>/model.yaml`). They must publish a
`relaxations.yaml` ledger stating how the answered task differs from the requested one. They differ in how
the model answers. `zero_shot_direct` models answer task-derived queries directly (MOTOR, EveryQuery),
recommended as an `aces-to-<model>` adapter on aces-relaxations. `zero_shot_materialized` models generate
futures in a task-independent `infer_trajectories`, and `predict_zero_shot_materialized` evaluates the task on them. See [`docs/ZERO_SHOT.md`](docs/ZERO_SHOT.md) for the design, the MOTOR mapping, and the MEDS-DEV
passthrough this needs.

## Work in the generated repository

```bash
cd ../my-meds-model
uv sync --extra test
uv run meds-model commands
uv run pytest -rs
```

The generated commands are intentional stubs. Before implementation, the local, MEDS-DEV, and MIMIC
end-to-end tests report explicit `model_stub` skips. Start with these rendered files:

1. `AGENTS.md`
2. `SPEC.md`
3. `README.md`
4. `docs/IMPLEMENTATION_GUIDE.md`
5. `src/<model_slug>/commands.py`
6. `tests/e2e.py`
7. `IMPLEMENTATION_REPORT.md`

A completed implementation removes each profile from `STUB_PROFILES` only after that profile works.

## Copyable model-implementation prompt

Use this after rendering a repository. Replace all placeholders before sending it to a coding agent.
The full-data evaluation may target any suitable MEDS dataset (for example, MIMIC-IV or NWICU); the
provided `real_data` test remains the MIMIC-IV demo smoke test.

```text
Based on the following source:

<PAPER_PATH_OR_URL_AND_OR_REPOSITORY_PATH_OR_URL>

implement the model in the generated MEDS model repository at:

<GENERATED_REPOSITORY_PATH>

For the full-data run, target this dataset in MEDS format (name, revision, and location):

<TARGET_DATASET_NAME_REVISION_AND_MEDS_PATH>

Use this dataset-specific shared task bundle if already available:

<FULL_DATA_WORK_DIR_OR_NOT_YET_AVAILABLE>

Read AGENTS.md, SPEC.md, README.md, and docs/IMPLEMENTATION_GUIDE.md in the generated repository
completely before writing code. Inspect the paper, supplementary material, source repository,
configuration files, checkpoints, preprocessing code, and evaluation code available from the supplied
source.

Preserve the selected model profile and standardized command arguments, MEDS input boundary, artifact
manifest envelopes, MEDS-DEV model.yaml interface, and final MEDS prediction output. Intermediate payload
formats and execution mechanisms are model-owned: choose whatever preprocessing, featurization, framework,
batching or non-batching strategy, external executable, storage format, and model architecture most
faithfully reproduce the source.

When predicates are needed, reuse MEDS-DEV predicates for the selected dataset if available; otherwise,
use reviewed external predicates for that dataset and record their provenance. Decide within the model
how those predicates become inputs. Validate dataset-specific codes, units, task definitions, and label mappings;
do not assume MIMIC mappings apply to another dataset. Keep such mappings in dataset-specific
configuration or model-owned code. Do not introduce a generic predicate-derived feature representation
into the contract package. Keep the provided MIMIC-IV demo code, task, and MEDS-DEV predicates as the
canonical smoke test, regardless of the full-data target.

For a zero_shot_direct model (answers queries directly, e.g. MOTOR, EveryQuery) or a zero_shot_materialized
model (generates futures and evaluates the task on them; infer is task-independent and only predict
receives the task): the model receives the original ACES task through
external_task_criteria_file (with the dataset predicates) and the upstream-built index through
external_index_dir. Never build, filter, or extend the cohort, and read the index only through
meds_model_contract.read_index. Reuse an existing aces-to-<model> adapter for this model if one exists;
otherwise write one on aces-relaxations, pinned to an exact version: reject tasks that are not future-only
or are degenerate, normalize, then apply only the approximations and assumptions the model's query
language forces. Publish relaxations.yaml with every step, and report per task whether the answer is exact.
A materialized model evaluates the task on generated futures instead and needs no relaxation beyond
sampling. Follow the shape for the selected profile in docs/IMPLEMENTATION_GUIDE.md.
Do not omit source behavior because it is inconvenient for a fixture; adapt the implementation or fixture
instead.

Record every material source element as ported, adapted, or omitted, with evidence and justification, in
IMPLEMENTATION_REPORT.md. Implement every registered command, finalize the implementation-specific
command strings in model.yaml, and implement tests/e2e.py. Keep STUB_PROFILES = set(PROFILES) until the actual selected
model profile completes and produces standards-conformant predictions.

Then run:

    uv run pytest -rs
    uv run pytest -m meds_dev -rs

Complete the pre-demo sections of IMPLEMENTATION_REPORT.md and ask for human review of source fidelity,
predicate interpretation, and the proposed MIMIC-IV demo execution. Only after approval, run:

    uv run pytest -m real_data -rs

There must be zero model_stub skips. Report exact pass/skip counts and account for every remaining skip.
Update IMPLEMENTATION_REPORT.md with the demo cohort, final-output coverage, predicate provenance,
environment, wall time, peak process-tree PSS/RSS, GPU measurements when available, failures, and fixes.
Ask for a second human review before launching the selected full dataset through the repository's SLURM
interface. Review target-dataset compatibility, access, and resources separately from the MIMIC-IV demo.
Use a shared, reviewed task bundle for the target dataset, built once upstream: clinical tasks defined in
ACES and extracted with the ACES package, or randomly sampled code-by-horizon tasks (generated with
https://github.com/florian6973/meds-random-task-sampler and selected with https://github.com/florian6973/meds-task-selection).
It must contain each task's definition and its generated index/labels; zero-shot models also need each
task's ACES criteria. If a compatible bundle is not yet available, report that blocker before the
full-data run. Record the dataset name/revision, predicate provenance, bundle location, the commit of the
tool that built it, and a digest of its task definitions. Keep the bundle external to Git. Commit and push the implementation,
configuration, and report-so-far; run the cluster job from that exact clean commit. After the authorized
run, complete the report with full-data evidence, scientific deviations, and known limitations, then
synchronize structured results through the GitHub workflow. Treat
docs/IMPLEMENTATION_GUIDE.md as the authority for the ordered gates and their evidence.
```

## Test tiers in a generated repository

```bash
uv run pytest -rs
uv run pytest -m meds_dev -rs
uv run pytest -m real_data -rs
```

- The default suite checks the contract and model-owned local end-to-end adapter.
- `meds_dev` registers `models/<profile>/model.yaml` and runs it in MEDS-DEV's isolated environment.
- `real_data` builds or reuses the MEDS MIMIC-IV demo, extracts MEDS-DEV task
  `mortality/in_icu/first_24h`, reuses MEDS-DEV's MIMIC predicates, and runs the full selected model profile.

The implementation guide defines what follows these commands: a report/review gate after the demo, then
an explicitly authorized run on the selected full dataset and final report. The demo's required task is
ICU mortality; additional MEDS-DEV MIMIC-supported tasks are optional coverage checks, not a mandatory
task benchmark.
The full-data evaluation instead uses a separately reviewed, shared task bundle for the target dataset
(clinical ACES tasks or randomly sampled code-by-horizon tasks), so model comparisons on that dataset use
the same task definitions and labels. Selecting another full dataset does not change the provided MIMIC-IV demo code.

Set `MEDS_DEV_DIR=/path/to/MEDS-DEV` to reuse a checkout and `MEDS_DEMO_DIR=/path/to/demo` to reuse the
dataset. A bare test run never clones MEDS-DEV or downloads MIMIC data.

Until MEDS-DEV PR #330 is merged, automatic integration provisioning pins its head commit
`19a8aa3417fae3586b2e8f0f17aba19ddb0560d4`. That commit is on top of `dev`, so it supplies both the
`predicates_path` passthrough (PR #325) and the `task_criteria_path` passthrough that zero-shot profiles
use. Set `MEDS_DEV_REF` to select another revision containing those capabilities. Reused `MEDS_DEV_DIR`
checkouts are capability-checked rather than silently using a model-side fallback. Only zero-shot
repositories require `task_criteria_path`.

## Cluster and result interfaces

```bash
$EDITOR slurm/config.sh
./slurm/submit.sh --dry-run
./slurm/submit.sh
scripts/github-sync.sh <run-id>
```

Each command manifest records wall time and sampled process-tree PSS/RSS. Structured run evidence is kept
under `runs/<run-id>/`. GitHub synchronization publishes a run branch; it does not commit datasets,
checkpoints, credentials, or raw logs.

## Develop the Copier template

From the parent repository root:

```bash
uv sync --group dev
uv run pytest tests/test_render.py -q
uv run pytest tests/ -q
uv run ruff check tests/test_render.py
uv run ruff format --check tests/test_render.py
```

`tests/test_render.py` renders all six model profiles, compiles the generated repositories, validates command
registries and operational files, tests measurement manifests and run results, and exercises MEDS-DEV
registration. To test the rendered repository itself, render it into a temporary directory and run:

```bash
uv run --project /tmp/my-render --extra test pytest /tmp/my-render/tests -q -rs
```

The authority is [`template/SPEC.md`](template/SPEC.md), which Copier renders as `SPEC.md` in generated
repositories. Files under `template/` are the generated payload; root tests
validate that payload without imposing a model implementation.

Profile selection and the distinct version 3 step names are described in [profiles](docs/profiles.md).
See the [software contract](https://github.com/florian6973/meds-model-core/blob/bfa347d13270bd29899671974d819e3c6c6f7ba8/src/meds_model_core/CONTRACT.md), [migration guide](docs/migration-v3.md),
and [shared-package assessment](docs/shared-package-assessment.md).
