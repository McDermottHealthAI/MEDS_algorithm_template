# Shared core package

The core lives in its own [repository](https://github.com/florian6973/meds-model-core), pinned by the template to an immutable commit.
See its [layout and extraction status](https://github.com/florian6973/meds-model-core/blob/bfa347d13270bd29899671974d819e3c6c6f7ba8/README.md) for the implemented APIs and planned modules.
The [specification](reference/spec.md) below is rendered from the installed dependency, so the site
and generated models use the same version without copying the contract into this repository.

Family-specific sharing belongs in one model-family repository with multiple profiles and shared internal
modules. Tokenizers, neural architectures, objectives and model-specific task translators stay there.
