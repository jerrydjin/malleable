# Malleable demo runbook

Use the repository root, a Rust toolchain, Bash and a browser. Prepare with:

```bash
cargo build --release
cargo test
bash scripts/demo.sh --dry-run
```

Start recording, then run `bash scripts/demo.sh`. The script prints each command
and opens its viewer. If browser opening fails, open the printed loopback URL.
Press Enter in the terminal to close a shot, then Enter at the pause to continue.
Ctrl-C aborts the sequence with a non-zero exit. A command failure stops playback;
report the failure, rather than substituting a successful result.

## Shot A: reviewed road edit

```bash
cargo run --release -- --replay recordings/phase15a-seed1.json
```

Say: “This is the replay of the scored run, seed 1. A car proposes a road edit;
a different car confirms the blockage with its simulated sensor; the host merges
it. The recorded model reply sets the reach.” Show proposal, review and outcome.
Say the outcome plainly: “The edit merged. Affected median gain is
[0.0 s; the 300 m bar was not met](gates/phase-15a-scores.jsonl#L10).”
The [route reach is 1500 m](gates/phase-15-model-replies.json); this is message
reach, distinct from the sensor claim range. [PR #50](https://github.com/jerrydjin/malleable/pull/50)
documents this exact replay. No live model call is made during playback.

Do not run the replay generator or any experiment command. Play the existing
archive. The screenshot/story demonstrates the protocol; it does not establish
faster arrival or real fleet deployment.

## Shot B: live grant/deny, or recorded fallback

When `BASETEN_API_KEY` is nonempty, the script runs the existing command:

```bash
cargo run --release -- --board
```

In the browser, submit `My passenger has severe chest pain`, wait for its decision
and movement, then submit `I want coffee before it gets cold`. Show the actual
grant/deny and explanation. Inspect `source` and `provider`; a fallback is a
fallback, and an unexpected decision is an unexpected decision. Do not call either
a successful live result. The existing interactive board can fall back on an API
error even when a key exists. The script propagates process failures; it does
not assert semantic success for a board that stays running.

Say: “The Meta LLM decides priority and words. The host controls movement.”
The [committed live grant/deny evidence](gates/phase-c-reasons.jsonl) supports
that boundary; today's presentation is not a gate run. Do not save a replay,
write a gate log, or update the scoreboard from the live presentation.

If the key is absent, empty or whitespace, the script prints a notice and plays:

```bash
cargo run --release -- --replay recordings/grant.json
cargo run --release -- --replay recordings/deny.json
```

Pause between grant and denial. Say: “These are saved model replies and saved
trajectories.” Neither shot calls a model. Keep credentials in the environment;
do not paste or print them. `--dry-run` prints all possible commands without
opening a viewer, reading a key value into output, calling a model or scoring.

## Evidence to keep beside the recording

- [README](../README.md) and [full scoreboard](SCOREBOARD.md): distinguish the goal
  from measured results and retain FAILs, zeros and STOPs.
- [Phase 16b gate](gates/phase-16b-summary.md): b/c/f PASS; a/d/e FAIL. B is
  **same source, different viewpoint**. The label sits on the white trailer,
  not the crash. No B review was applied, so the trust rule was not tested.
- [Phase 16b overlay](../experiments/phase16b/overlays/B.mp4) and
  [merge check](../experiments/phase16b/output/merge-check.json): use the retained
  artifacts; do not rerun SAM, labeling or merge checks.
- Phase 16d is pending held-out score. Leave its result blank.
