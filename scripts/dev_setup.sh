#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

echo "MailOps development environment is ready."

