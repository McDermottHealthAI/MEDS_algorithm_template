# Migrating to multiple profiles

Version 3 changes command names, artifact types, descriptor locations and repository dispatch. Do not
reuse version 2 artifacts by editing their manifest version: validate or rebuild their payloads against
the new contract. The template emits and reads version 3 envelopes.

1. Replace the Copier `profile` answer with `profiles: [<name>, ...]`. Rename `packaged` to `predict_only`.
   Keep the original source/revision metadata in `.copier-answers.yml` and review the Copier update diff.
2. Implement the selected profile ABCs and associate profiles with concrete classes in `IMPLEMENTATIONS`.
   Shared methods appear once where their semantics match.
3. Rename commands according to the table below. Split previously conditional implementations into
   distinct profile methods, sharing cohesive components where their semantics really match.
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

Replace imports from `meds_model_contract` with `meds_model_core` and remove the generated compatibility
package. Core supplies the registration/input-resolution CLI entry points; keep only the model's own
CLI in its project configuration. Import shared fixtures and checks from `meds_model_core.conformance`.
For the typed API, pass model provenance explicitly to `AlgorithmRepository(..., repo=model_root)`.
Return `E2EResult` from core's `conformance.types`, recording all external inputs;
the lifecycle checker now reruns every step with forbidden outcomes absent and fresh output paths.
Existing model repositories are not migrated by this template change.

## From mapping-based commands to typed algorithms

The Python API in core 0.4.0a1 keeps the version 3 CLI names and artifact envelope. Existing
`Command`/`ModelRepository` callers still work; their model-owned publication does not automatically
gain the new runner behavior. Migrate deliberately:

1. Move command bodies to the selected `Algorithm` profile methods. Use their typed request fields.
2. Put model settings/defaults in a frozen `ModelConfig` subclass; test validation and JSON round trips.
3. Replace internal publication contexts with writes to `request.output.directory` and a returned
   `PayloadMetadata`. Remove model-written manifests and truth attachment; the runner owns those.
4. Extend `validate_inputs` for payload compatibility. Document any override of its default same-model,
   same-config rule, especially for external pretrained artifacts or legacy manifests without config.
5. Route the CLI and end-to-end adapters through `AlgorithmRepository`/`StepRunner`. Verify saved
   requests/configuration and fitted artifacts work in a fresh process.

See [architecture and UML](reference/architecture.md). No private model migration is included here.
