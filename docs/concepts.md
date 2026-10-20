# Concepts

This page walks through the objects the contract talks about, in the order data flows through a model:
the dataset, the task, the predicates, the task specification (zero-shot only), the artifacts each
command publishes, the final predictions, and the measurements attached to all of them.

## The MEDS dataset and its splits

The input data is a split-sharded [MEDS](https://medical-event-data-standard.github.io/) dataset, passed
as `external_meds_dir`. MEDS fixes what `subject_id`, `time`, `code`, the value columns, static events
(`time = null`) and code metadata mean; a model may not reinterpret them.

The dataset comes with three splits: `train`, `tuning` and `held_out`. They are a **boundary**:

!!! warning "Fit population statistics on `train` only"
    Anything fitted over a population — vocabularies, code frequencies, quantile bins, normalization
    constants, feature selections — must be fitted on the training split alone. Fitting over all splits is
    *transductive leakage*. It is easy to miss because it is not label leakage: code frequencies do not
    depend on labels, so a model can pass every label-leakage check and still carry it. If preprocessing
    is delegated upstream and the scope is not yours to control, declare which quantity was fitted over
    which population.

The MIMIC-IV demo in MEDS form is the canonical real-data example used by the tests; it is not a separate
schema.

## The task index (built upstream)

A *task* reaches the model as an **index**: a table of `(subject_id, prediction_time)` rows, plus a label
column such as `boolean_value` for training and evaluation. It is passed as `external_labels_dir`.

The index is never built in the model repository. One ACES extraction, run upstream, applies the task's
trigger, inclusion/exclusion criteria and splits, so every model scores exactly the same rows:

| Run | Who builds the index |
|---|---|
| MIMIC-IV demo (smoke test) | MEDS-DEV's `meds-dev-task`, task `mortality/in_icu/first_24h` |
| Full-data evaluation | the shared `work/` bundle produced by [meds-task-selection](https://github.com/florian6973/meds-task-selection) |

A model repository must not re-extract, filter or extend the index. If a model rebuilt the cohort itself,
two models could silently be evaluated on different patients, and a zero-shot model would read the labels
it is supposed to be blind to.

### Reading labels: the one rule

Prediction code works on the keys of the index, never on its labels. There is exactly one sanctioned
exception: once every probability is final, `predict` may join the label column onto the predictions by
key (`attach_ground_truth`), because meds-evaluation reads ground truth from the predictions file. Nothing
computed from that join may feed back into a prediction.

## Dataset predicates

Tasks are written against named *predicates* (for example `icu_admission`, `death`, or
`abnormally_low_sodium` with a value threshold). A dataset's predicates file binds those names to that
dataset's codes. It is passed as `external_predicates_file` (MEDS-DEV's `{predicates_path}`).

- When MEDS-DEV provides predicates for a dataset, reuse them; the MIMIC-IV demo must use MEDS-DEV's
  MIMIC-IV predicates.
- The model decides whether and how to use them: selecting tokens, building SQL or columns, matching
  events directly, or not at all.
- Any command that consumes the file records its digest and origin in its manifest.
- A model that relies on particular predicate names declares and validates them in its own configuration.
  The contract deliberately has no generic "predicate features" format.

## The task specification (zero-shot only)

A supervised model learns *what* to predict from labels. A zero-shot model never sees labels, so the task
itself must be an input. The task language is [ACES](https://eventstreamaces.readthedocs.io/): a criteria
file passed as `external_task_criteria_file`, bound to the dataset predicates. The pair is the **task
specification** (`TaskSpec`).

```mermaid
flowchart LR
    crit[ACES criteria file<br/>e.g. mortality/in_icu/first_24h.yaml] --> spec[TaskSpec]
    pred[Dataset predicates<br/>e.g. MIMIC-IV predicates.yaml] --> spec
    spec --> digest["semantics_digest<br/>sha256 of criteria + predicates"]
```

The **semantics digest** hashes the criteria bytes together with the predicates bytes. MEDS-DEV task files
leave dataset codes as `???`, so the same criteria bound to MIMIC-IV and to eICU predicates are different
tasks with different digests. Every task-conditioned artifact records this digest, so an artifact can never
be silently reused for another task. See [Zero-shot in practice](zero-shot.md).

## Artifacts and the manifest envelope

Every command publishes one **artifact**: a directory containing whatever payload the model wants plus a
`manifest.yaml` that follows a fixed envelope.

```mermaid
flowchart LR
    p[preprocess_data] -->|patients| pt[pretrain]
    pt -->|pretrained_model| i[infer]
    i -->|inference| st[supervised_train]
    st -->|supervised_model| pr[predict]
    pr -->|predictions| out[(final output)]
```

*(The `probe` profile shown; other profiles skip some commands. See [Choosing a profile](profiles.md).)*

| Artifact type | Produced by | Meaning |
|---|---|---|
| `patients` | `preprocess_data` | the model's own representation of the dataset |
| `pretrained_model` | `pretrain` | a task-independent model |
| `inference` | `infer` | reusable, task-independent information at the requested timepoints (embeddings, generated futures, …) |
| `supervised_model` | `supervised_train` | a task-specific model |
| `predictions` | `predict` | the normative final output |

Three properties hold for every artifact:

- **The payload format is the model's.** The manifest declares it (`payload_format: name/version`), and
  consumers reject an incompatible type, contract version or payload format *before* doing expensive work.
- **Publication is atomic.** The command works in a staging directory and writes `manifest.yaml` last;
  the staging directory then replaces the destination in one step. A crashed command leaves no
  half-written artifact behind.
- **Inputs are traceable.** The manifest records stable identifiers or digests of its inputs (including
  the predicates digest and, for task-conditioned artifacts, the task's provenance and digest), plus the
  git commit and dirty state of the code that produced it.

The helper `measured_artifact(...)` does all of this; see the [manifest reference](reference/manifest.md).

## Final predictions

`predict` writes `predictions.parquet` in the
[meds-evaluation](https://github.com/kamilest/meds-evaluation) prediction schema:

- exactly **one row per requested key**, with **unique keys**;
- row order means nothing and must never be used to match outputs to keys;
- conformance tests compare the written keys directly with the requested index — a self-reported count is
  not proof of coverage;
- rows may be left out only under an explicitly declared exclusion policy that lists the excluded keys.

For zero-shot models, predictions are always evaluated against the labels of the *requested* task, and the
predictions artifact carries or references the `relaxations.yaml` describing what the model actually
answered.

## Measurements

Every command invocation records its resource use in the manifest, wherever it runs (tests, MEDS-DEV,
SLURM):

- **wall time** on a monotonic clock;
- **memory** sampled over the whole process tree; on Linux, PSS (which apportions shared pages) is the
  comparison value and RSS is kept as a diagnostic;
- **GPU** peak allocated/reserved memory when measured;
- optional work units (subjects, events, rows, optimizer steps).

`null` means *not measured*; `0` means *measured, nothing used*. Measurements are observations for
comparing models, never pass/fail thresholds.
