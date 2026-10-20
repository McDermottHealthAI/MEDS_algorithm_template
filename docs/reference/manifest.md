# Manifest fields

Every artifact directory contains a `manifest.yaml`, written last, after the payload, and published
atomically with it. `measured_artifact` (see the [contract API](api.md)) produces it; this table describes
what it writes.

```yaml
contract_version: "2"
artifact:
  type: predictions
  payload_format: my-model-predictions/v1
  producer: my_model.commands.Predict
command:
  name: predict
  config_digest: "sha256:…"
code:
  git_commit: 3f2a…
  dirty: false
inputs:
  external_predicates_file: {path: /…/predicates.yaml, digest: "sha256:…"}
  task: {name: null, criteria_file: {path: …, digest: "sha256:…"}, predicates_file: {path: …, digest: "sha256:…"}}
semantics_digest: "sha256:…"
resources:
  wall_seconds: 14.5
  memory:
    peak_process_tree_pss_bytes: 3300000000
    peak_process_tree_rss_bytes: 3500000000
    sampling_interval_seconds: 0.25
    source: linux_proc_smaps_rollup
    includes_descendants: true
  gpu: {peak_allocated_bytes: null, peak_reserved_bytes: null, source: null}
  measurement: {schema_version: "1"}
```

| Field | Meaning |
|---|---|
| `contract_version` | always `"2"`; readers reject anything else |
| `artifact.type` | `patients`, `pretrained_model`, `inference`, `supervised_model` or `predictions` |
| `artifact.payload_format` | model-defined `name/version` of the payload; consumers reject formats they do not understand |
| `artifact.producer` | importable or external identifier of the implementation that wrote it |
| `command.name` | the contract command that produced it |
| `command.config_digest` | `digest_config` over the command's arguments plus any model-owned settings it resolved (defaults, configuration files); two artifacts made with the same configuration share it |
| `code.git_commit`, `code.dirty` | recorded automatically: the commit of the model repository and whether its tree had uncommitted changes, so a run from a modified tree is identifiable; `null` outside a checkout |
| `inputs` | stable identifiers or digests of the inputs. Always includes the predicates file's path and digest when the command consumed one; task-conditioned zero-shot artifacts include `task` (`TaskSpec.provenance()`) |
| `semantics_digest` | the task's `TaskSpec.semantics_digest()` for task-conditioned artifacts; `null` otherwise |
| `resources.wall_seconds` | monotonic wall time of the command |
| `resources.memory.*` | peak PSS and RSS summed over the live process tree (Linux `smaps_rollup`; `getrusage` elsewhere), the sampling interval, the source, and whether descendants are included |
| `resources.gpu.*` | peak allocated and reserved GPU memory and its source; `null` when not measured |
| `resources.measurement.schema_version` | version of the measurement block, currently `"1"` |

`null` means *not measured* or *not applicable*; `0` means *measured, nothing used*. Manifests may add
diagnostic fields such as coverage counts or work units; those never replace the direct key-coverage
check.
