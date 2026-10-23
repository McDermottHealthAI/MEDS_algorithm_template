# Choosing profiles

A profile describes a model's lifecycle. A repository may declare several profiles and implement them
in one package. Choose them with Copier's `profiles` multiselect, or supply a data file:

```yaml
profiles: [finetune, probe, zero_shot_direct]
```

The [canonical lifecycle table](reference/spec.md#3-commands-and-model-profiles) lists the exact steps.

Only preprocessing and pretraining share command names. They may share artifacts when input identities,
configuration, payload format and training scope match. Selecting two profiles does not automatically
make their artifacts compatible.

| Profile | Use when |
|---|---|
| `supervised` | Learning a task-specific model directly from the dataset's training labels. |
| `finetune` | Updating a pretrained encoder together with a task-specific head. |
| `probe` | Fitting a task-specific head on frozen encoder representations. |
| `zero_shot_direct` | Translating an ACES task into direct model queries and decoding probabilities without labels. |
| `zero_shot_materialized` | Generating task-independent futures, then evaluating the task on history plus those futures. |
| `predict_only` | Preprocessing then applying a supplied fixed model or an in-context learner, without a training command. |

`predict_only` is the renamed packaged profile. It does not mean probe training. In-context learners may
read explicitly selected train/tuning examples; fixed scores need no labels. Neither may read evaluated
labels before its probabilities are final.

Each descriptor lives at `models/<profile>/model.yaml` and is registered as `<model-name>__<profile>` in
MEDS-DEV. Each invocation selects exactly one declared profile. Examples:

```bash
meds-model profiles
meds-model commands --profile probe
meds-model-add-to-meds-dev --meds-dev /path/to/MEDS-DEV --name example --profile probe
PROFILE=probe ./slurm/submit.sh --dry-run
```

The probe's `infer_embeddings` stage materializes keyed representations without labels. `train_probe`
fits a head on training representations, and `predict_probe` applies it to explicit evaluated embeddings.
Supervised/fine-tuned prediction instead takes `input_data_dir` and the fitted model. Neither dependency
is assumed to disappear just because training recorded its path.

The [software contract](reference/spec.md#9-software-interfaces) gives every command's arguments, artifact type, label
access, class responsibilities, compatibility checks, and acceptance requirements. See
[migration](migration-v3.md) for an existing repository.
