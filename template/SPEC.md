# Contract reference

This repository follows contract version 3 from its pinned `meds-model-core` dependency. The normative
specification is shipped with that package; do not copy or edit it in this model repository.

After installing dependencies, read the exact installed specification with:

```bash
meds-model-core-spec
# equivalently:
python -m meds_model_core.spec
```

The package source owns `src/meds_model_core/CONTRACT.md`. The template documentation site renders that
same file. Keep model-specific choices and deviations in `IMPLEMENTATION_REPORT.md`, and operational
instructions in `docs/IMPLEMENTATION_GUIDE.md`.
