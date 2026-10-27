# Fully manual example: setup to predictions

This walkthrough generates a repository, implements its three supervised methods by hand, creates
synthetic inputs, and runs **preprocessing → training → prediction** locally. No coding agent, MEDS-DEV
installation, clinical dataset, GPU or cluster is needed. All commands appear in execution order below.

The example is a **constant-prevalence baseline**, not a clinical algorithm reproduction. It learns one
smoothed probability from the training labels and emits it for every requested held-out key. It copies
events during preprocessing but does not use event features to predict. Additional predicates are
included to demonstrate composition and provenance, not to claim feature-dependent behavior.

## Setup and expected result

Use Bash on Linux/macOS or inside WSL on Windows, with **Git and uv installed** and network access for
Python/packages. Run the commands in a new workspace; the script refuses an existing directory.
`uv python install 3.11` installs the tutorial's Python, and `uv sync --extra test` installs the generated
package, core, Polars and the conformance dependencies into its `.venv`. No global Python environment
is modified. Copier and the template revision are pinned so the tutorial can be reproduced.

You can paste the entire block into Bash, or save/download the [same script](examples/manual-supervised.sh)
and run `bash manual-supervised.sh /absolute/path/to/a/new/tutorial-directory`.

The generated package is `manual_baseline`, its class is `ManualBaseline`, and its named command is
`manual-baseline`. `meds-algorithm` is an equivalent entry point. Each lifecycle command starts a fresh
process, using the same `config_file`. There are three training outcomes (`true, true, false`) and a
smoothing value of 1, so the resulting probability is `(2 + 1) / (3 + 2) = 0.6` for both held-out rows.

## All commands, in order

The code-writing commands below intentionally replace the generated tutorial stubs. The template alone
does not contain an implemented algorithm. Leave its completion gate in place: this short tutorial does
not implement `tests/e2e.py`, the full implementation report, or the MEDS-DEV/demo acceptance tiers.
The final pytest command runs only the generated contract and operations checks; its success does not
mean a production port has passed the [complete workflow](workflow.md).

```bash
--8<-- "docs/examples/manual-supervised.sh"
```

## What was produced

Under `manual-meds-example/manual-baseline/` (or your chosen workspace):

| Path | Contents |
|---|---|
| `src/manual_baseline/manual_baseline.py` | Concrete algorithm methods and profile association |
| `src/manual_baseline/config.py` | Named, typed configuration with positive smoothing validation |
| `dataset_configs/demo.yaml` | Dataset-specific settings and relative additional-predicates path |
| `inputs/meds/data/`, `inputs/labels/` | Synthetic events and the separate label/index bundle |
| `runs/manual/supervised/artifacts/data/` | Prepared events, summary, resolved feature predicates and core metadata |
| `runs/manual/supervised/artifacts/algorithm/` | Persisted learned probability and core metadata |
| `runs/manual/supervised/artifacts/predictions/` | Held-out probabilities, post-score truth and core metadata |

Each artifact has `manifest.yaml`, `config.json` and `request.json`. The manifest records measurements,
input identities and the configuration. Because this example does not create a Git commit for the
generated implementation, its commit provenance may be unavailable; commit reviewed implementation
code before reproducible production runs. Keep input data and artifact payloads out of source control.

The index and evaluation labels happen to share a directory in this example. Prediction reads only
keys through `request.index.read()`; the runner attaches `boolean_value` afterward. In real work,
reuse the upstream reviewed task bundle, respect all temporal cutoffs, and do not create labels inside
the algorithm. Additional feature predicates must not redefine the evaluated task.

To rerun, choose fresh output paths. Explicit `do_overwrite=true` opts into replacing an artifact with
rollback; do not add it automatically to every command. Other profiles have different intermediate
steps: use the [profile lifecycle table](reference/spec.md#3-commands-and-algorithm-profiles) and
[per-step arguments](reference/spec.md#9-software-interfaces) when adapting this example.
