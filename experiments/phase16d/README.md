# Phase 16d: automatic masks, video tracks and scene-local road proposals

Until a committed `FROZEN.md` exists, development is **unfrozen**. The current
status and measured results are in `docs/gates/phase-16d-summary.md`. A freeze
requires the development targets to pass on actual SAM 2.1 outputs and the
code/config to be committed. A missing checkpoint is not a detector result,
and synthetic tests do not establish development success.

The parent is Phase 16b commit `874c0c8`. All parent files, including masks,
preregistration and the live label result, stay unchanged. New work is isolated
under this experiment, its example and tests. No vehicle/physics API is used.

Official SAM 2.1 Hiera Large automatic masks cover a grid over each keyframe. The official SAM 2
video predictor propagates retained masks with deterministic track IDs. Grid
proposals are not a guarantee that every physical object is found; proposal,
filtering, identity-association and tracking counts must be reported.
Geometrically adjacent body/lower-part proposals can supply an automatic box
and two interior positive points to the official image predictor. Secondary
parts use a 0.65 proposal floor and never become independent tracks. A refined
whole mask must pass the original 0.8 IoU / 0.9 stability gates, retain both
parts and their lower extent, and remain within the automatic prompt region.
All prompt geometry comes from SAM masks; evaluation boxes never enter it.

Ego-motion uses road/background features outside foreground-instance masks.
The configured mode fits quality-gated homographies on adjacent processed
frames, then composes them across the motion lag. Every component must pass;
the composed record preserves component evidence and conservative quality.
Large road/sky/background masks remain visible in overlays but do not erase
the road from ego-motion estimation or become lane-blockage proposals.
Motion is measured at object road-contact anchors: mask-centroid motion on
tall trailers has parallax and is not a road-plane stationary test.
If lower-object texture is insufficient, a whole-mask fit can establish MOVING
evidence. It cannot establish STATIONARY or accumulate an emission run.

Configuration is in `config.json`. Initial engineering thresholds are open to
development tuning; they are not held-out results. Frame stride and N refer to
processed frames. Failed ego-motion/feature quality yields UNKNOWN and no edit.
Track motion uses separate confirmation windows: MOVING needs three consecutive
lower-band-supported observations; stationary edits need six consecutive
STATIONARY observations. Fallback-only movement stays provisional. Raw classes,
raw moving runs and supported moving runs remain in the exports. A track with
both confirmed states reports MIXED. These overlapping windows are an engineering
confirmation rule, not independent trials or calibrated probabilities.
Lane IDs are image-based camera-relative hypotheses, not surveyed lane numbers.
Positions state their reference image and pixels; metric/geographic position
is unknown without calibration. The adapter's link 0 is an explicitly
unlocalized scene-local road, not a Potrero or city-map location.

`examples/phase16d_record.rs` uses the existing Muse/Baseten client to label
eligible stationary lane evidence and choose reach. It emits Proposed
`RoadEdit` records with lane, position and heuristic-confidence metadata.
Muse is Meta's LLM; the project is Malleable. The model writes only `label` and
`reach`; a strict local response schema rejects extra fields. The host supplies
blockage, confirmations and status, and `RoadEdit::review` remains the merge
authority. The label model cannot operate vehicle physics.
It receives numerical mapping evidence and image/mask hashes through the
existing text client; it does not receive the images or the evaluation boxes.
An object type inferred from those numbers is not a separate visual observation.
B is always **same source, different viewpoint**. Another view from that
recording is not independent confirmation.

Runtime packages are pinned in `runtime/requirements.lock.txt`; official SAM 2
source provenance is in `runtime/sam2-source.json`. The checkpoint is cached
under `experiments/phase16d/checkpoints/`, which is gitignored. The configured
architecture is Hiera Large, using this official primary URL:

```text
https://huggingface.co/facebook/sam2.1-hiera-large/resolve/main/sam2.1_hiera_large.pt
```

The official fallback serves the same checkpoint:

```text
https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt
```

Acquisition follows HTTPS redirects. The managed runtime allows
`huggingface.co`, its redirected `*.hf.co` download hosts and
`dl.fbaipublicfiles.com`. Inherited proxy settings and verified TLS remain in
use. A transport failure records the actual host and HTTP code. No proxy bypass,
replacement model or simulated SAM output is used.

The current executor is CPU-only with an 8 GiB cgroup memory limit. The current
configuration uses two Torch threads, a full-frame 16 by 16 point grid and prompt
batches of eight. Reducing the prompt batch size retains every grid point.
The tracker keeps one official native video-predictor session, backed by an
on-demand JPEG sequence with a two-image cache and the native FP32 normalization.
The configured temporal cap retains the newest two nonconditioning output
records and two conditioning anchors. Missing older records are skipped by the
official predictor; this deliberately limits temporal context. With the cap
unset, pruning preserves the full native mask-memory/object-pointer horizon.
Packed per-frame masks are written to disk, and loaded RGB/mask sequences cache
eight records each. Tracks are retired through the official `remove_object`
method after twenty consecutive empty processed frames; IDs are never reused.
The 128-object capacity applies to active tracks, and metadata records retirement,
history and peak-active counts. These memory controls are part of the inference
configuration and freeze. Genuine development inference and repeat determinism
must establish the result; the implementation alone supplies no measured score.

## Running development

The installed runtime is `/workspace/.venvs/phase16d`. Checkpoint acquisition is
explicit and uses the configured official primary and fallback URLs:

```sh
/workspace/.venvs/phase16d/bin/python experiments/phase16d/acquire_checkpoint.py
```

It records the actual byte count, native tensor structure and SHA-256, or the
actual transport failure. Existing weights are never overwritten. The tracker
then loads the native architecture strictly and verifies the pinned SAM source.

For Cargo in this workspace, use the installed toolchain and offline cache:

```sh
export PATH=/workspace/.toolchains/rust/rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin:$PATH
export CARGO_HOME=/workspace/.toolchains/rust/cargo
export CARGO_TARGET_DIR=/workspace/.cache/phase16d-cargo
/workspace/.venvs/phase16d/bin/python experiments/phase16d/launch.py --job-id dev-001 dev --run-id dev-001
```

Long runs write both output streams to a durable file. A closed tool terminal
must not break native SAM progress output. Detached job receipts under
`runs/_jobs/` record process IDs and commands without storing environment values.

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
passing target rows and validation evidence. `FROZEN.md` includes freeze UTC,
checkpoint SHA-256, N, the measured A/B/C table, Muse model/fallback provenance
and the complete frozen inference parameter sections. It records the code/config
commit; Git verifies the containing freeze commit before held-out access. The
helper refuses stale results, modified retained evidence, skipped determinism or
deferred labels.

Only after that freeze commit, merge `phase-16d-heldout` into this branch. Verify
the supplied preregistration SHA-256 is
`22410c75b5d1aee3b6eaa7d164b870c2044df365e7d23aa8dd56d623c9f4fd8d`
before filling its `16d commit` line with the frozen SHA. Then run
`heldout-preflight`; it hashes the completed preregistration and the sole supplied
video. Missing inputs return MISSING without reserving an attempt. Run the frozen
algorithm with the exact completed preregistration hash returned by preflight:

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
