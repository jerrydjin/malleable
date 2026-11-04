# Phase 16d: whole-frame mapping

Status: **A/B/C 5 of 5 PASS; UNFROZEN**. Final marked exports and full tests pass. The committed freeze and single held-out run follow next.

## Measured development gates

| Target | Class | Stationary run | Supported moving run | Proposed edits | Result |
| --- | --- | ---: | ---: | ---: | --- |
| A_red_stationary | STATIONARY | 8 | 2 | 1 | PASS |
| A_white_moving | MOVING | 2 | 3 | 0 | PASS |
| B_red_stationary | STATIONARY | 9 | 0 | 1 | PASS |
| B_white_moving | MOVING | 1 | 3 | 0 | PASS |
| C_clear_road | clear road | — | — | 0 | PASS |

B is **same source, different viewpoint**. There are **0 extra A/B edits**. Lane assignments are camera-relative hypotheses; positions are reference-image pixels.

The passing run is [`dev-004-final`](../../experiments/phase16d/runs/dev-004-final/run.json). It reuses hash-verified native SAM outputs from `dev-002-large-refined`. The latter completed 110 sampled frames in 5,007.675 seconds and scored 2/5 under the previous confirmation/threshold settings. No held-out data was used for calibration.

The host requires **6 consecutive STATIONARY frames** for an edit, with absolute residual at most **2 px**, relative residual at most **0.38**, observed ego magnitude at least **1 px** and heuristic confidence at least **0.35**. MOVING track confirmation requires **3 consecutive lower-band-supported observations**. Raw frame classes and both raw/supported moving runs are retained; fallback-only movement remains provisional. Both confirmed states report MIXED. The overlapping windows are not independent statistical trials.

A source-time edit: **13.1 s**, track **4**, `lane_2`. B source-time edit: **15.3 s**, track **4**, `lane_2`. Both remain **Proposed**, with empty confirmations. Both label attempts returned **source:model**, no fallback, via `meta-models/muse-spark-open-1026`. Muse is Meta's LLM and writes only label and reach. `RoadEdit::review` remains the merge authority; **0 merge reviews** and **0 physics actions** occurred.

## Native checkpoint and inference evidence

Official **SAM 2.1 Hiera Large**, **898,083,611 bytes**. Primary Hugging Face acquisition followed HTTP **302 → 200** at `us.aws.cdn.hf.co`. SHA-256:

`2647878d5dfa5098f2f8649825738a9345572bae2d4350a2468587ece47dd318`

The checkpoint cache is gitignored. Native source is pinned at `2b90b9f5ceec907a1c18123530e92e794ad901a4`; Torch is `2.5.1+cpu`. The runtime has an **8 GiB** cgroup limit and **2 CPUs**. Full-frame 16×16 grids use point batches of 8. Automatic body/lower-part prompts yield genuine native image-predictor masks that must pass the original **0.8 predicted-IoU / 0.9 stability** gates before video propagation. Temporal state retains two nonconditioning records and two conditioning anchors.

The following calls belong to the original native tracking run; the passing motion-analysis run reuses their verified masks.

| Clip | Sampled frames | Tracks | AMG calls | Refinement calls / accepted | Video chunks / outputs |
| --- | ---: | ---: | ---: | --- | --- |
| A | 30 | 18 | 3 | 1 / 1 | 3 / 32 |
| B | 30 | 17 | 3 | 1 / 1 | 3 / 32 |
| C | 50 | 19 | 5 | 0 / 0 | 5 / 54 |

Chunk-boundary outputs are counted when returned by SAM; unique sampled-frame counts are shown separately. The complete checkpoint acquisition and two development proposal probes are retained in this experiment. The first baseline failed after **1,881.475 s** with `BrokenPipeError` before completing A; detached jobs and durable log files address terminal closure.

## Validation and freeze

Final Python verification: **118 passed, 0 failed, 0 skipped**, including the real checkpoint-dependent fixed-clip SAM repeat. Cargo: **218 passed, 0 failed, 3 ignored**, exit **0**. See `runtime/validation.json`, `runtime/final-dev-002-python.log` and `runtime/final-dev-002-cargo.log`. An earlier validation was stopped before freeze for explicit edit markers; its partial logs are historical. The final overlays contain A **9 badges / 1 reference point**, B **22 / 1**, C **0 / 0**, derived from real Proposed records.

All **543 parent files** remain unchanged. The diff against parent `874c0c8` for `src/judge.rs`, `src/schema.rs`, and `src/make_way.rs` is empty.

Frozen code SHA: **none**. Freeze commit SHA: **none**. `FROZEN.md` will bind the measured gates, checkpoint, parameters, model/fallback provenance and green full checks.

Held-out: **NOT RUN**, **0 attempts**. Its branch, preregistration and clip remain unopened. The required source preregistration SHA-256 is `22410c75b5d1aee3b6eaa7d164b870c2044df365e7d23aa8dd56d623c9f4fd8d`; it will be verified after committing the freeze.

Outputs: [`overlays/`](../../experiments/phase16d/overlays/), [`tracks.csv`](../../experiments/phase16d/tracks.csv), [`edits.jsonl`](../../experiments/phase16d/edits.jsonl). These are actual development artifacts; the held-out overlay is pending.
