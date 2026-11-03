# Phase 16d: whole-frame mapping

Status: **UNFROZEN**. Official SAM 2.1 Hiera Large weights are acquired and verified.
The first development attempt **FAILED** with `BrokenPipeError` after
**1,881.475 seconds**, before completing A. Target scores and held-out scoring
are **NOT RUN**. Its actual failure is retained in
[`runs/dev-001-large/run.json`](../../experiments/phase16d/runs/dev-001-large/run.json).
The existing runner is continued from `609412b` on `phase-16d-mapping`; PR #51 stays draft.

## Checkpoint and runtime

The primary Hugging Face URL returned HTTP **302**, followed to
`us.aws.cdn.hf.co`, which returned HTTP **200**. The fallback was not needed.
Downloaded bytes: **898,083,611**. Native tensor validation: **903 tensors**,
**224,446,898 elements**. Checkpoint SHA-256:

`2647878d5dfa5098f2f8649825738a9345572bae2d4350a2468587ece47dd318`

The file is cached in gitignored `experiments/phase16d/checkpoints/`.
The [acquisition log](../../experiments/phase16d/runtime/checkpoint-acquisition-20261103.json)
records redirects, bytes, validation and hash. Temporary signed redirect query
parameters are not recorded. The inherited proxy and verified TLS were used.
The earlier checkpoint denial logs remain historical evidence.

Runtime: Python **3.12.14**, torch **2.5.1+cpu**, torchvision **0.20.1+cpu**,
OpenCV **4.11.0**, numpy **1.26.4**, official SAM revision
`2b90b9f5ceec907a1c18123530e92e794ad901a4`. Package dependency check passes.
The enforced cgroup limit is **8 GiB**, with **2 CPUs** and no GPU.
The full **16 × 16** point grid is retained with point batches of **8**.
Native video state and disk-backed frame/mask access are bounded before inference.

Two genuine development-only proposal probes are complete. Broad grid generation
retained **768** native proposals for inspection. Automatic body/chassis pairing
and native box/point refinement produced a complete white-vehicle mask with
**0.896959** predicted IoU, **0.926455** stability and **99.263%** support coverage.
The final **0.8 / 0.9** gates remain unchanged. These are proposal diagnostics,
not scored video results. Prompts were derived from SAM parts before evaluation
annotations were read. Evidence is in
[`runs/amg-refine-A-001/`](../../experiments/phase16d/runs/amg-refine-A-001/).

## Development gates

| Clip / target | Required | Measured class / edits | Result |
| --- | --- | --- | --- |
| A: red trailer / wedged car on right | STATIONARY + qualifying lane/road edit | Not measured | NOT RUN |
| A: white trailer ahead | MOVING + no edit | Not measured | NOT RUN |
| B: red trailer / wedged car on right | STATIONARY + qualifying lane/road edit | Not measured | NOT RUN |
| B: white trailer ahead | MOVING + no edit | Not measured | NOT RUN |
| C: clear-road control | No edit | Not measured | NOT RUN |

B is **same source, different viewpoint**. Extra A/B edits outside the
nonexhaustive target boxes are reported for review. C must have no edit.
Lane assignments are camera-relative hypotheses; positions are image pixels.
N is currently **6 consecutive processed frames**, at native stride **3**.

Muse is Meta's LLM. The existing Baseten client in `src/muse.rs` writes only
`label` and `reach`; additional model fields are rejected. The host determines
motion, lanes and proposal eligibility. Records remain **Proposed**;
`RoadEdit::review` is the merge authority. No physics actions occur.

## Validation and freeze

Focused checks in this session: acquisition routing/log hygiene **3 passed**;
freeze protocol **11 passed**; road-record Rust adapter **7 passed**.
Current fast Python verification: **87 passed, 0 failed, 0 skipped** in
[`milestone-4-unit-tests.log`](../../experiments/phase16d/runtime/milestone-4-unit-tests.log).
The checkpoint-dependent SAM repeat was explicitly excluded from this fast run;
it remains **NOT RUN**. Full current Python/Cargo validation remains pending.
The previous milestone's complete validation logs are retained as history and
are not current inference results.

All **543 parent files** match the preservation manifest, with **0 changes**.
The diff for `src/judge.rs`, `src/schema.rs`, and `src/make_way.rs` against
parent `874c0c8` is empty.

Frozen SHA: **none**. `FROZEN.md` is not created until every development gate,
actual SAM repeat, full tests and live-label attempt pass the freeze checks.
Held-out: **NOT RUN**, **0 attempts**. Its branch and clip remain unopened.
