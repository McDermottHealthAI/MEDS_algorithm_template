# Minimal MEDS algorithm template

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/meds-algorithm-template)](https://pypi.org/project/meds-algorithm-template/)
[![Tests and code quality](https://github.com/McDermottHealthAI/MEDS_algorithm_template/actions/workflows/ci.yml/badge.svg)](https://github.com/McDermottHealthAI/MEDS_algorithm_template/actions/workflows/ci.yml)
[![Documentation](https://readthedocs.org/projects/meds-algorithm/badge/?version=latest)](https://meds-algorithm.readthedocs.io/en/latest/)
[![Contributors](https://img.shields.io/github/contributors/McDermottHealthAI/MEDS_algorithm_template)](https://github.com/McDermottHealthAI/MEDS_algorithm_template/graphs/contributors)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](https://github.com/McDermottHealthAI/MEDS_algorithm_template/pulls)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](https://github.com/McDermottHealthAI/MEDS_algorithm_template/blob/main/LICENSE)

This repository is a self-contained [Copier](https://copier.readthedocs.io) template for minimal,
contract-first MEDS algorithm repositories.

Shared contracts and the canonical specification live in
[`meds-algorithm`](https://github.com/McDermottHealthAI/meds-algorithm). Generated repositories pin its PyPI release
`meds-algorithm==0.4.0a5` for reproducible installations.
The core owns the reusable infrastructure and conformance helpers; generated repositories import it directly.

The template fixes the external contract—MEDS input, six algorithm profiles and standard arguments, typed
artifact manifests, final MEDS predictions, measurements, MEDS-DEV, SLURM, and GitHub result exchange—while
leaving preprocessing, featurization, intermediate formats, frameworks, batching, and algorithm execution to
the generated repository.

## Documentation

For setup and every command in execution order, see the [fully manual example](https://meds-algorithm.readthedocs.io/en/latest/manual-example/).
It includes a complete tutorial implementation and synthetic data, so it runs without an agent or cluster.

The [unified documentation](https://meds-algorithm.readthedocs.io/en/latest/) is maintained and built in
[`meds-algorithm`](https://github.com/McDermottHealthAI/meds-algorithm). It includes concepts, profiles,
implementation workflow, running, publishing and API references. This repository retains template-specific
contributor instructions and the documents rendered into generated algorithm repositories.

## Render a repository

The installable `meds-algorithm-template` command uses the matching `v<package-version>` tag from this
GitHub repository. It needs Git and network access; it does not bundle a second copy of the template.
Install the pinned generator with:

```bash
uvx --from 'meds-algorithm-template==0.4.0a2' meds-algorithm-template ../my-meds-algorithm --trust
```

Use `--defaults --data-file answers.yaml` for unattended generation. The answers file records the
canonical GitHub source and release tag, so subsequent `copier update --trust` uses the same source.
The package itself uses Copier and PyYAML; generated projects depend on `meds-algorithm`.
See [publishing both packages in order](https://github.com/McDermottHealthAI/MEDS_algorithm_template/blob/main/RELEASING.md) for the release process and dependency updates.

From the root of this checkout:

```bash
uv tool install copier
copier copy . ../my-meds-algorithm
```

The rendered repository commits `.copier-answers.yml`, which records its template source, revision, and
answers. To bring later template changes into that repository, review its working tree and run:

```bash
cd ../my-meds-algorithm
copier update --trust
```

For portable updates across machines, copy from the Git repository URL rather than from a local checkout;
Copier records that source in the answers file.

For a reproducible non-interactive render, first create `profiles.yml` containing
`profiles: [probe]` (or several profile names), then run:

```bash
copier copy --defaults --trust \
  --data algorithm_name="My MEDS Algorithm" \
  --data algorithm_slug=my_meds_algorithm \
  --data-file profiles.yml \
  --data uses_predicates=true \
  --data implementation_source=https://github.com/example/source-model \
  . ../my-meds-algorithm
```

`--trust` is safe but currently unnecessary because the template defines no post-copy tasks. It is included
so the command remains usable if formatting/bootstrap tasks are added later.

### Copier questions

| Question | Meaning |
|---|---|
| `algorithm_name` | Human-readable algorithm name. |
| `algorithm_slug` | Importable Python package and MEDS-DEV algorithm identifier. |
| `package_name` | PyPI distribution name; defaults to the slug with hyphens, independently of the import/CLI. |
| `repository_url`, `license_expression` | Canonical HTTPS URL and chosen SPDX license; may be blank initially but required for release, together with a LICENSE file. |
| `algorithm_class` | Public class name; defaults to CamelCase from the slug. Set `RETAIN` explicitly to preserve that spelling. |
| `profiles` | Nonempty list of supported profiles; each gets its own MEDS-DEV YAML. |
| `algorithm_description` | Short description rendered into README and `algorithms/<profile>/model.yaml`. |
| `author_name`, `author_email` | MEDS-DEV contact metadata. |
| `uses_predicates` | Whether generated MEDS-DEV commands pass `external_predicates_file`. The algorithm still owns interpretation. |
| `implementation_source` | Paper path/URL, source repository path/URL, or both; prefilled into generated guidance and the report. |

For example, `algorithm_slug=retain algorithm_class=RETAIN` generates `retain/retain.py` containing
`RETAIN`, plus `retain/config.py` containing `RETAINConfig`. Import them with
`from retain import RETAIN, RETAINConfig` (or `from retain.retain import RETAIN`). The installed
`retain` command is the algorithm's CLI; each algorithm has its own command, so several can share an environment. Use the core runner for Python
execution so direct imports retain the same validation/publication path as the CLI.

Profiles are `supervised`, `finetune`, `probe`, `zero_shot_direct`, `zero_shot_materialized`, and
`predict_only`. A algorithm profile selects required commands, not an architecture or execution backend.

The two zero-shot profiles also receive the task itself: an ACES criteria file passed as
`external_task_criteria_file` (`{task_criteria_path}` in `algorithms/<profile>/model.yaml`). They must publish a
`relaxations.yaml` ledger stating how the answered task differs from the requested one. They differ in how
the algorithm answers. `zero_shot_direct` algorithms answer task-derived queries directly (MOTOR, EveryQuery),
recommended as an `aces-to-<algorithm>` adapter on aces-relaxations. `zero_shot_materialized` algorithms generate
futures in a task-independent `infer_trajectories`, and `predict_zero_shot_materialized` evaluates the task on them. See [Zero-shot in practice](https://meds-algorithm.readthedocs.io/en/latest/zero-shot/) for the design, algorithm examples, and the MEDS-DEV
passthrough this needs.

## Work in the generated repository

```bash
cd ../my-meds-algorithm
uv sync --extra test
uv run my-meds-algorithm commands
uv run pytest -rs
```

The generated commands are intentional stubs. Before implementation, the local, MEDS-DEV, and MIMIC
end-to-end tests report explicit `algorithm_stub` skips. Start with these rendered files:

1. `AGENTS.md`
2. `SPEC.md`
3. `README.md`
4. `docs/IMPLEMENTATION_GUIDE.md`
5. `src/<algorithm_slug>/<algorithm_slug>.py` and `src/<algorithm_slug>/config.py`
6. `tests/e2e.py`
7. `IMPLEMENTATION_REPORT.md`

A completed implementation removes each profile from `STUB_PROFILES` only after that profile works.

## Implementation prompt

Use the [interactive prompt builder](https://meds-algorithm.readthedocs.io/en/latest/prompt-builder/) or the
[copyable implementation prompt](https://meds-algorithm.readthedocs.io/en/latest/implementation-prompt/) maintained in `meds-algorithm`.

See [the test catalogue](TESTING.md) for each template test and its purpose; generated repositories
include `docs/TESTING.md` describing every acceptance test.

## Test tiers in a generated repository

```bash
uv run pytest -rs
uv run pytest -m meds_dev -rs
uv run pytest -m real_data -rs
```

- The default suite checks the contract and algorithm-owned local end-to-end adapter.
- `meds_dev` registers `algorithms/<profile>/model.yaml` and runs it in MEDS-DEV's isolated environment.
- `real_data` builds or reuses the MEDS MIMIC-IV demo, extracts MEDS-DEV task
  `mortality/in_icu/first_24h`, reuses MEDS-DEV's MIMIC predicates, and runs the full selected algorithm profile.

The implementation guide defines what follows these commands: a report/review gate after the demo, then
an explicitly authorized run on the selected full dataset and final report. The demo's required task is
ICU mortality; additional MEDS-DEV MIMIC-supported tasks are optional coverage checks, not a mandatory
task benchmark.
The full-data evaluation instead uses a separately reviewed, shared task bundle for the target dataset
(clinical ACES tasks or randomly sampled code-by-horizon tasks), so algorithm comparisons on that dataset use
the same task definitions and labels. Selecting another full dataset does not change the provided MIMIC-IV demo code.

Set `MEDS_DEV_DIR=/path/to/MEDS-DEV` to reuse a checkout and `MEDS_DEMO_DIR=/path/to/demo` to reuse the
dataset. A bare test run never clones MEDS-DEV or downloads MIMIC data.

Until MEDS-DEV PR #330 is merged, automatic integration provisioning pins its head commit
`19a8aa3417fae3586b2e8f0f17aba19ddb0560d4`. That commit is on top of `dev`, so it supplies both the
`predicates_path` passthrough (PR #325) and the `task_criteria_path` passthrough that zero-shot profiles
use. Set `MEDS_DEV_REF` to select another revision containing those capabilities. Reused `MEDS_DEV_DIR`
checkouts are capability-checked rather than silently using a algorithm-side fallback. Only zero-shot
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

`tests/test_render.py` renders all six algorithm profiles, compiles the generated repositories, validates command
registries and operational files, tests measurement manifests and run results, and exercises MEDS-DEV
registration. To test the rendered repository itself, render it into a temporary directory and run:

```bash
uv run --project /tmp/my-render --extra test pytest /tmp/my-render/tests -q -rs
```

The authority is [`template/SPEC.md`](template/SPEC.md), which Copier renders as `SPEC.md` in generated
repositories. Files under `template/` are the generated payload; root tests
validate that payload without imposing a algorithm implementation.

Profile selection and the distinct version 4 step names are described in [profiles](https://meds-algorithm.readthedocs.io/en/latest/profiles/).
See the [software contract](https://github.com/McDermottHealthAI/meds-algorithm/blob/v0.4.0a5/src/meds_algorithm/CONTRACT.md), [migration guide](https://meds-algorithm.readthedocs.io/en/latest/migration-v4/),
and [shared-package assessment](https://meds-algorithm.readthedocs.io/en/latest/shared-package-assessment/).

## Changes

### Unreleased

- Move the documentation site and prompt builder to `meds-algorithm` on Read the Docs, and replace
  this repository's Pages site with redirects. Generated-repository guides remain template-owned.
- Require confirmation for material scientific ambiguities by default; offer explicitly enabled exploratory
  assumptions in the prompt builder while preserving evaluation and execution approval gates.

- Generate an algorithm release guide, Trusted Publishing workflow, and installed-distribution checks.
- Configure PyPI metadata separately from Python names and bundle portable run/profile YAMLs once at build time.

### 0.4.0a2 (2026-11-03)

- Generate projects using the published `meds-algorithm==0.4.0a5` dependency.
- Inherit shared acceptance tests and keep algorithm-specific adapters and scientific tests local.
- Add the optional Hydra profile runner, local subprocess and Submitit execution, and resolved dry-run plans.
- Add the implementation prompt builder and reorganize documentation, including typed request UML and test guides.
- Use each algorithm's own executable name. Conformance and orchestration remain optional extras.
