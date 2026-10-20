# FAQ

## Why can't my model build or filter its own cohort?

Because then two models could be evaluated on different patients and nobody would notice. The index and
its labels come from one ACES extraction run upstream (MEDS-DEV's `meds-dev-task` for the demo, the
meds-task-selection bundle for full data). A model predicts every requested row; rows can be left out
only under a declared exclusion policy that lists them.

## My model needs a statistic over the whole dataset. Can I compute it on all splits?

No. Fit vocabularies, frequencies, bins and normalizers on `train` only. Computing them over all splits is
transductive leakage: it uses held-out patients' data even though it never touches a label.

## Why do some models run in two Python environments?

Because their dependencies cannot coexist. A model's training stack may pin an older `meds` (for example
femr 0.2.4 requires `meds==0.3.3`), while the ACES tooling a zero-shot adapter uses for task translation
(aces-relaxations, es-aces ≥ 0.7.3) requires `meds ≥ 0.4`. The two sides can run in separate environments
and exchange only files. The contract does not care how a command
is executed, so this is allowed; document it in the repository.

## What does it mean that a task is "refused"?

A zero-shot model must raise rather than answer a task it cannot pose; the command fails and writes no
predictions. The common case is a direct model given a task whose label is not *future-only* in
aces-relaxations' structural sense — for example MEDS-DEV's `mortality/in_icu/first_24h`, whose `gap`
window is anchored at the trigger and straddles the prediction time. A re-anchoring step makes it
posable; see [Zero-shot in practice](zero-shot.md#windows-that-straddle-the-prediction-time).
Materialized models are not affected.

## Why is the AUROC on the MIMIC-IV demo undefined (or meaningless)?

The demo has 100 patients. For `mortality/in_icu/first_24h` the held-out split has a handful of rows and
may have no positive label at all, in which case AUROC is undefined. Training rows cannot stand in for a
pretrained model: pretraining saw those patients' futures. The demo gate validates that the pipeline runs
on real data — formats, scale transitions, coverage, resources — not how good the model is. Performance
comes from the full-data run.

## My model writes several files next to `predictions.parquet`. Is that allowed?

Yes, with one rule: every parquet file in the predictions artifact must be a predictions file. MEDS-DEV
evaluates every `**/*.parquet` under the predictions directory, and the key check does the same. Store
supporting tables — a zero-shot query bundle, a coverage table — in another format such as Arrow IPC;
`relaxations.yaml` and JSON files are fine.

## How do the tests catch label leakage and transductive fitting?

In the same real run as the end-to-end test:

- **Label leakage:** `predict` is run again, with the exact arguments `run_e2e` used, on a copy of the
  index with every label column removed. It must still cover every key, so any read of a label on the
  prediction path fails.
- **Transductive fitting:** `tests.signal.add_split_canaries` gives every tuning and held-out subject a
  canary code that no training subject has. Your `fitted_codes(artifacts)` hook reports every code the
  model fitted a statistic for (vocabulary, frequencies, bins); no canary may appear in it.

## Can a non-zero-shot model use the ACES task?

It may accept `external_task_criteria_file`, but it is not required to, and its artifacts record
`semantics_digest: null`. Supervised, finetune and probe models learn the task from its labels.

## How do I bring template changes into an existing repository?

Review your working tree, then run in the generated repository:

```bash
copier update --trust
```

The repository's `.copier-answers.yml` records the template source, revision and answers, so Copier can
apply the template's changes as a three-way merge. Render from the Git URL rather than a local checkout so
updates work on every machine.

## Where is the authoritative rule for X?

In the [specification](reference/spec.md), which this site includes verbatim from `template/SPEC.md`.
Generated repositories carry the same file as their `SPEC.md`.
