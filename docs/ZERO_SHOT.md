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

### Direct vs materialized: how the model answers

The two zero-shot profiles are not two ways to organize the same code. They correspond to two kinds of
model:

| | `zero_shot_direct` | `zero_shot_materialized` |
|---|---|---|
| The model | answers a query directly: a hazard, or P(code in window) | generates (*materializes*) possible futures |
| Examples | MOTOR (time-to-event), EveryQuery (code-in-window queries) | autoregressive EHR generators |
| `infer` | none | task-independent: N futures per index row, reusable across every task |
| `predict` | task → model query → model → probabilities | evaluate the ACES task on history + each future; probability = fraction of futures with the label |
| Relaxations | the task is *translated* into the query language, so usually several steps; `exact` is rare | the task is *evaluated*, so it is usually `exact` up to sampling |
| Non-future-only tasks | must be rejected (the query is anchored at the prediction time) | fine: past criteria are checked on real history |

For a direct model, the recommended internal shape (the `ZeroShotTranslator` sketch in the rendered
implementation guide; not enforced) is an `aces-to-<model>` adapter with three steps, all inside `predict`:

```text
           TaskSpec (ACES criteria + predicates)       label-blind index
                         \                             /
                          encode  ->  model query + relaxations.yaml
                                            |
             MEDS data + pretrained  ->  model  ->  raw outputs
                                            |
                          decode  ->  predicted_boolean_probability per (subject_id, prediction_time)
```

The query, raw outputs, and ledger are published inside the predictions artifact so decode choices stay
inspectable. In both profiles only `predict` is task-conditioned (`ZERO_SHOT_TASK_COMMANDS`).

### What is enforced, and what is guidance

| Enforced by the contract and tests | Guidance only |
|---|---|
| `external_task_criteria_file`, checked before work | building on aces-relaxations, and which of its functions to call |
| `semantics_digest` and task provenance in task-conditioned manifests | the encode -> infer -> decode split and the `ZeroShotTranslator` sketch |
| index read without label columns (`read_index`) | the `kind` / `direction` vocabulary for ledger steps |
| complete, unique prediction keys | |
| `relaxations.yaml` with `query_language`, `decoded_quantity`, `exact` | |

aces-relaxations is not a template dependency. It is pre-1.0, and its PR #18 already moved functions that
aces-to-motor imports, so each adapter pins its own version.

The contract guarantees four things:

1. **Task identity.** `TaskSpec.semantics_digest()` hashes the criteria bytes together with the predicates
   bytes. MEDS-DEV task files leave dataset predicates as `???`, so the same criteria bound to MIMIC-IV
   and to eICU predicates are different tasks and get different digests.
2. **Label blindness at the boundary.** `read_index` never selects a label column. This is a rule plus a
   helper, not a test: a test comparing runs with flipped labels would also require deterministic
   predictions, which sampling-based models do not give.
3. **Relaxations are published, not implied.** See below.
4. **Predictions are complete and keyed.** `check_decoded` checks the decoded probabilities by key against
   the requested index and requires values in [0, 1].

## Relaxations: three kinds

`aces-relaxations` and the model adapters use "relaxation" for three different things. The recommended
ledger `kind` keeps them apart; the contract does not validate it.

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

Use `zero_shot_direct`. MOTOR answers time-to-event queries directly; it does not generate futures.
Implemented in `florian6973/meds-model-motor-plus` (private), with preprocessing and pretraining from
femr_runner.

| Template | aces-to-motor / femr_runner | Status |
|---|---|---|
| `preprocess_data` | `femr_runner/scripts/meds_reader_convert.sh` (MEDS to `meds_reader` DB) | exists, uses hard-coded cluster paths |
| `pretrain` | `femr_runner/scripts/train.py` (tokenizer, motor task, batches, train) | exists; must write `metadata.json` with `vocabulary` (task-head codes) and `inference_command_template` |
| `predict` (encode) | `aces_to_motor.encode(TaskExtractorConfig.load(criteria, predicates), ModelSpec.from_dir(...), read_index(...))` | exists |
| `predict` (model) | bundle (`index.parquet` + `query.json`) to `hazards.npz` | **missing.** `femr_runner/scripts/eval.py` already computes `time_dependent_logits` per row (`run_inference`, `match_logits_to_rows`), but only for per-(code, horizon) AUROC. It needs a small `infer_bundle.py` that reads `query.json["codes"]`, maps them to head indices, writes `rates = 2**logits` with `bin_edges_s` from the motor task's time bins, computes `marginal_mean_F` over the full vocabulary when `needs_marginal`, and writes `inference_stats.json` |
| `predict` (decode) | `aces_to_motor.decode(bundle, index)` | exists; the result must pass `check_decoded` |
| ledger | `relaxation_report.md` (prose) | write the fixed pipeline's steps as `relaxations.yaml` `steps` (table in the rendered implementation guide) |

Multi-task: `aces_to_motor.encode_tasks` shares one inference pass across many tasks. The current
contract runs one task per `predict`, which is correct but repeats inference. Sharing it would need a
multi-task `predict`, which is a later extension. Also note that FEMR's
batch builder makes a row's representation depend on *which* other rows a subject carries (median |dp| = 0,
6-10% of rows move by more than 0.01 when tasks are batched together). This is not label leakage, but it
means a task's probabilities can differ slightly between a standalone and a batched run.

Suggested MOTOR test plan, in order:

1. Render `zero_shot_direct` and wrap `aces-to-motor` (encode, hazards runner, decode) in `Predict`.
2. Write the missing `bundle -> hazards.npz` runner in `femr_runner`, and check it against `eval.py` on a
   single-code fixed-horizon task, where both must agree because that relaxation is exact.
3. Run a MIMIC-IV demo task. `mortality/in_icu/first_24h` is currently not posable for direct models:
   aces-relaxations rejects it as not future-only, because its `gap` window is rooted at the trigger and
   straddles the prediction time. The `abnormal_lab/*/first_24h` tasks are posable, but `normalize` drops
   the future half of their `no_discharge` window without a message. Both have the same root cause; see the
   open issue below.
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

## Open issue: windows that straddle the prediction time

Several MEDS-DEV tasks have a window rooted at the trigger that spans the prediction time. Examples are
`gap` in `mortality/in_icu/first_24h` and `no_discharge` in every `abnormal_lab/*/first_24h` task.
Upstream cohort extraction already enforces the window's past part. Its future part is a real condition
on the label: no discharge or death in the next 24h, for example. aces-relaxations treats such windows as
past, which has two effects:

- **Mortality:** `is_future_only` fails, so direct models reject the task.
- **Abnormal-lab tasks:** `normalize` drops the window, and with it the future condition, without a
  message.

The fix belongs in aces-relaxations: split the window at the prediction time, drop the past part, and keep
the future part as a criteria branch. Materialized models are unaffected, because they evaluate the
original task on history plus generated futures.

