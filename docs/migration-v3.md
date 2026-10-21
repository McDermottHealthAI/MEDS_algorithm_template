# Migrating to multiple profiles

Version 3 changes command names, artifact types, descriptor locations and repository dispatch. Do not
reuse version 2 artifacts by editing their manifest version: validate or rebuild their payloads against
the new contract. The template emits and reads version 3 envelopes.

1. Replace the Copier `profile` answer with `profiles: [<name>, ...]`. Rename `packaged` to `predict_only`.
   Keep the original source/revision metadata in `.copier-answers.yml` and review the Copier update diff.
2. Replace the command registry with the union of selected profiles. Shared steps appear once.
3. Rename commands according to the table below. Split previously conditional implementations into
   distinct classes, keeping shared private helpers where their semantics really match.
4. Update every invocation, manifest producer, output argument, test adapter and SLURM stage selection.
5. Move the MEDS-DEV descriptor to `models/<profile>/model.yaml`; add one for each declared profile.
   Register them independently using `--profile`; the registered name is `<name>__<profile>`.
6. Supply explicit split lists for inference and prediction. Supervised/fine-tuned prediction receives `input_data_dir`; probe prediction receives
   `input_embeddings_dir`. Scoring and inference use `external_index_dir`, not the training-label argument.
7. Replace the global `IS_STUB` boolean with `STUB_PROFILES`. Run the acceptance suite for every profile.
   Record the profile in `write_run_result(..., profile=...)`.

| Profile | Old command | New command |
|---|---|---|
| All | `preprocess_data`, `pretrain` where present | Unchanged |
| supervised | `supervised_train`, `predict` | `train_supervised`, `predict_supervised` |
| finetune | `supervised_train`, `predict` | `train_finetune`, `predict_finetune` |
| probe | `infer`, `supervised_train`, `predict` | `infer_embeddings`, `train_probe`, `predict_probe` |
| zero_shot_direct | `predict` | `predict_zero_shot_direct` |
| zero_shot_materialized | `infer`, `predict` | `infer_trajectories`, `predict_zero_shot_materialized` |
| predict_only (formerly packaged) | `predict` | `predict_only` |

`inference` splits into `embeddings` and `trajectories`, with matching
`input_embeddings_dir`/`output_embeddings_dir` and `input_trajectories_dir`/`output_trajectories_dir`.
Task-model artifacts split into `supervised_model`, `finetuned_model`, and `probe_model`, with matching
input/output argument names. Prediction output remains `output_predictions_dir`.

Use Copier 9.17.1 or newer; the template uses its yield extension to generate a directory for each
selected profile. A single-profile repository may omit CLI `--profile`; a repository with multiple
profiles must select one. There is no ambiguous compatibility alias for the old generic command names.

This revision supplies the interfaces and tests. It does not automatically migrate downstream model
implementations or publish a shared runtime package. See the [package assessment](shared-package-assessment.md).

The core package now owns the single normative `CONTRACT.md`. Generated `SPEC.md` is a pointer to the
installed package version, readable with `meds-model-core-spec`. The template and generated projects
install the alpha from an immutable Git commit in the separate core repository; no PyPI release is required.
