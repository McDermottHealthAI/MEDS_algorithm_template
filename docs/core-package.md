# Shared core package

The core lives in its own [repository](https://github.com/florian6973/meds-model-core), pinned by the template to an immutable commit.
See its [layout and extraction status](https://github.com/florian6973/meds-model-core/blob/5599c0925f9361057b2ef396c57eb8a194928c1a/README.md) for the implemented APIs and planned modules.
The [specification](reference/spec.md) below is rendered from the installed dependency, so the site
and generated models use the same version without copying the contract into this repository.

Family-specific sharing belongs in one model-family repository with multiple profiles and shared internal
modules. Tokenizers, neural architectures, objectives and model-specific task translators stay there.
