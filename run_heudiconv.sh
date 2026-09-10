#!/usr/bin/env bash
set -euo pipefail

# Dispatch to a project's heudiconv conversion script.
#
# Usage: run_heudiconv.sh PROJECT [ARGS...]
#
# PROJECT selects which project-specific script to run (case-insensitive);
# any remaining ARGS are passed through to that script unchanged.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 PROJECT [ARGS...]"
    echo "  PROJECT: osa | wisp"
    exit 1
fi

PROJECT="$1"
shift

case "${PROJECT,,}" in
    osa)
        exec "${SCRIPT_DIR}/OSA/run_heudiconv_osa.sh" "$@"
        ;;
    wisp)
        exec "${SCRIPT_DIR}/WISP/run_heudiconv_wisp.sh" "$@"
        ;;
    *)
        echo "Unknown project: ${PROJECT} (expected: osa | wisp)"
        exit 1
        ;;
esac
