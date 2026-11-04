# Phase 16d freeze

Freeze UTC: `2026-11-04T09:52:47.525097+00:00`.

Frozen code/config commit: `0cc372b2907d7e574d87855718ec5b3aa806cb52`.

This file binds the committed code/config above. Its containing freeze commit is verified by Git before held-out access; a file cannot contain the hash of its own commit. Resolve the freeze commit with `git log --diff-filter=A --format=%H -- experiments/phase16d/FROZEN.md`.

Code manifest SHA-256: `15eec52c89c162e3bca6d7421c64a6a9baeacd440786ac5fc5bae1dc78d3c2cd`.

Checkpoint SHA-256: `2647878d5dfa5098f2f8649825738a9345572bae2d4350a2468587ece47dd318`.

N: **6 consecutive processed frames**. Native frame stride: `3`; exact cadence is recorded from each source clip's FPS.

MOVING confirmation: **3 consecutive processed frames**. This separate confirmation window never authorizes a stationary edit.

MOVING lower-band support required: **True**. When required, fallback-only MOVING stays provisional; raw frame classes and runs remain recorded.

Development run: `experiments/phase16d/runs/dev-004-final`. Actual SAM repeat, complete Python suite and Cargo validation passed. See `freeze.json` for committed evidence hashes.

## Measured A/B/C gates

B is **same source, different viewpoint**.

| Target | Required | Measured class | Longest stationary run | Longest moving run | Candidates | Edits | Result |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| red stationary trailer | STATIONARY | STATIONARY | 8 | 2 | 1 | 1 | PASS |
| white moving truck | MOVING | MOVING | 2 | 3 | 0 | 0 | PASS |
| red stationary trailer | STATIONARY | STATIONARY | 9 | 0 | 1 | 1 | PASS |
| white moving truck | MOVING | MOVING | 1 | 3 | 0 | 0 | PASS |
| clear-road control | no edit | clear-road control | NOT RECORDED | NOT RECORDED | 0 | 0 | PASS |

## Muse label and reach provenance

Muse is Meta's LLM. Its output is limited to label and reach; the host controls proposal eligibility and blockage. `RoadEdit::review` remains the merge authority.

| Clip | Track ID | Source | Fallback reason | Provider | Model | Model calls |
| --- | ---: | --- | --- | --- | --- | ---: |
| A | 4 | model | none | baseten | meta-models/muse-spark-open-1026 | 1 |
| B | 4 | model | none | baseten | meta-models/muse-spark-open-1026 | 1 |

## Frozen inference parameters

Lane assignments are camera-relative perspective hypotheses. The complete parameter sections below are copied from the frozen config.

```json
{
  "ego": {
    "block_size": 7,
    "coverage_grid": [
      3,
      2
    ],
    "exclusion_dilate_px": 5,
    "fb_error_px": 1.5,
    "lk_epsilon": 0.01,
    "lk_levels": 4,
    "lk_max_iterations": 30,
    "lk_window_px": 41,
    "max_corner_displacement_fraction": 0.35,
    "max_corners": 1500,
    "min_coverage_fraction": 0.08,
    "min_distance_px": 3,
    "min_inlier_ratio": 0.5,
    "min_inliers": 15,
    "min_matches": 15,
    "min_occupied_cells": 3,
    "mode": "composed_adjacent",
    "quality_level": 0.005,
    "ransac_confidence": 0.995,
    "ransac_max_iterations": 5000,
    "ransac_reprojection_px": 1.5,
    "rng_seed": 0,
    "roi": [
      0.08,
      0.6,
      0.92,
      0.8
    ]
  },
  "emission": {
    "consecutive_frames": 6,
    "duplicate_containment": 0.7
  },
  "frame_stride": 3,
  "lanes": {
    "boundaries": [
      [
        [
          0.5,
          0.48
        ],
        [
          -0.05,
          0.8
        ]
      ],
      [
        [
          0.5,
          0.48
        ],
        [
          0.25,
          0.8
        ]
      ],
      [
        [
          0.5,
          0.48
        ],
        [
          0.6,
          0.8
        ]
      ],
      [
        [
          0.5,
          0.48
        ],
        [
          0.95,
          0.8
        ]
      ],
      [
        [
          0.5,
          0.48
        ],
        [
          1.3,
          0.8
        ]
      ]
    ],
    "boundary_margin_px": 2,
    "method": "camera_relative_perspective_hypothesis",
    "shoulder_width_in_lane_widths": 0.5,
    "valid_y_range": [
      0.5,
      0.85
    ]
  },
  "motion": {
    "affine_confidence": 0.99,
    "affine_max_iterations": 2000,
    "affine_reprojection_px": 1.5,
    "contact_quantile": 0.98,
    "low_texture_fallback": "whole_mask_moving_only",
    "lower_band_fraction": 0.35,
    "mask_erode_px": 1,
    "min_affine_inlier_ratio": 0.5,
    "min_confidence": 0.35,
    "min_ego_motion_px": 1.0,
    "min_features": 4,
    "moving_consecutive_frames": 3,
    "moving_min_relative_residual": 0.6,
    "moving_require_lower_band_support": true,
    "stationary_max_relative_residual": 0.38,
    "stationary_max_residual_px": 2.0
  },
  "motion_lag_frames": 3,
  "sam": {
    "association_containment": 0.75,
    "association_iou": 0.3,
    "association_max_area_ratio": 4.0,
    "box_nms_threshold": 0.7,
    "checkpoint": "experiments/phase16d/checkpoints/sam2.1_hiera_large.pt",
    "decoded_frame_cache_size": 8,
    "deterministic_algorithms": true,
    "device": "cpu",
    "dtype": "float32",
    "duplicate_containment": 0.9,
    "duplicate_iou": 0.85,
    "hood_min_area_fraction": 0.05,
    "hood_min_y_fraction": 0.9,
    "keyframe_interval_frames": 10,
    "mask_threshold": 0.0,
    "max_cond_frames_in_attn": 2,
    "maximum_tracks": 128,
    "minimum_mask_area_px": 96,
    "model_config": "configs/sam2.1/sam2.1_hiera_l.yaml",
    "model_id": "facebook/sam2.1-hiera-large",
    "nonconditioning_history_frames": 2,
    "official_checkpoint_url": "https://huggingface.co/facebook/sam2.1-hiera-large/resolve/main/sam2.1_hiera_large.pt",
    "part_refinement": {
      "area_ratio": [
        0.1,
        0.8
      ],
      "body_aspect_ratio": [
        0.4,
        3.0
      ],
      "enabled": true,
      "lower_height_ratio": [
        0.1,
        0.8
      ],
      "maximum_area_growth": 3.0,
      "maximum_box_expansion_px": 3,
      "maximum_center_offset_width_fraction": 0.2,
      "maximum_gap_height_fraction": 0.12,
      "maximum_gap_px": 4,
      "maximum_lower_extent_loss_px": 3,
      "minimum_horizontal_overlap": 0.7,
      "minimum_source_parts_coverage": 0.8,
      "minimum_stability": 0.9,
      "secondary_pred_iou_threshold": 0.65,
      "stability_score_offset": 1.0,
      "width_ratio": [
        0.5,
        1.5
      ]
    },
    "points_per_batch": 8,
    "points_per_side": 16,
    "pred_iou_threshold": 0.8,
    "retire_after_empty_frames": 20,
    "sky_max_y_fraction": 0.5,
    "source_revision": "2b90b9f5ceec907a1c18123530e92e794ad901a4",
    "stability_threshold": 0.9,
    "stuff_area_fraction": 0.25,
    "stuff_border_count": 3,
    "top_border_fraction": 0.02,
    "torch_threads": 2,
    "video_frame_cache_size": 2
  },
  "seed": 0,
  "working_width": 640
}
```

Commit this freeze before opening the held-out clip. Code/config affecting inference must remain unchanged for its single attempt. No held-out result is asserted by this file.
