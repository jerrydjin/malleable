# Phase 16d: whole-frame mapping with SAM 2.1 tracking

Status: **UNFROZEN / BLOCKED before SAM inference**. No development target or
held-out result has been scored. Phase 16 remains stopped.

The parent is `phase-16-live-sam` commit
`874c0c869426831fefa0624ed9e395c5c67ab9af` (PR #49). The preservation manifest
[`base-preservation.json`](../../experiments/phase16d/base-preservation.json)
verifies all 543 parent files unchanged, including all 32 `src/` files,
the earlier STOP evidence, Phase 16b masks, preregistration and live-label result.

## Development targets

| Clip / target | Required | Measured run | Edit count | Result |
| --- | --- | --- | --- | --- |
| A: angled red trailer / wedged car | STATIONARY, qualifying lane edit | Not measured | Not measured | NOT RUN |
| A: white trailer ahead | MOVING, no edit | Not measured | Not measured | NOT RUN |
| B: angled red trailer / wedged car | STATIONARY, qualifying lane edit | Not measured | Not measured | NOT RUN |
| B: white trailer ahead | MOVING, no edit | Not measured | Not measured | NOT RUN |
| C: clear-road control | No edit | Not measured | Not measured | NOT RUN |

B is **same source, different viewpoint**. It cannot supply independent sensing
or a second confirmation for A.

## Milestone 1: perception and road-record plumbing

Implemented automatic full-frame grid proposals from the official SAM 2.1 tiny
model and the official SAM 2 video predictor. Stable IDs are associated by mask
geometry across automatic keyframes. Retained masks are propagated, counted and
hashed; capacity overflow fails instead of silently dropping proposals.
Foreground/background role changes are causal and do not rewrite earlier frames.

Road/background optical flow and a quality-gated RANSAC homography estimate
ego-motion outside foreground masks. Lower-object feature motion is measured at
a ground-contact proxy and compared with that homography. Missing motion quality
is UNKNOWN. A co-moving vehicle with little image motion has a nonzero compensated
residual and is MOVING when road motion is observable.

The current, unfrozen configuration requires six consecutive processed frames
for an edit. Processing samples every third native frame; actual cadence is
recorded from the clip FPS. Lane assignment uses explicit camera-relative
perspective hypotheses. Positions are reference-image pixels; metric position
and city-map localization are unknown. Confidence is a heuristic.

The new example uses the existing Muse/Baseten client for label and reach only.
It emits scene-local Proposed `RoadEdit` records and records model/fallback
provenance. It does not review/merge a record or call a vehicle-motion API.
Development label deferral is explicit and cannot qualify for a freeze.

Verification: [Python log](../../experiments/phase16d/runtime/milestone-1-python-tests.log)
has **24 passed, 1 skipped**. The skipped test is actual SAM fixed-clip repeat
determinism; it is **UNMEASURED**, because the native checkpoint is absent.
[Cargo log](../../experiments/phase16d/runtime/milestone-1-cargo-tests.log)
has **218 passed, 0 failed, 3 ignored** across 39 result sections, including seven
new road-record adapter tests. A prior socket-restricted invocation failed seven
loopback-binding tests; its
[log](../../experiments/phase16d/runtime/milestone-1-cargo-sandbox-failure.log)
is retained. The successful invocation granted network access for those loopback
tests and used the same source.

## Runtime blocker

The user authorized adding `dl.fbaipublicfiles.com`, but the current enforced
runtime allowlist still omits it. The normal proxied official-checkpoint HEAD
request returned **HTTP 403**, curl exit **22**; **0 checkpoint bytes** were
downloaded and **0 Phase 16d SAM inference runs** occurred.
[Checkpoint access evidence](../../experiments/phase16d/runtime/checkpoint-access.json)
records the distinction between authorization and applied configuration.

Only read-only Cloud Environment status/diagnostic tools are available here.
The host must be added through the environment configuration workflow. The
inherited proxy and TLS verification remain enabled. Native weights are not
substituted with Phase 16b masks or another model.

## Freeze and held-out scoring

Frozen SHA: **none**. `FROZEN.md` has not been created, because the development
targets have not passed on real inference. No held-out clip has been opened.
Held-out result: **NOT RUN**, **0 attempts**, with no invented PASS/FAIL or
detection count. Required overlays, tracks and edits will be published only
after an actual complete development run; their absence is not a zero result.
