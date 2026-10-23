# Shared core package

The core lives in its own [repository](https://github.com/florian6973/meds-model-core), pinned by the template to an immutable commit.
See its [layout and usage](https://github.com/florian6973/meds-model-core/blob/a16ba1d5e6837bb0d50120cdf2e09b348745c964/README.md) for its artifact, runtime, task, evaluation, integration and conformance APIs.
The [specification](reference/spec.md) below is rendered from the installed dependency, so the site
and generated models use the same version without copying the contract into this repository.

Family-specific sharing belongs in one model-family repository with multiple profiles and shared internal
modules. Tokenizers, neural architectures, objectives and model-specific task translators stay there.

Generated repositories import `meds_model_core` directly. Their own package contains model command
implementations; `tests/e2e.py` supplies model-specific execution and fitted-feature inspection hooks.
Reusable assertions, fixtures and MEDS-DEV provisioning live in core. No compatibility package is copied.

Publication uses exclusive writers and overwrite rollback. Model provenance must be supplied explicitly;
the installed package cannot infer a model checkout. See the core README for crash recovery, reader
visibility during overwrite, optional dependencies, and measurement limits.
