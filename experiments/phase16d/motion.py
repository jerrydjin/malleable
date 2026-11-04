"""Road-plane ego compensation and ground-contact motion classification.

Every engineering threshold is supplied through the root config's ``ego``,
``motion`` and ``lanes`` sections. A quality failure is UNKNOWN, never a zero
motion observation. Confidence is an evidence-quality heuristic, not a
calibrated probability. These functions neither emit edits nor move vehicles.
"""

import cv2
import numpy as np


def _gray(rgb):
    pixels = np.asarray(rgb)
    if pixels.ndim == 2:
        return pixels.astype(np.uint8, copy=False)
    if pixels.ndim != 3 or pixels.shape[2] != 3:
        raise ValueError("expected an RGB or grayscale image")
    return cv2.cvtColor(pixels.astype(np.uint8, copy=False), cv2.COLOR_RGB2GRAY)


def _mask(mask, shape):
    if mask is None:
        return np.zeros(shape, dtype=np.uint8)
    result = np.asarray(mask)
    if result.shape != shape:
        raise ValueError("mask and frame dimensions differ")
    return (result != 0).astype(np.uint8) * 255


def _morph(mask, radius, dilate):
    radius = int(radius)
    if radius <= 0:
        return mask.copy()
    kernel = np.ones((radius * 2 + 1, radius * 2 + 1), dtype=np.uint8)
    return cv2.dilate(mask, kernel) if dilate else cv2.erode(mask, kernel)


def _project(matrix, points):
    points = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    homogeneous = np.column_stack((points, np.ones(len(points))))
    projected = homogeneous @ np.asarray(matrix, dtype=np.float64).T
    if not np.isfinite(projected).all() or np.any(np.abs(projected[:, 2]) <= np.finfo(float).eps):
        raise ValueError("nonfinite or singular projective location")
    return projected[:, :2] / projected[:, 2:3]


def _feature_flow(prev, curr, source_mask, target_mask, ego_cfg):
    points = cv2.goodFeaturesToTrack(
        prev,
        maxCorners=int(ego_cfg["max_corners"]),
        qualityLevel=float(ego_cfg["quality_level"]),
        minDistance=float(ego_cfg["min_distance_px"]),
        blockSize=int(ego_cfg["block_size"]),
        mask=source_mask,
    )
    empty = np.empty((0, 2), dtype=np.float32)
    if points is None:
        return empty, empty, np.empty(0), "no_features"
    params = {
        "winSize": (int(ego_cfg["lk_window_px"]),) * 2,
        "maxLevel": int(ego_cfg["lk_levels"]),
        "criteria": (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
                     int(ego_cfg["lk_max_iterations"]), float(ego_cfg["lk_epsilon"])),
    }
    forward, status, _ = cv2.calcOpticalFlowPyrLK(prev, curr, points, None, **params)
    if forward is None or status is None:
        return empty, empty, np.empty(0), "forward_flow_failed"
    original = points.reshape(-1, 2)
    forward = forward.reshape(-1, 2)
    h, w = curr.shape
    keep = (status.reshape(-1) != 0) & np.isfinite(forward).all(axis=1)
    keep &= ((forward[:, 0] >= 0) & (forward[:, 0] < w)
             & (forward[:, 1] >= 0) & (forward[:, 1] < h))
    indexes = np.flatnonzero(keep)
    if not len(indexes):
        return empty, empty, np.empty(0), "no_forward_matches"
    coords = np.rint(forward[indexes]).astype(int)
    coords[:, 0] = np.clip(coords[:, 0], 0, w - 1)
    coords[:, 1] = np.clip(coords[:, 1], 0, h - 1)
    indexes = indexes[target_mask[coords[:, 1], coords[:, 0]] != 0]
    if not len(indexes):
        return empty, empty, np.empty(0), "matches_outside_target_support"
    backward, backward_status, _ = cv2.calcOpticalFlowPyrLK(
        curr, prev, forward[indexes].reshape(-1, 1, 2), None, **params)
    if backward is None or backward_status is None:
        return empty, empty, np.empty(0), "backward_flow_failed"
    backward = backward.reshape(-1, 2)
    error = np.linalg.norm(backward - original[indexes], axis=1)
    keep = ((backward_status.reshape(-1) != 0) & np.isfinite(backward).all(axis=1)
            & (error <= float(ego_cfg["fb_error_px"])))
    return original[indexes][keep], forward[indexes][keep], error[keep], "ok"


def _ego_failure(reason, **updates):
    result = {"H": None, "valid": False, "inliers": 0, "ratio": 0.0,
              "reprojection_error": None, "reason": reason, "matches": 0,
              "coverage_fraction": 0.0, "occupied_cells": 0}
    result.update(updates)
    return result


def estimate_ego(prev_rgb, curr_rgb, foreground_prev_bool, foreground_curr_bool, cfg):
    """Estimate road H mapping previous working-frame pixels into current pixels.

    Foreground masks must contain admitted object instances, not road/sky stuff
    masks. Homography support is restricted to the configured road ROI.
    """
    params = cfg["ego"]
    prev, curr = _gray(prev_rgb), _gray(curr_rgb)
    if prev.shape != curr.shape:
        return _ego_failure("frame_dimensions_differ")
    h, w = prev.shape
    x0, y0, x1, y1 = (float(v) for v in params["roi"])
    xa, ya = max(0, int(x0 * w)), max(0, int(y0 * h))
    xb, yb = min(w, int(x1 * w)), min(h, int(y1 * h))
    if xb <= xa or yb <= ya:
        return _ego_failure("empty_road_roi")
    roi = np.zeros_like(prev, dtype=np.uint8)
    roi[ya:yb, xa:xb] = 255
    previous_objects = _morph(_mask(foreground_prev_bool, prev.shape), params["exclusion_dilate_px"], True)
    current_objects = _morph(_mask(foreground_curr_bool, curr.shape), params["exclusion_dilate_px"], True)
    source_support = cv2.bitwise_and(roi, cv2.bitwise_not(previous_objects))
    target_support = cv2.bitwise_and(roi, cv2.bitwise_not(current_objects))
    p0, p1, fb, reason = _feature_flow(prev, curr, source_support, target_support, params)
    if len(p0) < int(params["min_matches"]):
        return _ego_failure("too_few_background_matches:" + reason, matches=len(p0))
    cv2.setRNGSeed(int(params["rng_seed"]))
    matrix, inlier_mask = cv2.findHomography(
        p0, p1, cv2.RANSAC, float(params["ransac_reprojection_px"]),
        maxIters=int(params["ransac_max_iterations"]), confidence=float(params["ransac_confidence"]))
    if matrix is None or inlier_mask is None or not np.isfinite(matrix).all():
        return _ego_failure("homography_fit_failed", matches=len(p0))
    inlier_mask = inlier_mask.reshape(-1).astype(bool)
    count = int(inlier_mask.sum())
    ratio = count / len(p0)
    if count < int(params["min_inliers"]) or ratio < float(params["min_inlier_ratio"]):
        return _ego_failure("insufficient_homography_inliers", matches=len(p0), inliers=count, ratio=ratio)
    points = p0[inlier_mask]
    hull = cv2.convexHull(points)
    coverage = float(cv2.contourArea(hull)) / ((xb - xa) * (yb - ya))
    cols, rows = (int(value) for value in params["coverage_grid"])
    cells = {(min(cols - 1, max(0, int((x - xa) / (xb - xa) * cols))),
              min(rows - 1, max(0, int((y - ya) / (yb - ya) * rows)))) for x, y in points}
    quality = {"matches": len(p0), "inliers": count, "ratio": ratio,
               "coverage_fraction": coverage, "occupied_cells": len(cells)}
    if coverage < float(params["min_coverage_fraction"]) or len(cells) < int(params["min_occupied_cells"]):
        return _ego_failure("insufficient_spatial_background_support", **quality)
    try:
        predictions = _project(matrix, points)
        projected_hull = _project(matrix, hull.reshape(-1, 2))
    except ValueError:
        return _ego_failure("singular_homography_projection", **quality)
    error = float(np.median(np.linalg.norm(predictions - p1[inlier_mask], axis=1)))
    before_area = cv2.contourArea(hull, oriented=True)
    after_area = cv2.contourArea(projected_hull.astype(np.float32), oriented=True)
    displacement = np.linalg.norm(projected_hull - hull.reshape(-1, 2), axis=1)
    if (before_area * after_area <= 0 or not np.isfinite(error)
            or float(displacement.max()) > float(params["max_corner_displacement_fraction"]) * np.hypot(w, h)):
        return _ego_failure("implausible_supported_homography", reprojection_error=error, **quality)
    scale = matrix[2, 2]
    if abs(scale) <= np.finfo(float).eps:
        return _ego_failure("singular_homography_normalization", **quality)
    return {"H": (matrix / scale).tolist(), "valid": True, "reprojection_error": error,
            "reason": "ok", "median_forward_backward_error": float(np.median(fb)), **quality}


def compose_ego(steps, start_frame=0):
    """Compose consecutive, quality-passing previous→current road transforms.

    The caller estimates each adjacent pair once. No failed pair is bridged,
    and composition does not promote the individual fits' quality. The summed
    component median pixel errors are a conservative diagnostic, not a new
    reprojection fit on the lagged pair.
    """
    if not steps:
        return _ego_failure("empty_ego_composition", mode="composed_adjacent",
                            component_count=0, components=[])
    components = []
    for offset, step in enumerate(steps):
        component = {"from_frame": int(start_frame) + offset,
                     "to_frame": int(start_frame) + offset + 1, **step}
        # Keep provenance independent of an input list the caller may reuse.
        if step.get("H") is not None:
            matrix = np.asarray(step["H"], dtype=np.float64)
            component["H"] = matrix.tolist() if matrix.shape == (3, 3) and np.isfinite(matrix).all() else None
        components.append(component)
    provenance = {"mode": "composed_adjacent", "component_count": len(components),
                  "from_frame": int(start_frame), "to_frame": int(start_frame) + len(components),
                  "components": components,
                  "quality_aggregation": "minimum_component_matches_inliers_ratio_coverage_and_cells",
                  "reprojection_error_kind": "sum_of_component_median_pixel_errors_not_a_lagged_fit"}
    for offset, component in enumerate(components):
        if not component.get("valid") or component.get("H") is None:
            return _ego_failure("invalid_ego_component:" + str(offset) + ":"
                                + str(component.get("reason", "missing_homography")), **provenance)
    matrix = np.eye(3, dtype=np.float64)
    for offset, component in enumerate(components):
        step_matrix = np.asarray(component["H"], dtype=np.float64)
        if np.linalg.matrix_rank(step_matrix) < 3:
            return _ego_failure("singular_ego_component:" + str(offset), **provenance)
        # Column-vector convention: latest transform multiplies on the left.
        matrix = step_matrix @ matrix
        scale = matrix[2, 2]
        if not np.isfinite(matrix).all() or abs(scale) <= np.finfo(float).eps:
            return _ego_failure("invalid_composed_homography", **provenance)
        matrix = matrix / scale
    error_sum = float(sum(float(step["reprojection_error"]) for step in components))
    if not np.isfinite(error_sum):
        return _ego_failure("nonfinite_component_reprojection_error", **provenance)
    return {"H": matrix.tolist(), "valid": True,
            "reason": "composed_pairwise_road_homographies",
            "matches": min(int(step["matches"]) for step in components),
            "inliers": min(int(step["inliers"]) for step in components),
            "ratio": min(float(step["ratio"]) for step in components),
            "coverage_fraction": min(float(step["coverage_fraction"]) for step in components),
            "occupied_cells": min(int(step["occupied_cells"]) for step in components),
            "reprojection_error": error_sum,
            "component_reprojection_error_sum_px": error_sum,
            "median_forward_backward_error": max(float(step.get("median_forward_backward_error", 0.))
                                                   for step in components),
            "forward_backward_error_kind": "maximum_component_median_pixel_error",
            **provenance}


def classify_residual(observed_flow_xy, ego_flow_xy, cfg, quality=1.0):
    """Classify two contact-anchor flow vectors; all thresholds come from config."""
    params = cfg["motion"]
    observed = np.asarray(observed_flow_xy, dtype=np.float64)
    ego = np.asarray(ego_flow_xy, dtype=np.float64)
    if observed.shape != (2,) or ego.shape != (2,) or not np.isfinite(observed).all() or not np.isfinite(ego).all():
        return {"class": "UNKNOWN", "residual_px": None, "relative_residual": None,
                "ego_motion_px": None, "observed_motion_px": None, "confidence": 0.0,
                "reason": "nonfinite_motion"}
    ego_motion = float(np.linalg.norm(ego))
    residual = float(np.linalg.norm(observed - ego))
    confidence = float(np.clip(quality, 0.0, 1.0)) if np.isfinite(quality) else 0.0
    result = {"class": "UNKNOWN", "residual_px": residual, "relative_residual": None,
              "ego_motion_px": ego_motion, "observed_motion_px": float(np.linalg.norm(observed)),
              "confidence": confidence, "reason": "insufficient_ego_motion"}
    if confidence < float(params["min_confidence"]):
        result["reason"] = "low_motion_quality"
        return result
    if ego_motion < float(params["min_ego_motion_px"]):
        return result
    relative = residual / ego_motion
    result["relative_residual"] = relative
    if residual <= float(params["stationary_max_residual_px"]) and relative <= float(params["stationary_max_relative_residual"]):
        result.update({"class": "STATIONARY", "reason": "matches_road_ego_motion"})
    elif relative >= float(params["moving_min_relative_residual"]):
        result.update({"class": "MOVING", "reason": "nonzero_ego_compensated_motion"})
    else:
        result["reason"] = "ambiguous_ego_compensated_motion"
    return result


def _contact(mask, quantile):
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return None
    y = float(np.quantile(ys, float(quantile)))
    return np.array([float(np.median(xs[ys >= y])), y], dtype=np.float64)


def _track_failure(reason, contact=None, featurecount=0, **updates):
    result = {"class": "UNKNOWN", "residual_px": None, "relative_residual": None,
              "ego_motion_px": None, "observed_motion_px": None,
              "contact_xy": None if contact is None else np.asarray(contact).tolist(),
              "confidence": 0.0, "reason": reason, "featurecount": int(featurecount), "inliers": 0}
    result.update(updates)
    return result


def classify_track(prev_rgb, curr_rgb, prev_mask, curr_mask, ego, cfg):
    """Use lower-instance feature motion at a robust ground-contact proxy.

    Whole-instance SAM masks are required: a mask of a trailer door alone has
    no justified ground-contact proxy and should not be admitted as a vehicle
    instance upstream. No semantic target-specific ROI is used here.
    """
    params = cfg["motion"]
    prev, curr = _gray(prev_rgb), _gray(curr_rgb)
    if prev.shape != curr.shape:
        return _track_failure("frame_dimensions_differ")
    previous_mask, current_mask = _mask(prev_mask, prev.shape), _mask(curr_mask, curr.shape)
    anchor = _contact(previous_mask, params["contact_quantile"])
    current_anchor = _contact(current_mask, params["contact_quantile"])
    if anchor is None or current_anchor is None:
        return _track_failure("empty_object_mask", current_anchor)
    if not ego.get("valid") or ego.get("H") is None:
        return _track_failure("invalid_ego:" + str(ego.get("reason", "missing")), current_anchor)
    fallback_mode = params.get("low_texture_fallback", "disabled")
    if fallback_mode not in ("disabled", "whole_mask_moving_only"):
        raise ValueError("Unsupported low-texture motion fallback")
    full_support = _morph(previous_mask, params["mask_erode_px"], False)
    feature_support = full_support.copy()
    ys, _ = np.nonzero(previous_mask)
    cutoff = float(ys.max()) - float(params["lower_band_fraction"]) * (float(ys.max()) - float(ys.min()) + 1.)
    feature_support[np.arange(prev.shape[0]) < cutoff, :] = 0
    p0, p1, fb, reason = _feature_flow(prev, curr, feature_support, current_mask, cfg["ego"])
    support = {"flow_support": "lower_band", "flow_support_fallback_reason": None,
               "lower_band_featurecount": len(p0), "lower_band_flow_reason": reason,
               "whole_mask_featurecount": None, "flow_support_area_px": int(np.count_nonzero(feature_support)),
               "lower_band_cutoff_y_px": cutoff}
    if len(p0) < int(params["min_features"]) and fallback_mode == "whole_mask_moving_only":
        p0, p1, fb, reason = _feature_flow(prev, curr, full_support, current_mask, cfg["ego"])
        support.update({"flow_support": "whole_mask_fallback",
                        "flow_support_fallback_reason": "lower_band_features_below_minimum",
                        "whole_mask_featurecount": len(p0),
                        "flow_support_area_px": int(np.count_nonzero(full_support))})
    if len(p0) < int(params["min_features"]):
        return _track_failure("too_few_object_features:" + reason, current_anchor, len(p0), **support)
    cv2.setRNGSeed(int(cfg["ego"]["rng_seed"]))
    affine, inlier_mask = cv2.estimateAffinePartial2D(
        p0, p1, method=cv2.RANSAC,
        ransacReprojThreshold=float(params["affine_reprojection_px"]),
        maxIters=int(params["affine_max_iterations"]), confidence=float(params["affine_confidence"]))
    if affine is None or inlier_mask is None or not np.isfinite(affine).all():
        return _track_failure("object_affine_fit_failed", current_anchor, len(p0), **support)
    inliers = inlier_mask.reshape(-1).astype(bool)
    count, ratio = int(inliers.sum()), float(inliers.sum()) / len(p0)
    if count < int(params["min_features"]) or ratio < float(params["min_affine_inlier_ratio"]):
        return _track_failure("insufficient_object_affine_inliers", current_anchor, len(p0), inliers=count, **support)
    fitted = np.column_stack((p0[inliers], np.ones(count))) @ affine.T
    affine_error = float(np.median(np.linalg.norm(fitted - p1[inliers], axis=1)))
    observed_anchor = affine @ np.array([anchor[0], anchor[1], 1.])
    try:
        expected_anchor = _project(ego["H"], anchor)[0]
    except ValueError:
        return _track_failure("invalid_contact_projection", current_anchor, len(p0), inliers=count, **support)
    fit_quality = max(0., 1. - affine_error / float(params["affine_reprojection_px"]))
    quality = min(float(ego.get("ratio", 0.0)), ratio) * fit_quality
    result = classify_residual(observed_anchor - anchor, expected_anchor - anchor, cfg, quality)
    result.update(support)
    result["residual_motion_class"] = result["class"]
    if support["flow_support"] == "whole_mask_fallback" and result["class"] == "STATIONARY":
        # Upper-body features do not establish a physical road-contact fit.
        # Their agreement with H cannot accumulate a stationary emission run.
        result.update({"class": "UNKNOWN", "reason": "whole_mask_fallback_cannot_establish_contact_stationarity"})
    result.update({"contact_xy": observed_anchor.tolist(), "previous_contact_xy": anchor.tolist(),
                   "mask_contact_xy": current_anchor.tolist(), "featurecount": len(p0), "inliers": count,
                   "affine_inlier_ratio": ratio, "affine_reprojection_error": affine_error,
                   "median_forward_backward_error": float(np.median(fb))})
    return result


def assign_lane(contact_xy, size_wh, cfg):
    """Assign a camera-relative lane using configured perspective boundaries.

    Boundaries are normalized endpoint pairs, ordered from left to right.
    Bounded shoulders extend outside the outer boundaries; farther points are
    off-road. A point too close to a boundary or outside the configured vertical
    validity range is unknown. Without a configured shoulder width, legacy
    shoulder-only assignment is preserved.
    """
    if contact_xy is None:
        return "unknown"
    params = cfg["lanes"]
    w, h = (float(value) for value in size_wh)
    x, y = (float(value) for value in contact_xy)
    if not np.isfinite([x, y, w, h]).all() or w <= 0 or h <= 0 or not (0 <= x < w and 0 <= y < h):
        return "unknown"
    low, high = (float(value) for value in params["valid_y_range"])
    if not low <= y / h <= high:
        return "unknown"
    boundaries = []
    for line in params["boundaries"]:
        (x0, y0), (x1, y1) = np.asarray(line, dtype=float)
        if not np.isfinite([x0, y0, x1, y1]).all() or y0 == y1:
            return "unknown"
        boundaries.append(float((x0 + (x1 - x0) * ((y / h - y0) / (y1 - y0))) * w))
    if len(boundaries) < 2 or any(b <= a for a, b in zip(boundaries, boundaries[1:])):
        return "unknown"
    if any(abs(x - boundary) <= float(params["boundary_margin_px"]) for boundary in boundaries):
        return "unknown"
    if x < boundaries[0] or x > boundaries[-1]:
        shoulder_width = params.get("shoulder_width_in_lane_widths")
        if shoulder_width is not None:
            shoulder_width = float(shoulder_width)
            if not np.isfinite(shoulder_width) or shoulder_width < 0:
                return "unknown"
            if x < boundaries[0]:
                distance = boundaries[0] - x
                lane_width = boundaries[1] - boundaries[0]
            else:
                distance = x - boundaries[-1]
                lane_width = boundaries[-1] - boundaries[-2]
            if distance > shoulder_width * lane_width:
                return "off-road"
        return "shoulder"
    for index, (left, right) in enumerate(zip(boundaries, boundaries[1:])):
        if left < x < right:
            return f"lane_{index}"
    return "unknown"


def classify_motion_history(rows, stationary_required, moving_required=None,
                            moving_require_lower_band_support=False):
    """Confirm track history with explicit asymmetric consecutive windows.

    UNKNOWN, missing frames and nonforeground observations reset either raw
    run. Supported MOVING additionally requires explicit lower-band flow in
    every frame; missing support metadata never establishes that support.
    MOVING confirmation never authorizes an edit. Both confirmed states are
    MIXED. Raw observations and runs remain visible, not calibrated confidence.
    """
    moving_required = stationary_required if moving_required is None else moving_required
    if any(type(value) is not int or value <= 0 for value in (stationary_required, moving_required)):
        raise ValueError("Motion confirmation windows must be positive integers")
    if type(moving_require_lower_band_support) is not bool:
        raise ValueError("Moving support requirement must be boolean")
    longest = {"STATIONARY": 0, "MOVING": 0}
    allowed = {"STATIONARY", "MOVING", "UNKNOWN"}
    previous_frame, previous_kind, run = None, None, 0
    supported_run = longest_supported = 0
    for row in sorted(rows, key=lambda value: value["frame"]):
        kind = row["class"] if row.get("role") == "foreground" else "UNKNOWN"
        if kind not in allowed:
            raise ValueError("Unknown per-frame motion class")
        consecutive = previous_frame == row["frame"] - 1
        if kind in longest:
            run = run + 1 if consecutive and previous_kind == kind else 1
            longest[kind] = max(longest[kind], run)
        else:
            run = 0
        if kind == "MOVING" and row.get("flow_support") == "lower_band":
            supported_run = supported_run + 1 if consecutive else 1
            longest_supported = max(longest_supported, supported_run)
        else:
            supported_run = 0
        previous_frame, previous_kind = row["frame"], kind
    stationary = longest["STATIONARY"] >= stationary_required
    confirming_moving_run = longest_supported if moving_require_lower_band_support else longest["MOVING"]
    moving = confirming_moving_run >= moving_required
    observed = ("MIXED" if stationary and moving else "STATIONARY" if stationary
                else "MOVING" if moving else "UNKNOWN")
    return {"class": observed, "longest_stationary_run": longest["STATIONARY"],
            "longest_moving_run": longest["MOVING"],
            "longest_supported_moving_run": longest_supported,
            "required_stationary_motion_frames": stationary_required,
            "required_moving_motion_frames": moving_required,
            "moving_require_lower_band_support": moving_require_lower_band_support,
            "motion_confirmation_policy": "asymmetric_consecutive_windows"}
