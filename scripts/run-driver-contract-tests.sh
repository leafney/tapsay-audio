#!/bin/bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$root/scripts/run-driver-contract-tests.py" "$@"
