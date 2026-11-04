# Phase 16d: whole-frame mapping

Status: **A/B/C 5 of 5 PASS; FROZEN; held-out FAIL, exactly 1 attempt**. The complete frozen run processed **300 sampled frames / 115 tracks** and emitted **0 candidates / 0 edits**. It missed the required truck-body hit. No post-freeze inference change or rerun occurred.

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

Frozen evidence/code SHA: **`0cc372b2907d7e574d87855718ec5b3aa806cb52`**. Freeze commit SHA: **`d0fcc110e5b5b03b127016270a87c483ee561d77`**. [`FROZEN.md`](../../experiments/phase16d/FROZEN.md) binds the measured gates, checkpoint, parameters, model provenance and green full checks. Frozen inference manifest SHA-256: `15eec52c89c162e3bca6d7421c64a6a9baeacd440786ac5fc5bae1dc78d3c2cd`.

## Held-out score: FAIL, attempt 1

The single frozen process started at **2026-11-04 10:00:47 UTC** and was observed complete at **18:18:59 UTC**. [`score.json`](../../experiments/phase16d/heldout/score.json) records the assessment against the committed preregistration, with hashes of the actual inputs and outputs.

| Preregistered requirement | Actual evidence | Result |
| --- | --- | --- |
| At least one truck-body edit in clip 10.0–28.5 s | **0 hits; 0 candidates; 0 edits** | **FAIL** |
| No edit for a moving vehicle anywhere | **0 moving-vehicle edits** | PASS |
| No edit in clip 0.0–3.0 s | **0 edits** | PASS |
| Paul amendment: no stopped off-travel object labelled blocked travel lane | **0 such edits**, because no edits were emitted | PASS |

The empty emitted set establishes the missed hit directly; no new detector, visual-overlap threshold, or scoring rule was introduced. Evidence: [`records.json`](../../experiments/phase16d/runs/heldout/records.json), [`candidates.json`](../../experiments/phase16d/runs/heldout/candidates.json), and the **0-byte** [`held-out edits.jsonl`](../../experiments/phase16d/runs/heldout/edits.jsonl). Other correct stopped-lane edits: **0**. The earlier Phase 16b clip-1 FAIL remains unchanged.

Native SAM produced **115 tracks**: **93 foreground / 22 background**, with **44 maximum active / 76 retired**. There were **30 AMG calls**, **3 automatic refinement calls / 3 accepted masks**, **506 mask additions**, and **30 video chunks / 329 returned frame outputs**, including boundary repeats across **300 unique sampled frames**. The analysis contains **8,436 observations** and reports **19 MOVING / 96 UNKNOWN / 0 STATIONARY** aggregate tracks. The maximum measured consecutive stationary run was **5**, below frozen **N = 6**; no track qualified for emission. These are algorithm outputs, not a claim that the ground-truth truck moved.

Held-out Muse calls: **0**, because the host produced no eligible candidates; no label or fallback label was produced. The two development live-label attempts above remain **source:model**. Held-out merge reviews and physics actions: **0 / 0**.

The held-out branch was merged only after freeze commit `d0fcc110e5b5b03b127016270a87c483ee561d77`. The original preregistration matches required SHA-256 `22410c75b5d1aee3b6eaa7d164b870c2044df365e7d23aa8dd56d623c9f4fd8d` and is preserved as [`prereg.original.md`](../../experiments/phase16d/heldout/prereg.original.md). Filling only the required frozen-commit placeholder produced bound SHA-256 `7ae67341017f51557a39cda14824534f564ce57ccc7297f4973db3812e4e41bf`; [`prereg-provenance.json`](../../experiments/phase16d/heldout/prereg-provenance.json) records both hashes and the reference-frame timestamp convention before inference. [`ATTEMPTED.json`](../../experiments/phase16d/heldout/ATTEMPTED.json) records the exclusive reservation of **attempt 1**. The frozen inference manifest still matches; no inference code/config changed after freeze.

Held-out footage credit: **BloknotVrn36, CC BY 3.0, via Wikimedia Commons**, as specified in the preregistration.

Outputs: [`overlays/`](../../experiments/phase16d/overlays/) contains all four real H.264 exports: A **30 frames / 3 s**, B **30 / 3 s**, C **50 / 5 s**, held-out **300 / 30 s**. Held-out overlay SHA-256: `45a461664ad4dfa39be46bad8550c0200a44118aedb1417d5f7b49b3c5b06810`; it contains **8,436 actual object drawings / 0 Proposed badges / 0 reference markers**. Combined [`tracks.csv`](../../experiments/phase16d/tracks.csv) contains **169 rows**. Combined [`edits.jsonl`](../../experiments/phase16d/edits.jsonl) contains **2 development records only**, with **0 held-out edits**. All four overlay hashes and the run artifact manifest were independently verified.
