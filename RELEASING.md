# Publishing meds-algorithm-template

Release `meds-algorithm` first. This repository publishes a small Copier frontend named
`meds-algorithm-template`; it is not another copy of the shared algorithm library. The command fetches
`https://github.com/McDermottHealthAI/MEDS_algorithm_template.git` at `v<installed-version>` and records
that source/tag in `.copier-answers.yml`, preserving normal Copier updates. Git and network access are
required. The generator wheel contains the frontend, not the template payload.

Use the [shared publishing checklist](https://github.com/McDermottHealthAI/meds-algorithm/blob/main/RELEASING.md)
for the exact PyPI/TestPyPI publisher fields and GitHub environment setup. The template values are:
project `meds-algorithm-template`, owner `McDermottHealthAI`, repository `MEDS_algorithm_template`,
workflow `publish.yml`, and environments `testpypi` / `pypi`. The workflow must be merged into `main`
before GitHub exposes its manual dispatch action.

## 1. Switch generated projects to the published shared package

This development version pins core revision `99b3b59798d796360d1eff74fa75db58d35c4e90`.
First publish `meds-algorithm==0.4.0a5`, then replace the development Git requirements with the exact
PyPI requirements below before tagging generator `0.4.0a2`:

| File | Change |
|---|---|
| `pyproject.toml`, development dependencies | Pin the shared conformance dependency to `meds-algorithm[conformance]==0.4.0a5` |
| `template/pyproject.toml.jinja`, project dependencies | Use `meds-algorithm[data]==0.4.0a5` |
| `template/pyproject.toml.jinja`, test extra | Use `meds-algorithm[conformance]==0.4.0a5` |
| `README.md` | Document the shared PyPI version and update the generator install example to `0.4.0a2` |
| `uv.lock` | Regenerate with `uv lock` |
| `template/pyproject.toml.jinja`, Hatch metadata | Remove `allow-direct-references` after replacing all Git requirements |

Do not change the generator's runtime dependencies to require the shared library; it only generates
files. Preserve historical tutorial/source revision pins as recorded provenance. If updating the manual
tutorial to demonstrate the new PyPI dependency, pin it to a real template commit after this cutover,
then execute the entire script again.

Validate before merging:

```bash
uv lock
uv sync --locked --group dev --group docs
uv run ruff check src tests scripts docs/hooks.py
uv run ruff format --check src tests scripts docs/hooks.py
uv run pytest -q
uv run mkdocs build --strict
uv run python scripts/check_release.py
uv build
uvx --from 'twine>=6' twine check --strict dist/*
wheel_env=$(mktemp -d)
uv venv "$wheel_env"
uv pip install --python "$wheel_env/bin/python" dist/*.whl
"$wheel_env/bin/python" -I tests/wheel_smoke.py "$PWD"
```

`check_release.py` enforces matching exact index pins and verifies that the shared release has files on
PyPI. It rejects Git requirements and inconsistent version pins. The wheel smoke test uses a temporary
local tagged mirror to exercise the installed command, single/all-profile generation and the canonical
update URL without creating a real release tag or fetching a nonexistent release.

## 2. Tag and rehearse on TestPyPI

Candidate generator version: **0.4.0a2**. Once the release changes are merged and CI passes:

```bash
git switch main
git pull --ff-only
git tag v0.4.0a2
git push origin v0.4.0a2
gh workflow run publish.yml --repo McDermottHealthAI/MEDS_algorithm_template \
  --ref v0.4.0a2 -f index=testpypi
gh run list --repo McDermottHealthAI/MEDS_algorithm_template --workflow publish.yml --limit 5
gh run watch RUN_ID --repo McDermottHealthAI/MEDS_algorithm_template --exit-status
```

The workflow verifies the tag/version and reviewed main history, checks the shared release prerequisite,
runs tests and strict docs, and validates the built and installed wheel before upload. It rebuilds the
same tag for each index; it does not reuse the previous workflow's exact distribution bytes.

Install dependencies from PyPI, then install only this distribution from TestPyPI:

```bash
check_env=$(mktemp -d)
uv venv "$check_env"
uv pip install --python "$check_env/bin/python" 'copier>=9.17.1,<10' 'pyyaml>=6'
uv pip install --python "$check_env/bin/python" --no-deps \
  --index-url https://test.pypi.org/simple/ 'meds-algorithm-template==0.4.0a2'
"$check_env/bin/meds-algorithm-template" --version
"$check_env/bin/meds-algorithm-template" "$check_env/generated" --defaults --trust
uv pip install --python "$check_env/bin/python" "$check_env/generated[test]"
"$check_env/bin/meds-algorithm" profiles
uv pip check --python "$check_env/bin/python"
```

Generation alone does not implement an algorithm; the generated completion gates remain in place.
Do not move a published tag to repair a release. Increment the package version and use a new tag.

## 3. Publish the generator to PyPI

After the TestPyPI rehearsal succeeds:

```bash
gh workflow run publish.yml --repo McDermottHealthAI/MEDS_algorithm_template \
  --ref v0.4.0a2 -f index=pypi
# Find and watch the new run, then approve the pypi environment deployment.
# After it succeeds, verify in another clean environment:
pypi_env=$(mktemp -d)
uv venv "$pypi_env"
uv pip install --python "$pypi_env/bin/python" 'meds-algorithm-template==0.4.0a2'
"$pypi_env/bin/meds-algorithm-template" "$pypi_env/generated" --defaults --trust
uv pip install --python "$pypi_env/bin/python" "$pypi_env/generated[test]"
"$pypi_env/bin/meds-algorithm" profiles
uv pip check --python "$pypi_env/bin/python"
```

Verify the PyPI badge and install commands after publication. Future versions retain
the same order whenever the template requires a new shared-package version. Pin both generator and
shared-package versions for reproducible runs.
