#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
TZ=Europe/London date >&2
export CARGO_TARGET_DIR="$PWD/target/phase15e"
if [[ ${1:-} == build ]]; then
 build_dir=$(python3 experiments/phase15e/materialize.py)
 cargo build --offline --release --manifest-path "$build_dir/Cargo.toml" --example phase15e_traffic
else
 cargo run --offline --release --manifest-path /tmp/malleable-phase15e-build/Cargo.toml --example phase15e_traffic -- "$@"
fi
