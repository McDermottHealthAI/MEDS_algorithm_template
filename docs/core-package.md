# Shared core package

The core lives in its own [repository](https://github.com/McDermottHealthAI/meds-algorithm), pinned by the template to an immutable commit.
See its [layout and usage](https://github.com/McDermottHealthAI/meds-algorithm/blob/10be61980262684a979a284b3f5c1577ef188c90/README.md) for its artifact, runtime, task, evaluation, integration and conformance APIs.
The [specification](reference/spec.md) below is rendered from the installed dependency, so the site
and generated algorithms use the same version without copying the contract into this repository.
The [architecture and UML](reference/architecture.md) are also rendered from the pinned core wheel.

`AlgorithmConfig` is the shared configuration parent. Neural implementations can extend `NNConfig`;
the [neural configuration and scaling guide](reference/architecture.md#neural-network-configuration-and-scaling-experiments)
shows a concrete subclass, YAML settings and a capacity sweep. It also explains why data-subset selection
belongs upstream and which measurements an algorithm must report for a later scaling-law analysis.
The template keeps this example in the core guide rather than maintaining a second specification.

Family-specific sharing belongs in one algorithm-family repository with multiple profiles and shared internal
modules. Tokenizers, neural architectures, objectives and algorithm-specific task translators stay there.

Generated repositories import `meds_algorithm` directly. Their package contains a typed algorithm
implementation and a algorithm-owned immutable configuration. `tests/e2e.py` invokes the same shared runner
as the CLI and supplies fitted-feature inspection hooks.
Reusable assertions, fixtures and MEDS-DEV provisioning live in core. No compatibility package is copied.

Publication uses exclusive writers and overwrite rollback. Algorithm provenance must be supplied explicitly;
the installed package cannot infer a algorithm checkout. See the core README for crash recovery, reader
visibility during overwrite, optional dependencies, and measurement limits.
