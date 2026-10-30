# Contract reference

This repository follows contract version 4 from its pinned `meds-algorithm` dependency. The normative
specification is shipped with that package; do not copy or edit it in this algorithm repository.

After installing dependencies, read the exact installed specification with:

```bash
meds-algorithm-spec
# equivalently:
python -m meds_algorithm.spec
```

The package source owns `src/meds_algorithm/CONTRACT.md`. The template documentation site renders that
same file. Keep algorithm-specific choices and deviations in `IMPLEMENTATION_REPORT.md`, and operational
instructions in `docs/IMPLEMENTATION_GUIDE.md`.
