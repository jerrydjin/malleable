# Phase 16b

B is the SAME SOURCE, DIFFERENT VIEWPOINT. It is not a second vehicle and not an independent camera.

The previous run stopped before this footage was attached. That stop, verbatim:

STOP — Phase 16b Step 1: no complete licensed footage set was acquired and visually verified in this environment. Wikimedia runtime requests were denied by the proxy (CONNECT 403), and automatic approval review rejected a subsequent access retry. Candidate licence descriptions were found, but A/B/C frames, timestamps, lane obstruction and second viewpoint remain unverified. No SAM inference, model call or merge experiment was run.

This run used the attached file. It did not download from Wikimedia. The original sha256 is `ab4e593ff348713a41ab341cb5fde51de8ef7f7896d139702e63ba4948df31f3`.

## Bars

| Bar | Result | Numbers |
| --- | --- | --- |
| a. A detects by the preregistered rule | FAIL | positive 2/9, longest run 1 (need 3), max lane pixels 16450 (threshold 10000) |
| b. B confirms by the same rule. B is the SAME SOURCE, DIFFERENT VIEWPOINT | PASS | positive 9/9, longest run 9, max lane pixels 13090 |
| c. C produces no detection | PASS | positive 0/15, longest run 0, max lane pixels 2225 |
| d. Merge only with B. A spoof and C do not merge | FAIL | spoof merged False, C merged False, B merged False |
| e. Merged edit has the SPEC hazard keys | FAIL | status Proposed, kind hazard, confirmations 0 |
| f. Label and reach come from a live model reply | FAIL | source fallback, fallback_reason no_key, provider None, model_id None, latency_ms None |

## Detection

Threshold 10000 lane pixels, 3 consecutive sampled frames, stride 10 at 30 fps. Lane polygon area 306000 px.

| Clip | Role | Sampled | Positive | Longest run | Max lane px | Median lane px | Infer sum s | Infer mean s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | proposal | 9 | 2 | 1 | 16450 | 8332 | 21.082 | 2.342 |
| B | SAME SOURCE, DIFFERENT VIEWPOINT | 9 | 9 | 9 | 13090 | 12137 | 21.314 | 2.368 |
| C | negative_control | 15 | 0 | 0 | 2225 | 1786 | 35.949 | 2.397 |

## Models

SAM runtime model id `facebook/sam2.1-hiera-tiny`, Hugging Face revision `de431c4043854a71d8101e17995dfe596bf101a5`, torch `2.15.0+cpu`, transformers `5.22.1`, device `cpu`.

Label client: existing `src/muse.rs` Baseten path, requested model `meta-models/muse-spark-open-1026`. Recorded source `fallback`, fallback_reason `no_key`, provider `None`, model_id `None`, latency_ms `None`.

The stored reply label is what that source produced. On `fallback` / `no_key` the body is `Reply::mock()` from `src/record.rs` (`fallen tree`). That text is not a classification of these frames. The edit's `blocks` value is the preregistered `road`, not the reply's `blocks`. Merge is `RoadEdit::review`. The reply does not set status and does not move a vehicle.

Measured `since_s`: `None`. Value stored on the edit: `12.0`. A produced no qualifying run. RoadEdit requires a since_s, so the edit keeps the test fixture value 12.0. That number is not a measured detection time. link 0 and an empty route are placeholders. This recording is not localized onto the Potrero graph. B review applied: `False`. C review applied: `True`.

A machine with `BASETEN_API_KEY` reruns only the label step, rewrites the edit metadata, reruns the merge check and refreshes this summary:

```sh
experiments/phase16b/run_live_label.sh
```

The script reads the key from the environment and does not print it.

## Sources

[https://commons.wikimedia.org/wiki/File:400_SB_Crash.webm](https://commons.wikimedia.org/wiki/File:400_SB_Crash.webm). Author as listed: Dash. Licence as listed: Commons public-domain statement for an automated recording. That statement was not independently adjudicated.

Per-frame lane pixels and infer times: `experiments/phase16b/output/frames-A.json`, `frames-B.json`, `frames-C.json`. Masks: `experiments/phase16b/masks/`. Overlays: `experiments/phase16b/overlays/`. Edit: `experiments/phase16b/output/edit.json`. Merge check: `experiments/phase16b/output/merge-check.json`.
