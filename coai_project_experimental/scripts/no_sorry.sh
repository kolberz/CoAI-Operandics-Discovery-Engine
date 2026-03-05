#!/usr/bin/env bash
set -euo pipefail
# ignore build artifacts and vendored deps
rg -n --hidden --glob '!.lake/**' --glob '!**/.git/**' '\bsorry\b|\badmit\b' CoAI && exit 1 || exit 0
