# Phase 16b: Step 1 STOP

STOP — Phase 16b Step 1: no complete licensed footage set was acquired and visually verified in this environment. Wikimedia runtime requests were denied by the proxy (CONNECT 403), and automatic approval review rejected a subsequent access retry. Candidate licence descriptions were found, but A/B/C frames, timestamps, lane obstruction and second viewpoint remain unverified. No SAM inference, model call or merge experiment was run.

This is an acquisition STOP, not a measured detector result. Licensed candidates were identified; a complete usable set was not acquired. [Sources and licences](../../experiments/phase16b/SOURCES.md), [search/access evidence](../../experiments/phase16b/search-evidence.json), and [machine-readable status](../../experiments/phase16b/status.json) preserve the distinction.

| Bar | Result | Evidence |
| --- | --- | --- |
| a. A detects | FAIL — not measured | No verified A segment; mask areas and detection frame counts unavailable. |
| b. B confirms | FAIL — not measured | No verified B segment or second viewpoint. |
| c. C has no detection | FAIL — not measured | No verified C segment; zero processed frames cannot establish a negative control. |
| d. Only B enables merge | FAIL — not measured | No footage-based merge, C-only or spoof trial run. |
| e. SPEC-shaped merged edit | FAIL — not measured | No phase-16b edit emitted. |
| f. Live label and reach | FAIL — not measured | No live model call or reply; no fallback manufactured. |

The status records **0 acquired media bytes, 0 inspected/processed frames, 0 SAM calls, 0 model calls and 0 phase-16b merge trials**. Mask areas, per-frame timings, model latency and runtime model IDs are **unavailable**, not zero. Requested model IDs are `facebook/sam2.1-hiera-tiny` and `meta-models/muse-spark-open-1026`. No runtime model/package-version claim follows from the retained cache.

The experiment stopped before Step 2. No preregistration, prompts, lane regions, detection thresholds, trimmed clips, masks, overlays, live-output adapter or new detector tests are presented as completed. An accessible licensed set with verified views and timestamps is required before preregistering and running inference.

Read-only integration audit at base `e4ba2a6e9555f99baec8dfaf1ea9c5a6a7766b50`:

- [`src/record.rs::sam_summary`](https://github.com/jerrydjin/malleable/blob/e4ba2a6e9555f99baec8dfaf1ea9c5a6a7766b50/src/record.rs#L253) reads `assets/phase15/sam.json`, checks the requested SAM model, fixed original photograph hash and mask hash. The retained result is a still-image cache; it is not live video evidence.
- [`examples/phase15_gate.rs::live`](https://github.com/jerrydjin/malleable/blob/e4ba2a6e9555f99baec8dfaf1ea9c5a6a7766b50/examples/phase15_gate.rs#L333) already calls `muse::select_talk` / `GeminiChat` with the SAM summary. [`src/muse.rs`](https://github.com/jerrydjin/malleable/blob/e4ba2a6e9555f99baec8dfaf1ea9c5a6a7766b50/src/muse.rs#L216) supplies the requested Baseten/Meta model default. No new client was written and this entry point was not invoked.
- [`Reply::validate`](https://github.com/jerrydjin/malleable/blob/e4ba2a6e9555f99baec8dfaf1ea9c5a6a7766b50/src/record.rs#L34) permits a nonempty label/rationale, `road|lane|none`, `nearby|route|city`, and finite radius in `[0,100000]` metres. Label is not a closed enum in the existing code; a future preregistration must state the actual constraint.
- [`RoadEdit::review`](https://github.com/jerrydjin/malleable/blob/e4ba2a6e9555f99baec8dfaf1ea9c5a6a7766b50/src/record.rs#L119) requires a distinct later reviewer and a positive observation before merging. Model classification alone does not review an edit.
- `docs/SPEC.md` is absent from the requested main base. Its actual [hazard example at `f3f319ab9934aa7e134e449d119826ad2fd24fe1`](https://github.com/jerrydjin/malleable/blob/f3f319ab9934aa7e134e449d119826ad2fd24fe1/docs/SPEC.md#L58) was read without merging an unrelated documentation branch. It is a projection of the isolated v2 message, including `kind: hazard`; schema conformance is unmeasured because no edit was emitted.

Existing guard verification: **6 passed, 0 failed** in the unchanged `tests/road_record.rs`, including distinct later sensor witnesses, rejection of model motion fields and spoof/no-knowledge route checks. [Full retained test output](../../experiments/phase16b/existing-road-record-tests.log). These inherited tests do not substitute for new video detection/confirmation tests or any bar above. No Rust source file changed.

Automatic approval review rejected a subsequent Wikimedia access retry because it repeated a previously denied host using additional network access; the exact rejected action and stated reason are preserved in `search-evidence.json`. No workaround followed it.
