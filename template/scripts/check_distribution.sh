#!/usr/bin/env bash
# Build wheel from the sdist, then exercise installed artifacts outside the checkout.
set -euo pipefail
if compgen -G 'dist/*' > /dev/null; then
  echo 'dist/ must be empty before checking a release; move previous builds elsewhere.' >&2
  exit 1
fi
verification=$(mktemp -d)
uv build --out-dir "$verification/dist"
uvx --from 'twine>=6' twine check --strict "$verification"/dist/*
uv venv "$verification/env"
wheels=("$verification"/dist/*.whl)
uv pip install --python "$verification/env/bin/python" "${wheels[0]}"
"$verification/env/bin/python" -I tests/wheel_smoke.py
uv pip install --python "$verification/env/bin/python" "${wheels[0]}[orchestration]"
uv pip check --python "$verification/env/bin/python"
"$verification/env/bin/python" -I tests/wheel_smoke.py --orchestration
# Only these checked distributions are uploaded by the publishing job.
mkdir -p dist
cp "$verification"/dist/* dist/
