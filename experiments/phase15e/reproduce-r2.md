# Reproduce the retained r2 STOP

Run from the repository root with the repository's Rust toolchain/dependency
cache available:

```sh
bash scripts/phase15e.sh
```

The command verifies all 433 retained bytes, runs the four Python ring/clipping
regressions, builds the isolated map/traffic executables, reproduces the passing
map gate, and replays the committed ten-seed **see-only** validity. The large
traffic replay is written to `/tmp/phase15e-validity-replay.json` and compared
byte for byte with `assets/phase15e/validity.json`.

Exit 0 means the committed result reproduces. The experimental result remains
**STOP**, including spillback, unfinished trips and overlap counters. This
verification does not run a RECORD arm, change an input, repair the failed
baseline, or create an efficacy score. Runtime is approximately the same as the
original validity run; London clock/progress output goes to stderr.

For the human-readable result, read STOP-r2.md and
assets/phase15e/validity-summary.json. Full entry/arrival/null/status/final-link
rows are retained in assets/phase15e/validity.json. Historical STOPs 7b4fd03
and 8618bfd, and the v1 map/rejection artifacts, remain in history and in the
retained notes. The scientific code and all declared validity inputs stay
identical to the pre-run commit 20efca7.
