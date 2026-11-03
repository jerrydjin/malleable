# Phase 16d: automatic masks, video tracks and scene-local road proposals

Development is **unfrozen**. No held-out clip has been opened. `FROZEN.md`
will be created only after the development targets pass on actual SAM 2.1
outputs and code/config are committed. A missing checkpoint is not a detector
result, and synthetic tests do not establish development success.

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
B is always **same source, different viewpoint**. Another view from that
recording is not independent confirmation.

Runtime packages are pinned in `runtime/requirements.lock.txt`; official SAM 2
source provenance is in `runtime/sam2-source.json`. The checkpoint is external
to Git. Its official host must be permitted by the managed runtime policy, or
an accessible native SAM 2.1 checkpoint must be supplied. No proxy bypass or
unverified replacement weights are used.
