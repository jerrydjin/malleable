#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
TZ=Europe/London date >&2
build_dir=/tmp/malleable-phase15e-build
case "${1:-reproduce}" in
 build|test) build_dir=$(python3 experiments/phase15e/materialize.py);;
esac
export CARGO_TARGET_DIR="$PWD/target/phase15e"
case "${1:-reproduce}" in
 import) python3 experiments/phase15e/import_boundary.py --boundary ;;
 build) cargo build --offline --release --manifest-path "$build_dir/Cargo.toml" --example phase15e_gate ;;
 test) shift; cargo test --offline --manifest-path "$build_dir/Cargo.toml" "$@" ;;
 run) shift; cargo run --offline --release --manifest-path "$build_dir/Cargo.toml" --example phase15e_gate -- "$@" ;;
 reproduce)
  python3 experiments/phase15e/verify.py
  python3 -m unittest discover -s experiments/phase15e -p 'test_*.py'
  bash "$0" build
  bash "$0" run part=map-check > /tmp/phase15e-map-replay.json
  if [[ -f assets/phase15e/map-validity.json ]]; then cmp assets/phase15e/map-validity.json /tmp/phase15e-map-replay.json; fi
  cat /tmp/phase15e-map-replay.json
  ;;
 *) exit 2 ;;
esac
