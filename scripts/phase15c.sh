#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
build_dir=/tmp/malleable-phase15c-build
if [[ ${1:-} != run ]]; then build_dir=$(python3 experiments/phase15c/materialize.py); fi
[[ -f "$build_dir/Cargo.toml" ]] || { echo 'Build the 15c crate first.' >&2; exit 1; }
export CARGO_TARGET_DIR="$PWD/target/phase15c"
case "${1:?test, build, or run}" in
 test) shift; cargo test --offline --manifest-path "$build_dir/Cargo.toml" "$@" ;;
 build) cargo build --offline --release --manifest-path "$build_dir/Cargo.toml" --example phase15c_gate ;;
 run) shift; cargo run --offline --release --manifest-path "$build_dir/Cargo.toml" --example phase15c_gate -- "$@" ;;
 *) exit 2 ;;
esac
