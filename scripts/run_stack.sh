#!/usr/bin/env bash

set -euo pipefail
_SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${_SCRIPTS_DIR}/_compose_up.sh" "$@"
