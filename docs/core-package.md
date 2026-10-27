# Shared core package

The core lives in its own [repository](https://github.com/florian6973/meds-algorithm-core), pinned by the template to an immutable commit.
See its [layout and usage](https://github.com/florian6973/meds-algorithm-core/blob/7134bc4370b04b7fbbbfca1017a30ffa07709299/README.md) for its artifact, runtime, task, evaluation, integration and conformance APIs.
The [specification](reference/spec.md) below is rendered from the installed dependency, so the site
and generated algorithms use the same version without copying the contract into this repository.
The [architecture and UML](reference/architecture.md) are also rendered from the pinned core wheel.

Family-specific sharing belongs in one algorithm-family repository with multiple profiles and shared internal
modules. Tokenizers, neural architectures, objectives and algorithm-specific task translators stay there.

Generated repositories import `meds_algorithm_core` directly. Their package contains a typed algorithm
implementation and a algorithm-owned immutable configuration. `tests/e2e.py` invokes the same shared runner
as the CLI and supplies fitted-feature inspection hooks.
Reusable assertions, fixtures and MEDS-DEV provisioning live in core. No compatibility package is copied.

Publication uses exclusive writers and overwrite rollback. Algorithm provenance must be supplied explicitly;
the installed package cannot infer a algorithm checkout. See the core README for crash recovery, reader
visibility during overwrite, optional dependencies, and measurement limits.
