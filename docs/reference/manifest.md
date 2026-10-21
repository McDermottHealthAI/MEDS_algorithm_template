# Reading artifact manifests

The [normative manifest schema](spec.md#4-intermediate-artifacts) and
[measurement schema](spec.md#6-measurements) live in the core contract. This page does not duplicate
their field tables.

When comparing runs, check the producer and payload format, configuration digest, source revision,
input content identities, and task semantics before comparing measurements. A configuration hash alone
does not identify the dataset or weights. A copied path is provenance, not proof of compatibility.

`null` means not measured or not applicable; zero is an observed value. Sampled live process-tree
memory and scheduler peak memory measure different things. Coverage counts are diagnostics; compare
actual prediction keys with the requested index.

The template's `measured_artifact` implementation remains pending extraction into the core's
`artifacts` and `runtime` modules. The [package status](../core-package.md) distinguishes implemented
modules from planned work.
