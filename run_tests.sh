#!/bin/bash

set -euxo pipefail

uv build --sdist

# ensure dev deps are available for each ephemeral run
for v in 3.10 3.11 3.12 3.13; do
  COVERAGE_FILE=".coverage.$v" \
  uv run -p "$v" --with ".[dev]" -m pytest --cov=pciid --cov-report= # no report now
done

uv run -p 3.13 --with coverage -m coverage combine
uv run -p 3.13 --with coverage -m coverage report -m
uv run -p 3.13 --with coverage -m coverage xml
uv run -p 3.13 --with coverage -m coverage html
