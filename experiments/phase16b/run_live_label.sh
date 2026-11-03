#!/bin/sh
# Rerun only the hazard label/reach step through the existing Baseten client.
# BASETEN_API_KEY is read from the environment. This script never prints it.
set -eu
cd "$(dirname "$0")/../.."
if [ -z "${BASETEN_API_KEY:-}" ]; then
  echo "BASETEN_API_KEY is unset; recording source=fallback fallback_reason=no_key" >&2
fi
unset MALLEABLE_SAM_CACHE || true
export MALLEABLE_LABEL_USER="experiments/phase16b/output/detection-summary.json"
export MALLEABLE_REPLY_OUT="experiments/phase16b/output/label.json"
export PHASE16B_WRITE=1
cargo run --offline --example phase15_gate -- part=live
python3 experiments/phase16b/apply_label.py
