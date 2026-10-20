# Running a model

A generated repository exposes one command-line entry point, a MEDS-DEV descriptor, and a SLURM
interface. All three run the same commands with the same standard arguments.

## The CLI

```bash
uv run meds-model commands                       # list the selected profile's commands, in order
uv run meds-model <command> key=value [key=value ...]
```

Each `key=value` is parsed as JSON when possible (`do_overwrite=true`, `splits=["held_out"]`), otherwise
kept as a string. Unquoted lists in the style MEDS-DEV and Hydra emit, such as `splits=[held_out]` or
`splits=[train, tuning]`, are parsed as lists of strings.

```bash
uv run meds-model preprocess_data external_meds_dir=/data/mimic output_data_dir=runs/x/data
uv run meds-model pretrain input_data_dir=runs/x/data output_pretrained_model_dir=runs/x/pretrained
uv run meds-model predict input_data_dir=runs/x/data input_pretrained_model_dir=runs/x/pretrained \
    external_labels_dir=/tasks/mortality external_task_criteria_file=/tasks/mortality.yaml \
    splits=[held_out] output_predictions_dir=runs/x/predictions do_overwrite=true
```

## Standard arguments

Argument names are shared across models so the same command line works for any repository. Which
arguments a command reads depends on the profile; the table shows how the generated `model.yaml` wires
them.

| Argument | Meaning | Read by |
|---|---|---|
| `external_meds_dir` | the split-sharded MEDS dataset | `preprocess_data` (all profiles); `predict` in `zero_shot_materialized` (real history for evaluating the task) |
| `external_predicates_file` | dataset predicates (MEDS-DEV `{predicates_path}`) | `preprocess_data` when the model uses predicates; zero-shot `predict` (part of the task) |
| `external_labels_dir` | the task index, built upstream | `supervised_train` (with labels); `infer`, `predict` (keys only) |
| `external_task_criteria_file` | the ACES criteria file (MEDS-DEV `{task_criteria_path}`) | `predict` in both zero-shot profiles |
| `output_data_dir` / `input_data_dir` | the `patients` artifact | written by `preprocess_data`; read by later commands |
| `output_pretrained_model_dir` / `input_pretrained_model_dir` | the `pretrained_model` artifact | written by `pretrain`; read by `infer`, `supervised_train` (finetune) and `predict` (zero_shot_direct) |
| `output_inference_dir` / `input_inference_dir` | the `inference` artifact, a directory of its own next to the others | written by `infer`; read by `supervised_train` (probe) and `predict` (zero_shot_materialized) |
| `output_supervised_model_dir` / `input_supervised_model_dir` | the `supervised_model` artifact | written by `supervised_train`; read by `predict` |
| `output_predictions_dir` | the `predictions` artifact (`predictions.parquet` + `manifest.yaml`) | written by `predict` |
| `splits` | which splits of the index to process | `infer` (materialized), `predict` |
| `do_overwrite` | replace an existing destination artifact | any command; publication otherwise refuses to overwrite |

Models may accept extra, model-specific arguments; document them in the repository's README.

## MEDS-DEV

`model.yaml` is the [MEDS-DEV](https://github.com/Medical-Event-Data-Standard/MEDS-DEV) descriptor. Its
`unsupervised` / `supervised` × `train` / `predict` slots hold command strings with these template
variables:

| Variable | Filled by MEDS-DEV with |
|---|---|
| `{dataset_dir}` | the MEDS dataset |
| `{labels_dir}` | the task's labels (the index) |
| `{output_dir}` | this stage's output directory |
| `{model_initialization_dir}` | the previous stage's `{output_dir}` |
| `{split}` | the split to predict (`held_out` in full mode) |
| `{predicates_path}` | the dataset's predicates file (`predicates_path` argument; MEDS-DEV PR #325) |
| `{task_criteria_path}` | the task's ACES criteria: the `task_criteria_path` argument, else the registered criteria file of `task_name` (MEDS-DEV PR #330) |

Every artifact gets its own subdirectory of the MEDS-DEV run directory: `data/`, `pretrained/`, `model/`,
`inference/`, `predictions/`. Nothing is written to `{output_dir}` itself, because MEDS-DEV keeps its own
`cmd.sh` and `.done` marker there and artifacts are published by atomically replacing their destination
directory. Artifacts are never nested inside one another, so runs over different indexes or splits cannot
overwrite each other's outputs.

MEDS-DEV evaluates every `**/*.parquet` under the predictions directory with meds-evaluation 0.0.3, so
every parquet file there must be a predictions file (see the [FAQ](faq.md)).

Register a completed repository with MEDS-DEV by copying its descriptor into a MEDS-DEV checkout:

```bash
uv run meds-model-add-to-meds-dev --meds-dev /path/to/MEDS-DEV --name my_model
```

The `meds_dev` test tier
provisions MEDS-DEV at a pinned commit that supplies both passthroughs (currently the head of PR #330, which
builds on PR #325); set `MEDS_DEV_REF` to use another revision. A checkout supplied through
`MEDS_DEV_DIR` is capability-checked rather than silently used; only zero-shot repositories require
`{task_criteria_path}`.

## SLURM

`slurm/config.sh` is the only SLURM file meant for routine edits: partitions, time limits, CPUs, memory,
GPUs, and `stage_args`, which prints each command's `key=value` arguments from environment variables
(`MEDS_ROOT`, `LABELS_DIR`, `TASK_CRITERIA_FILE`, `RUN_DIR`).

```bash
$EDITOR slurm/config.sh
./slurm/submit.sh --dry-run    # prints every sbatch call and each command's arguments; changes nothing
./slurm/submit.sh              # submits the profile as dependent jobs
```

- `stage_args` lists only the selected profile's commands.
- Each command is one job; later commands depend on earlier ones (`afterok`). `preprocess_data` runs on the
  CPU partition, the others on the GPU partition.
- Submission refuses a dirty working tree, so every cluster run corresponds to a commit. `--dry-run` only
  warns, so a run can be reviewed before it is committed.
- Artifacts land under `runs/<run-id>/artifacts`.

## Run results and GitHub sync

Each run's evidence is structured: `spec.yaml` (dataset, task, predicates), `result.yaml` (status, git
commit and dirty state, host, Python, SLURM job id, per-command resources) and copies of every command
manifest under `runs/<run-id>/`. `write_run_result` assembles them.

```bash
scripts/github-sync.sh <run-id>
```

publishes them on an isolated `runs/<slug>/<run-id>` branch and opens a draft PR. Datasets, checkpoints,
credentials and raw logs are never committed.
