#!/usr/bin/env bash

set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"

command -v docker >/dev/null || { echo "ERROR: docker not found" >&2; exit 1; }

cd "${FIN_US_INTEGRATE_ROOT}"
exec docker compose up --build "$@"
