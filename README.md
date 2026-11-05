# Minimal MEDS algorithm template

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/meds-algorithm-template)](https://pypi.org/project/meds-algorithm-template/)
[![Tests and code quality](https://github.com/McDermottHealthAI/MEDS_algorithm_template/actions/workflows/ci.yml/badge.svg)](https://github.com/McDermottHealthAI/MEDS_algorithm_template/actions/workflows/ci.yml)
[![Documentation](https://github.com/McDermottHealthAI/MEDS_algorithm_template/actions/workflows/docs.yml/badge.svg)](https://McDermottHealthAI.github.io/MEDS_algorithm_template/)
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

For setup and every command in execution order, see the [fully manual example](https://github.com/McDermottHealthAI/MEDS_algorithm_template/blob/main/docs/manual-example.md).
It includes a complete tutorial implementation and synthetic data, so it runs without an agent or cluster.

This README is written for coding agents that port algorithms. For a human-oriented explanation of the
contract (concepts, choosing a profile, zero-shot algorithms, the gate workflow, running, and reference), read
the documentation site: https://McDermottHealthAI.github.io/MEDS_algorithm_template/ (built from `docs/` by
`.github/workflows/docs.yml`). Preview it locally with:

```bash
uv run --group docs mkdocs serve
```

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
futures in a task-independent `infer_trajectories`, and `predict_zero_shot_materialized` evaluates the task on them. See [Zero-shot in practice](https://github.com/McDermottHealthAI/MEDS_algorithm_template/blob/main/docs/zero-shot.md) for the design, algorithm examples, and the MEDS-DEV
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

<!-- --8<-- [start:implementation-prompt] -->
## Copyable algorithm-implementation prompt

Use the [interactive prompt builder](https://McDermottHealthAI.github.io/MEDS_algorithm_template/prompt-builder/)
or fill in the fields below. The agent inspects sources and selects profiles before generating a new
local or GitHub repository. The builder runs locally in your browser; it does not launch an agent.
The provided `real_data` test remains the MIMIC-IV demo smoke test, independent of supplied evaluation tasks.

The prompt adapts [Ponytail's implementation principles](https://github.com/DietrichGebert/ponytail/blob/main/skills/ponytail/SKILL.md)
to scientific algorithm development. It works with Claude and other coding agents without installing a plugin.

```text
Implement a MEDS algorithm from the following inputs.

Paper(s), supplementary material and versions:
<PAPER_REFERENCES_OR_NOT_SUPPLIED>

Code/repository source(s), revisions, configurations and checkpoints:
<CODE_REFERENCES_OR_NOT_SUPPLIED>

Destination (a NEW local repository or a NEW GitHub repository, including visibility):
<NEW_REPOSITORY_DESTINATION>

Local working directory for the new repository:
<NEW_LOCAL_REPOSITORY_PATH>

Profile selection (automatic, or an explicit list of one or more profiles):
<PROFILE_SELECTION>

Dataset context (name, revision and MEDS path, if available):
<DATASET_CONTEXT_OR_NOT_SUPPLIED>

Already prepared evaluation tasks (labels location, task-config location, bundle revision and
optional task subset; or explicitly not supplied):
<PREPARED_TASK_BUNDLE_OR_NOT_SUPPLIED>

Work scope (implementation/local tests, also MEDS-DEV integration, or preparation for full evaluation):
<WORK_SCOPE>

Additional implementation constraints:
<ADDITIONAL_CONSTRAINTS_OR_NONE>

Inspect the supplied sources before generating the repository. If both paper and code are provided,
compare them, record discrepancies and identify which behavior is implemented; do not silently assume
one always overrides the other. If only a paper is provided, distinguish source-backed choices from
necessary assumptions. If only code is provided, inspect its revision, configuration and checkpoint
requirements; do not claim fidelity to an unavailable paper.

For automatic profile selection, choose one or more profiles supported by documented source behavior:
supervised, finetune, probe, zero_shot_direct, zero_shot_materialized or predict_only. Record evidence for
each choice and proceed when the evidence is clear. Do not add speculative capabilities merely because
a profile exists. For an explicit list, implement that scope; report material incompatibilities before
implementing unsupported behavior, and do not silently replace or expand it. Shared methods may be
implemented once through multiple profile inheritance when their semantics match, or through separate
classes with shared components. Each selected profile gets its own MEDS-DEV YAML and acceptance tests.

Generate the new repository with the MEDS algorithm template at
https://github.com/McDermottHealthAI/MEDS_algorithm_template using a reviewed immutable revision, and
record it in .copier-answers.yml. Pass the selected profiles explicitly; do not accidentally accept the
single-profile default. Never overwrite an existing local directory or GitHub repository. For a local
destination, initialize Git without creating a remote. For a GitHub destination, create the specified
repository with the specified visibility and connect the local checkout; report missing access without
changing the destination or visibility. Respect any more specific workspace repository-routing rules.

Supplied evaluation tasks are already prepared: use their labels and task configs as fixed inputs.
Verify their dataset/revision, task identities, splits, prediction times and consistency before use.
An optional task subset selects only tasks already present in that bundle. Do not generate new tasks,
extract new labels, relabel examples or silently modify the task definitions. Use supplied indices or
read only the supplied prediction keys through the core index reader; evaluation outcomes must never
enter scoring. Zero-shot profiles additionally require executable task criteria and matching predicates.
If the bundle is not supplied, continue implementation and synthetic tests; report evaluation as
pending. An incomplete bundle blocks only the dependent evaluation, not unrelated implementation.

Read AGENTS.md, SPEC.md, README.md, and docs/IMPLEMENTATION_GUIDE.md in the generated repository
completely before writing code. Inspect the paper, supplementary material, source repository,
configuration files, checkpoints, preprocessing code, and evaluation code available from the supplied
source.

Apply the Ponytail principle of the smallest complete change: implement the complete source-defined
algorithm with the least additional infrastructure. Check meds-algorithm, existing algorithm-family code,
standard libraries and installed dependencies before creating helpers. If the source ships an installable
package or executable, depend on it pinned to the exact reviewed revision and call it; write only contract
glue (label-free preprocessing, cohort/key adaptation, explicit key association, coverage). Install it in the
algorithm environment; if it breaks meds-algorithm within core's declared dependency ranges, fix core. For a
genuine conflict with core, run the source as an external executable from a separate environment that the
algorithm package creates and manages (committed lockfile, built at install or first use, digest recorded in
manifests; MEDS-DEV installs only requirements.txt). Reimplement only when the source cannot run even in
isolation or its code cannot meet the contract even with glue, and record why in IMPLEMENTATION_REPORT.md;
local hardware alone is not a reason, since CPU or other hardware is acceptable.
Choose an algorithm_slug that does not shadow the source's distribution or import name (for example
genhpf_meds, not genhpf), so both can be installed together. Keep shared fixes in their
owning package; do not copy core utilities into the algorithm repository. Avoid speculative wrappers,
configuration options and compatibility layers. Trace affected commands, callers, fixtures and
documentation, and finish all required changes. Simplicity must preserve scientific fidelity, temporal
and label isolation, artifact validation, reproducibility, required evaluation evidence and human
review gates. Write focused tests for new behavior and failure cases. Report deviations and checks
that were not run.

Write minimalist, auditable, object-oriented algorithm code. Put source-defined hyperparameters and defaults
in the algorithm-owned frozen <AlgorithmClass>Config class in config.py; validate values and prove
serialization round trips. Keep the implementation in <algorithm_slug>.py and expose the named algorithm
and configuration classes from the package, so callers can import them meaningfully.
For neural algorithms with matching semantics, extend core NNConfig rather than
duplicating shared capacity, learning_rate, batch_size, weight_decay and dropout settings. Define
source-backed defaults and the capacity-multiplier mapping (reference architecture, dimensions, rounding
and minimums); call super().validate() for inherited
constraints. Test that the settings actually control construction/training. See the installed architecture
guide for units, extension examples and scaling ownership. Keep cohort selection upstream; record actual
parameter counts and consumed data separately rather than inferring them from capacity or a data fraction.
Use inherited additional_predicates_file for dataset-specific feature additions when needed. Read the
runner-resolved request.predicates_file in preprocessing; do not override base definitions, merge again,
or change task predicates. Preserve temporal isolation and use the same configuration across steps.
Implement the selected Algorithm profile methods with their typed request classes. Prefer small cohesive
components and explicit constructor dependencies; use inheritance for the profile contract and composition
for algorithm internals. Do not add unnecessary classes, wrappers, mutable module-level runtime state, hidden
singletons, import-time work, broad exception swallowing, or duplicated contract tables. Declarative
constants and the profile-to-implementation association are appropriate; fitted state belongs in artifacts.
Use core's runner for both CLI execution and tests. Algorithm methods write only to its staging destination
and return PayloadMetadata; do not reimplement publication, measurements or manifest/config/request writing.
Implement explicit payload compatibility checks. Prediction outputs contain keys and probabilities;
only the runner attaches evaluation truth after scoring. Demonstrate that saved configuration and requests
can be reloaded in a fresh process and executed without an earlier call on the same algorithm instance.

Preserve all selected algorithm profiles and standardized command arguments, MEDS input boundary, artifact
manifest envelopes, MEDS-DEV model.yaml interface, and final MEDS prediction output. Intermediate payload
formats and execution mechanisms are algorithm-owned: choose whatever preprocessing, featurization, framework,
batching or non-batching strategy, external executable, storage format, and algorithm architecture most
faithfully reproduce the source.

When predicates are needed, reuse MEDS-DEV predicates for the selected dataset if available; otherwise,
use reviewed external predicates for that dataset and record their provenance. Decide within the algorithm
how those predicates become inputs. Validate dataset-specific codes, units, task definitions, and label mappings;
do not assume MIMIC mappings apply to another dataset. Keep such mappings in dataset-specific
configuration or algorithm-owned code. Do not introduce a generic predicate-derived feature representation
into the contract package. Keep the provided MIMIC-IV demo code, task, and MEDS-DEV predicates as the
canonical smoke test, regardless of the full-data target.

For a zero_shot_direct algorithm (answers queries directly, e.g. MOTOR, EveryQuery) or a zero_shot_materialized
algorithm (generates futures and evaluates the task on them; infer is task-independent and only predict
receives the task): the algorithm receives the original ACES task through
external_task_criteria_file (with the dataset predicates) and the upstream-built index through
external_index_dir. Never build, filter, or extend the cohort, and read the index only through
meds_algorithm.read_index. Reuse an existing aces-to-<algorithm> adapter for this algorithm if one exists;
otherwise write one on aces-relaxations, pinned to an exact version: reject tasks that are not future-only
or are degenerate, normalize, then apply only the approximations and assumptions the algorithm's query
language forces. Publish relaxations.yaml with each zero-shot prediction artifact, and report per task whether
the answer is exact.
A materialized algorithm evaluates the task on generated futures instead and needs no relaxation beyond
sampling. Follow the shape for the selected profile in docs/IMPLEMENTATION_GUIDE.md.
Do not omit source behavior because it is inconvenient for a fixture; adapt the implementation or fixture
instead.

Record every material source element as ported, adapted, or omitted, with evidence and justification, in
IMPLEMENTATION_REPORT.md. Implement every selected typed algorithm method, finalize the implementation-specific
command strings in model.yaml, and implement tests/e2e.py. Configure representative config instances
in tests/conftest.py. Keep TestConformance inheriting the shared meds-algorithm acceptance suite;
do not copy its test bodies or override its checks to suppress failures. Remove each profile from STUB_PROFILES only
after that profile completes and produces standards-conformant predictions; complete every selected profile.

Always run:

    uv run pytest -rs

Also run `bash scripts/check_distribution.sh` to verify installed imports, CLI commands and bundled
defaults outside the checkout. Extend `tests/wheel_smoke.py` for required algorithm configuration or
resources. Follow RELEASING.md for publication readiness; package publication itself requires an explicit
user request. Do not choose a license on the user's behalf or bundle datasets, credentials or fitted weights.

If the selected scope includes MEDS-DEV integration or full-evaluation preparation, also run:

    uv run pytest -m meds_dev -rs

For implementation/local-tests scope, finish with implementation and local validation evidence. For
MEDS-DEV integration scope, finish after its integration evidence. Report unavailable dependencies or
adapters explicitly; do not weaken tests. The following demo and full-data stages apply only when the
selected scope is preparation for full evaluation; selecting that scope is not execution approval.

Complete the pre-demo sections of IMPLEMENTATION_REPORT.md and ask for human review of source fidelity,
predicate interpretation, and the proposed MIMIC-IV demo execution. Only after approval, run:

    uv run pytest -m real_data -rs

There must be zero algorithm_stub skips. Report exact pass/skip counts and account for every remaining skip.
Update IMPLEMENTATION_REPORT.md with the demo cohort, final-output coverage, predicate provenance,
environment, wall time, peak process-tree PSS/RSS, GPU measurements when available, failures, and fixes.
Ask for a second human review before launching the selected full dataset through the repository's SLURM
interface. Review target-dataset compatibility, access, and resources separately from the MIMIC-IV demo.
Use the supplied, already prepared task bundle for the selected dataset. It must contain task configs,
per-task labels/keys and split assignments; zero-shot runs additionally require the original ACES criteria
and matching predicates. Do not generate or extract replacement evaluation tasks. Canonical synthetic
fixtures and the built-in MIMIC-IV demo smoke task remain separate from this supplied evaluation bundle. If the bundle is absent
or inconsistent, report the evaluation blocker and the exact missing inputs.
Record the dataset name/revision, predicate provenance, bundle location, supplied bundle revision and
available upstream build provenance, and a digest of its task definitions. Keep the bundle external to Git.
Commit the implementation, configuration and report-so-far; push when a remote is configured. Run the
cluster job from that exact clean commit. After the authorized run, complete the report with full-data evidence, scientific deviations, and known limitations, then
synchronize structured results through the GitHub workflow when the destination has a GitHub remote.
For a local-only repository, retain the committed report and run evidence locally. Treat
docs/IMPLEMENTATION_GUIDE.md as the authority for the ordered gates and their evidence.
```
<!-- --8<-- [end:implementation-prompt] -->

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

Profile selection and the distinct version 4 step names are described in [profiles](https://github.com/McDermottHealthAI/MEDS_algorithm_template/blob/main/docs/profiles.md).
See the [software contract](https://github.com/McDermottHealthAI/meds-algorithm/blob/v0.4.0a5/src/meds_algorithm/CONTRACT.md), [migration guide](https://github.com/McDermottHealthAI/MEDS_algorithm_template/blob/main/docs/migration-v4.md),
and [shared-package assessment](https://github.com/McDermottHealthAI/MEDS_algorithm_template/blob/main/docs/shared-package-assessment.md).

## Changes

### Unreleased

- Link to the shared `meds-algorithm` catalogue and explain registration in generated release guides.

- Generate an algorithm release guide, Trusted Publishing workflow, and installed-distribution checks.
- Configure PyPI metadata separately from Python names and bundle portable run/profile YAMLs once at build time.

### 0.4.0a2 (2026-11-03)

- Generate projects using the published `meds-algorithm==0.4.0a5` dependency.
- Inherit shared acceptance tests and keep algorithm-specific adapters and scientific tests local.
- Add the optional Hydra profile runner, local subprocess and Submitit execution, and resolved dry-run plans.
- Add the implementation prompt builder and reorganize documentation, including typed request UML and test guides.
- Use each algorithm's own executable name. Conformance and orchestration remain optional extras.
