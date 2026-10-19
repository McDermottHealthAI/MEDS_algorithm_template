# Zero-shot models: design notes

This note explains the zero-shot interface added to the contract (rendered `SPEC.md` sections 2.4 and 3.1,
`meds_model_contract/task.py`), how the existing ACES-to-MOTOR tooling plugs into it, and what remains to
be done outside this repository.

## The problem

Before this change, the two `zero_shot_*` profiles had the right command lifecycle but no way to state
*what* to predict. Their `predict` received only `external_labels_dir` (the index) and optionally the
dataset predicates, and every manifest recorded `semantics_digest: null`. A supervised model learns the task
from labels; a zero-shot model never sees labels, so it could only predict a task hard-coded into it, or
read the labels, which is leakage.

## Who builds what

| Product | Built by | Where |
|---|---|---|
| Cohort / index `(subject_id, prediction_time)` and labels | one ACES extraction, upstream of every model | MEDS-DEV `meds-dev-task` (demo), `meds-task-selection` `work/` bundle (full data) |
| Query for the model | the zero-shot model, from the same ACES task | the model repository (`encode`) |
| Predictions | the model | the model repository (`decode`) |

The model repository never builds, filters, or extends the cohort (SPEC section 2.2). Suppose a zero-shot
model rebuilt the cohort from the ACES task: every model could then end up scoring different rows, and the
cohort extraction would read the labels it is meant to be blind to. The ACES task reaches the model only
so that it knows *what* to ask about each requested row.

## The interface

Zero-shot prediction mirrors the supervised `predict`, with the task as an extra input:

| | Supervised `predict` | Zero-shot `predict` |
|---|---|---|
| Task | learned from labels in `supervised_train` | **`external_task_criteria_file`** (ACES) + `external_predicates_file` |
| Index | `external_labels_dir` | `external_labels_dir`, read label-blind via `read_index` |
| Data | MEDS dataset (via `preprocess_data`) | MEDS dataset (via `preprocess_data`) + pretrained model |
| Output | `predictions.parquet` | `predictions.parquet` + `relaxations.yaml` |

Internally the model implements `ZeroShotTranslator`, which has three steps:

```text
           TaskSpec (ACES criteria + predicates)       label-blind index
                         \                             /
                          encode  ->  inference target + relaxations.yaml
                                            |
             MEDS data + pretrained  ->  infer  ->  raw outputs
                                            |
                          decode  ->  predicted_boolean_probability per (subject_id, prediction_time)
```

- `zero_shot_direct`: `predict` runs all three steps.
- `zero_shot_materialized`: `infer` runs `encode` and `infer`, and `predict` runs `decode`. Both commands
  are task-conditioned (`ZERO_SHOT_TASK_COMMANDS`), and `predict` rejects an inference artifact whose
  `semantics_digest` differs from its own task's.

The contract guarantees four things:

1. **Task identity.** `TaskSpec.semantics_digest()` hashes the criteria bytes together with the predicates
   bytes. MEDS-DEV task files leave dataset predicates as `???`, so the same criteria bound to MIMIC-IV
   and to eICU predicates are different tasks and get different digests.
2. **Label blindness at the boundary.** `read_index` never selects a label column. The rendered
   `test_zero_shot_predictions_ignore_index_labels` reruns the model with every `boolean_value` flipped
   and requires identical predictions.
3. **Relaxations are published, not implied.** See below.
4. **Predictions are complete and keyed.** `check_decoded` checks the decoded probabilities by key against
   the requested index and requires values in [0, 1].

## Relaxations: three kinds

`aces-relaxations` and the model translators use "relaxation" for three different things. The ledger
gives each step a `kind` so they are never confused.

| `kind` | Owner | Examples | Effect on labels |
|---|---|---|---|
| `label_preserving` | `aces-relaxations` | `require_bounding_events`, `normalize` (re-root at prediction time, split label branch from criteria branches) | none on extracted rows (property-tested against ACES); `direction` must be `exact` |
| `approximation` | `aces-relaxations`, chosen by the translator | `simplify_constraints` (counts to ever/never/drop), `last_link_target` (single label window from its own start) | changes labels in a stated direction: `weakening` gives a superset of positives, `strengthening` a subset |
| `model_assumption` | the translator (for example `aces-to-motor`) | vocabulary restriction with the `marginal` sentinel; dropping all criteria branches (conditional independence); TTE stationarity; independence across codes for `and`/`or`; same-timestamp `and` read as within-window `and`; bounds that never occur extended to infinity | depends on the data distribution; usually `unknown` |

The rules that follow from this:

- `aces-relaxations` decides whether a task **can be posed** (`is_future_only`, `degeneracies`) and provides
  rewrites whose effect on labels is known. It deliberately does not decide which approximations a model
  should accept ("those decisions are left to the caller").
- The translator decides which steps its query language forces, and must record every one of them.
- Predictions are always evaluated against the labels of the **requested** task, because the relaxation is
  part of the model. The ledger tells a reader how much of the error is relaxation error rather than model
  error. A useful extra analysis is to extract the relaxed task's labels with
  `aces_relaxations.extract_at` on the same index and report AUROC against both label sets. This works for
  the task-rewrite steps, but not for model assumptions such as independence.

Two structural cases from `aces-to-motor`'s `docs/relaxation_examples.md` should be flagged on every
benchmark task, because they are wrong for every data distribution rather than only some:

- A criterion that shares codes with the label (a gap window that forbids the label code, or an inclusion
  criterion that requires it) cannot be independent of the label. Dropping it is always wrong.
- A same-timestamp `and` over codes that never co-occur has a true prevalence of about 0, but the decoded
  probability can be large.

## Mapping MOTOR onto the template

Use `zero_shot_materialized`. MOTOR inference is the expensive step, and its outputs (hazards per code at
each index time) can be shared across tasks.

| Template | aces-to-motor / femr_runner | Status |
|---|---|---|
| `preprocess_data` | `femr_runner/scripts/meds_reader_convert.sh` (MEDS to `meds_reader` DB) | exists, uses hard-coded cluster paths |
| `pretrain` | `femr_runner/scripts/train.py` (tokenizer, motor task, batches, train) | exists; must write `metadata.json` with `vocabulary` (task-head codes) and `inference_command_template` |
| `infer` (encode) | `aces_to_motor.encode(TaskExtractorConfig.load(criteria, predicates), ModelSpec.from_dir(...), read_index(...))` | exists |
| `infer` (model) | bundle (`index.parquet` + `query.json`) to `hazards.npz` | **missing.** `femr_runner/scripts/eval.py` already computes `time_dependent_logits` per row (`run_inference`, `match_logits_to_rows`), but only for per-(code, horizon) AUROC. It needs a small `infer_bundle.py` that reads `query.json["codes"]`, maps them to head indices, writes `rates = 2**logits` with `bin_edges_s` from the motor task's time bins, computes `marginal_mean_F` over the full vocabulary when `needs_marginal`, and writes `inference_stats.json` |
| `predict` (decode) | `aces_to_motor.decode(bundle, index)` | exists; the result must pass `check_decoded` |
| ledger | `relaxation_report.md` (prose) | convert the fixed pipeline's steps into `Relaxation` entries (table in the rendered implementation guide) |

Multi-task: `aces_to_motor.encode_tasks` shares one inference pass across many tasks. That fits a later
`infer` over the union index, with per-task `predict` decodes that each check their own digest. The
current contract runs one task per `predict`, which is correct but repeats inference. Also note that FEMR's
batch builder makes a row's representation depend on *which* other rows a subject carries (median |dp| = 0,
6-10% of rows move by more than 0.01 when tasks are batched together). This is not label leakage. The
label-invariance test flips label values but keeps the rows, so the batching is unchanged. If GPU
nondeterminism still moves probabilities, set `LABEL_INVARIANCE_ATOL` in `tests/e2e.py` and record why.

Suggested MOTOR test plan, in order:

1. Render `zero_shot_materialized` and wrap `aces-to-motor` in `Infer` and `Predict`.
2. Write the missing `bundle -> hazards.npz` runner in `femr_runner`, and check it against `eval.py` on a
   single-code fixed-horizon task, where both must agree because that relaxation is exact.
3. Run the MIMIC-IV demo task `mortality/in_icu/first_24h`. Expect a non-exact ledger: the gap-window
   exclusion is dropped, and the label window is promoted to the prediction time.
4. Run the shared ten-task `meds-task-selection` bundle, with the ledgers attached to each result.

## Outside this repository: MEDS-DEV

MEDS-DEV formats model commands with `dataset_dir`, `labels_dir`, `output_dir`, `split`,
`model_initialization_dir` and, since PR #325, `predicates_path`. It never passes the task definition, even
though it knows `task_name` and `TASKS[task_name]["criteria_fp"]`. Zero-shot `model.yaml` therefore uses
`{task_criteria_path}`, which needs a passthrough analogous to #325 in `MEDS_DEV/models/__init__.py`:

```python
from ..tasks import TASKS

if cfg.get("task_criteria_path", None):
    format_kwargs["task_criteria_path"] = str(cfg.task_criteria_path)
elif cfg.get("task_name", None) in TASKS:
    format_kwargs["task_criteria_path"] = str(TASKS[cfg.task_name]["criteria_fp"])
```

This is MEDS-DEV PR #330 (into `dev`), which also adds `task_criteria_path: null` to `_run_model.yaml`.
MEDS-DEV forwards the *original* task, since only the model knows which relaxations its query language
needs. `labels_dir` still supplies the index; zero-shot models read only its key columns. Until #330
merges, `tests/integration.py` pins its head commit, and only zero-shot repositories require the
capability. The MIMIC demo gate and SLURM runs pass the criteria file directly
(`tests/e2e.py:mimic_task_criteria`, `TASK_CRITERIA_FILE`).
