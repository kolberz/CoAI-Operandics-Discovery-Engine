#!/usr/bin/env bash
set -euo pipefail
lake env lean CoAI/Export/AxiomAudit.lean > ../docs/axiom_report.txt
