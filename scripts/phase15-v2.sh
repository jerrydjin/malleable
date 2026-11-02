#!/usr/bin/env bash
# v1 stays byte-identical; v2 is compiled only in this generated crate.
set -euo pipefail
cd "$(dirname "$0")/.."
build_dir=/tmp/malleable-phase15-v2-build
if [[ ${1:-} != run ]]; then build_dir=$(python3 experiments/phase15-v2/materialize.py); fi
[[ -f "$build_dir/Cargo.toml" ]] || { echo 'Build the v2 crate first.' >&2; exit 1; }
export CARGO_TARGET_DIR="$PWD/target/phase15-v2"
case "${1:?test, build, or run}" in
  test) shift; cargo test --offline --manifest-path "$build_dir/Cargo.toml" "$@" ;;
  build) cargo build --offline --release --manifest-path "$build_dir/Cargo.toml" --example phase15_v2_gate ;;
  run) shift; cargo run --offline --release --manifest-path "$build_dir/Cargo.toml" --example phase15_v2_gate -- "$@" ;;
  *) exit 2;;
esac
