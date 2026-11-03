# Phase 16d: automatic masks, video tracks and scene-local road proposals

Until a committed `FROZEN.md` exists, development is **unfrozen**. The current
status and measured results are in `docs/gates/phase-16d-summary.md`. A freeze
requires the development targets to pass on actual SAM 2.1 outputs and the
code/config to be committed. A missing checkpoint is not a detector result,
and synthetic tests do not establish development success.

The parent is Phase 16b commit `874c0c8`. All parent files, including masks,
preregistration and the live label result, stay unchanged. New work is isolated
under this experiment, its example and tests. No vehicle/physics API is used.

SAM 2.1 automatic masks cover a grid over each keyframe. The official SAM 2
video predictor propagates retained masks with deterministic track IDs. Grid
proposals are not a guarantee that every physical object is found; proposal,
filtering, identity-association and tracking counts must be reported.

Ego-motion uses road/background features outside foreground-instance masks.
Large road/sky/background masks remain visible in overlays but do not erase
the road from ego-motion estimation or become lane-blockage proposals.
Motion is measured at object road-contact anchors: mask-centroid motion on
tall trailers has parallax and is not a road-plane stationary test.

Configuration is in `config.json`. Initial engineering thresholds are open to
development tuning; they are not held-out results. Frame stride and N refer to
processed frames. Failed ego-motion/feature quality yields UNKNOWN and no edit.
Lane IDs are image-based camera-relative hypotheses, not surveyed lane numbers.
Positions state their reference image and pixels; metric/geographic position
is unknown without calibration. The adapter's link 0 is an explicitly
unlocalized scene-local road, not a Potrero or city-map location.

`examples/phase16d_record.rs` uses the existing Muse/Baseten client to label
eligible stationary lane evidence and choose reach. It emits Proposed
`RoadEdit` records with lane, position and heuristic-confidence metadata.
The label model cannot set confirmations/status or operate vehicle physics.
It receives numerical mapping evidence and image/mask hashes through the
existing text client; it does not receive the images or the evaluation boxes.
An object type inferred from those numbers is not a separate visual observation.
B is always **same source, different viewpoint**. Another view from that
recording is not independent confirmation.

Runtime packages are pinned in `runtime/requirements.lock.txt`; official SAM 2
source provenance is in `runtime/sam2-source.json`. The checkpoint is external
to Git. Its official host must be permitted by the managed runtime policy, or
an accessible native SAM 2.1 checkpoint must be supplied. No proxy bypass or
unverified replacement weights are used.

## Running development

The installed runtime is `/workspace/.venvs/phase16d`. Checkpoint acquisition is
explicit and uses the pinned official URL, inherited proxy and verified TLS:

```sh
/workspace/.venvs/phase16d/bin/python experiments/phase16d/acquire_checkpoint.py
```

It records the actual byte count, native tensor structure and SHA-256, or the
actual transport failure. Existing weights are never overwritten. The tracker
then loads the native architecture strictly and verifies the pinned SAM source.
The current managed-runtime host denial must be resolved in network settings
before this command can download weights.

For Cargo in this workspace, use the installed toolchain and offline cache:

```sh
export PATH=/workspace/.toolchains/rust/rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin:$PATH
export CARGO_HOME=/workspace/.toolchains/rust/cargo
export CARGO_TARGET_DIR=/workspace/.cache/phase16d-cargo
/workspace/.venvs/phase16d/bin/python experiments/phase16d/run_mapping.py dev --run-id dev-001
```

The Muse key stays in the environment and is never displayed. `--defer-labels`
is available for early development, records an explicit fallback and cannot
qualify for a freeze. `--clips A` can isolate a development case. Tracking cache
reuse requires verified hashes; changed tracking code/config/inputs require an
explicit `--force-tracking`. Motion-only tuning can reuse genuine masks.
`completed_tracking_clips` counts clips with verified tracking artifacts, including
cache reuse. `tracking.json` retains the original SAM invocation counts/timings;
those counts must not be presented as fresh inference calls in a cached analysis.

Each attempt has its own `runs/<id>/run.json`, including failures and code/input
hashes. A full successful A/B/C run publishes `overlays/{A,B,C}.mp4`, `tracks.csv`
and `edits.jsonl`, with provenance sidecars. Every retained visible mask is drawn;
UNKNOWN is shown separately from MOVING/STATIONARY. Only actual edits are written.
`dev-targets.json` contains separate, manually inspected development annotations;
the perception and label inputs never consume them. Extra A/B edits outside those
nonexhaustive boxes are reported for review. C must have no candidate or edit.

## Freeze, then one held-out attempt

After the five development rows pass with final live-label attempts:

```sh
/workspace/.venvs/phase16d/bin/python experiments/phase16d/validate.py --prefix final-dev
```

Validation runs the full Python and offline Cargo suites. The actual SAM repeat
test must PASS, not SKIP. In this runtime, Cargo's existing loopback tests also
need the execution tool's network permission. Commit all code, config, dev
evidence and validation logs before creating the freeze:

```sh
/workspace/.venvs/phase16d/bin/python experiments/phase16d/run_mapping.py freeze --run-dir experiments/phase16d/runs/dev-001
```

Commit the generated `FROZEN.md` and `freeze.json` before opening held-out inputs.
The freeze binds the code commit, complete code/config manifest, checkpoint hash,
passing target rows and validation evidence. The helper refuses stale results,
modified retained evidence, skipped determinism or deferred labels.

Only then run `heldout-preflight`. Missing Michael-supplied input returns MISSING
without reserving an attempt. A supplied `heldout/prereg.md` and exactly one
video are hashed and exposed for preregistration review. Run the frozen algorithm
with that exact preregistration hash:

```sh
/workspace/.venvs/phase16d/bin/python experiments/phase16d/run_mapping.py heldout-preflight
/workspace/.venvs/phase16d/bin/python experiments/phase16d/run_mapping.py heldout --prereg-sha256 SUPPLIED_PREREG_SHA256
```

An exclusive `heldout/ATTEMPTED.json` is written before inference. Failures and
interruptions consume the attempt; no cache replacement or rerun is allowed.
The frozen runner emits `overlays/heldout.mp4` and numerical artifacts. Apply
the supplied preregistration to those committed numbers and report PASS/FAIL in
the gate summary; the runner records PENDING_PREREG_EVALUATION rather than invent
a scoring rule. Summary/output updates do not require changing frozen code.
Held-out timestamps are local clip seconds; no source offset is invented.
