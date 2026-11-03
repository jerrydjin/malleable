# Phase 16b preregistration

This file is committed before any SAM forward pass and before any label-model call. The numeric rules below are not to be edited after masks exist. `prereg.json` is the same constants in machine-readable form. `rules.py` implements the detection rule and is what the tests call.

## Footage

One Commons file, cut locally. Hash `ab4e593ff348713a41ab341cb5fde51de8ef7f7896d139702e63ba4948df31f3` matched the supplied original before the cuts.

| Clip | Source window | Role |
| --- | --- | --- |
| A | 11.0 s for 3.0 s (90 frames at 30 fps) | Approach. Jackknifed trucks block the lanes ahead. This proposes the hazard edit. |
| B | 14.5 s for 3.0 s (90 frames at 30 fps) | SAME SOURCE, DIFFERENT VIEWPOINT. Closer frames of the same recording, not a second vehicle and not an independent camera. Confirmation is B detecting by the rule below. |
| C | 0.0 s for 5.0 s (150 frames at 30 fps) | Clear snowy highway. Expected result: no detection. |

Author as listed: Dash. Licence as listed: the Commons public-domain statement for an automated recording. That statement was not independently adjudicated. Page: https://commons.wikimedia.org/wiki/File:400_SB_Crash.webm

Cuts use `ffmpeg -ss <start> -t <dur> -i 400_SB_Crash.webm -c:v libx264 -pix_fmt yuv420p -an`.

## What was looked at before this registration

Still frames of the original at source times 0.0, 2.5, 5.0, 11.0, 12.5, 14.0, 14.5, 16.0, 16.5 and 17.2 s. No SAM weights were run. The point for A was checked on the rear door of the left trailer at 11.0, 12.5 and 14.0 s. The point for B was checked on the rear door of that same trailer at 14.5, 16.5 and 17.2 s; the door sits in a different place in the frame because the viewpoint has moved. The point for C was checked on empty snow in the travel lane at 0.0, 2.5 and 5.0 s, below the overhead sign.

## SAM prompt

Model id: `facebook/sam2.1-hiera-tiny`. Device `cpu`, dtype `float32`, seed `0`, `torch.set_num_threads(1)`. `torch.use_deterministic_algorithms` stays off; the seed and the thread count are the fixed controls. One positive point per clip, the same pixel on every sampled frame of that clip. `multimask_output` false. Mask threshold `0.0`, then binarize, matching the Phase 15 cache script. The runtime Hugging Face revision and package versions are recorded from the process that runs; they are not chosen from the masks.

| Clip | Point (x, y) |
| --- | --- |
| A | 910, 560 |
| B | 880, 530 |
| C | 980, 620 |

Sample every 10th frame starting at frame 0 (3 Hz). That is 9 frames for A, 9 for B and 15 for C.

## Lane region

The same quadrilateral on every clip, in original 1920×1080 pixels, clockwise from the upper left:

`(780, 520), (1180, 520), (1680, 860), (280, 860)`

Shoelace area: 306000 px. It covers the travel lanes ahead of the dashcam and stops above the hood. It is not refit per clip. Each prompt point lies inside it.

## Detection rule

A sampled frame is positive when the binarized mask has at least **10000** pixels inside the lane polygon. A clip detects when at least **3** consecutive sampled frames are positive (1.0 s at the 3 Hz sample).

10000 is a round count, about 3.3% of the lane polygon. On the 11.0 s inspection frame the in-lane body of the left trailer is visually on the order of 10^4 pixels, and 10000 sits at that order of magnitude. It was not fit to a mask.

B confirms only by this same rule. C is expected not to detect. Those expectations are hypotheses. A miss is a failed bar, not a reason to edit this file.

The evidence frame for the Phase 15 cache file is the sampled frame with the greatest lane-pixel count. The lowest index wins a tie.

## What the label model receives

The user message is one JSON object and nothing else. Its fields are:

- `task`: write only a hazard label and a reach; do not decide merge; do not move a vehicle
- `sam_model_id`
- `threshold_lane_pixels`, `consecutive_required`, `frame_stride`
- `viewpoint_note`: B is the SAME SOURCE, DIFFERENT VIEWPOINT
- `clips[]`: `id`, `role`, `source_window_s`, `prompt_point_xy`, `lane_polygon_xy`, `sampled_frames`, `positive_frames`, `longest_consecutive_positive`, `max_lane_pixels`, `median_lane_pixels`, `detected`

No pixels, no mask bytes, no link ids, no instruction to merge.

The system prompt is the existing Phase 15 sentence in `examples/phase15_gate.rs`:

> Classify evidence and choose communication reach. Return only JSON {"label":string,"blocks":"road"|"lane"|"none","reach":{"scope":"nearby"|"route"|"city","radius_m":number},"rationale":string}. No motion controls, grants, link IDs or extra fields. SAM geometry is evidence, not a calibrated road map.

## Allowed label and reach

Taken from `Reply` and `Reply::validate` in `src/record.rs`. Unknown fields are rejected.

| Field | Allowed |
| --- | --- |
| `label` | nonempty string. Not a closed enum. |
| `blocks` | `road`, `lane`, or `none` |
| `reach.scope` | `nearby`, `route`, or `city` |
| `reach.radius_m` | finite number in `[0, 100000]` |
| `rationale` | nonempty string |

The model reply is stored in full. On the hazard edit, only `label` and `reach` are taken from that reply. `blocks` on the edit is the preregistered value `road` (the trailers occupy the travel lanes). A reply cannot set `status`, cannot merge an edit, and cannot move a vehicle. `RoadEdit::review` remains the only merge.

## Merge trials

Viewpoint slots are integers because `RoadEdit::review` ignores a reviewer whose id equals `author_car`. They are slots in this one recording, not vehicles.

| Slot | Clip |
| --- | --- |
| 1 | A, the author of the proposal |
| 2 | B, the confirming viewpoint |
| 3 | C, the negative control |

- `since_s` is the source time of the first frame of A's earliest run that reaches 3 positive frames.
- B's `at_s` is the source time of the frame on which that run first reaches 3. It must be strictly later than `since_s`.
- `expires_at` is 30.0 s.
- Spoof: the A proposal with no review. It must not merge.
- C: one review from slot 3 at `since_s + 1` with `saw_blockage` equal to whether C detected. The expected detection is false, so this review is expected not to merge. A detection on C is recorded and fails the bars; the review is not rewritten to hide it.
- B: one review from slot 2 with `saw_blockage` true at B's `at_s`. It merges only when B detected.

## Label fallback

`BASETEN_API_KEY` selects the existing client in `src/muse.rs` (`meta-models/muse-spark-open-1026` unless `MODEL_API_MODEL` is set). If the key is absent, the edit metadata is `source: "fallback"` and `fallback_reason: "no_key"`. The reply body is the existing `Reply::mock()`, which is not a classification of this footage. Bar f fails in that case. No model text is invented.
