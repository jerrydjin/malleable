"""Automatic SAM part-to-whole prompts, without annotations or motion authority.

A low-confidence part never becomes an independent video track here. It can
only suggest a box and two positive interior points together with an admitted
high-quality mask. The official image predictor must then return a new mask
that passes the original final quality gates and covers both source parts.
"""
from __future__ import annotations

import hashlib
import time

import cv2
import numpy as np


DEFAULTS = {
    "enabled": False,
    "secondary_pred_iou_threshold": 0.65,
    "minimum_stability": 0.9,
    "body_aspect_ratio": [0.4, 3.0],
    "width_ratio": [0.5, 1.5],
    "lower_height_ratio": [0.1, 0.8],
    "area_ratio": [0.1, 0.8],
    "maximum_gap_px": 4,
    "maximum_gap_height_fraction": 0.12,
    "maximum_center_offset_width_fraction": 0.2,
    "minimum_horizontal_overlap": 0.7,
    "minimum_source_parts_coverage": 0.8,
    "maximum_lower_extent_loss_px": 3,
    "maximum_area_growth": 3.0,
    "maximum_box_expansion_px": 3,
    "stability_score_offset": 1.0,
}


def options(sam):
    result = {**DEFAULTS, **sam.get("part_refinement", {})}
    if type(result["enabled"]) is not bool:
        raise ValueError("Part refinement enabled must be boolean")
    for key in ("secondary_pred_iou_threshold", "minimum_stability",
                "minimum_horizontal_overlap", "minimum_source_parts_coverage"):
        if not 0 <= float(result[key]) <= 1:
            raise ValueError("Part refinement probability/fraction is outside [0,1]")
    if result["enabled"] and float(result["secondary_pred_iou_threshold"]) > float(sam["pred_iou_threshold"]):
        raise ValueError("The secondary part floor must not exceed the primary gate")
    for key in ("body_aspect_ratio", "width_ratio", "lower_height_ratio", "area_ratio"):
        low, high = (float(value) for value in result[key])
        if not np.isfinite([low, high]).all() or low <= 0 or high < low:
            raise ValueError("Invalid part refinement ratio interval")
    for key in ("maximum_gap_px", "maximum_gap_height_fraction",
                "maximum_center_offset_width_fraction", "maximum_lower_extent_loss_px",
                "maximum_box_expansion_px", "stability_score_offset"):
        if not np.isfinite(float(result[key])) or float(result[key]) < 0:
            raise ValueError("Invalid nonnegative part refinement limit")
    if not np.isfinite(float(result["maximum_area_growth"])) or float(result["maximum_area_growth"]) < 1:
        raise ValueError("Part refinement maximum area growth must be at least one")
    return result


def automatic_iou_floor(sam):
    """The extra part floor changes prompting, never final mask acceptance."""
    policy = options(sam)
    return (float(policy["secondary_pred_iou_threshold"]) if policy["enabled"]
            else float(sam["pred_iou_threshold"]))


def automatic_stability_floor(sam):
    policy = options(sam)
    return (min(float(policy["minimum_stability"]), float(sam["stability_threshold"]))
            if policy["enabled"] else float(sam["stability_threshold"]))


def _mask(item):
    return np.asarray(item["segmentation"], dtype=bool)


def _box(mask):
    """Half-open pixel bounds, suitable for an image-predictor box prompt."""
    ys, xs = np.nonzero(mask)
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1] if len(xs) else None


def _hash(mask):
    return hashlib.sha256(np.packbits(mask.reshape(-1), bitorder="little").tobytes()).hexdigest()


def _quality(item, iou, stability):
    values = [float(item["predicted_iou"]), float(item["stability_score"])]
    return bool(np.isfinite(values).all() and values[0] >= iou and values[1] >= stability)


def _interior(mask):
    distance = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    _, _, _, point = cv2.minMaxLoc(distance)
    return [int(point[0]), int(point[1])]


def select_pairs(raw, sam, eligible_primary_indices=None):
    """Find mutually unambiguous, vertically adjacent parts over the full image."""
    policy = options(sam)
    allowed = set(range(len(raw))) if eligible_primary_indices is None else set(eligible_primary_indices)
    descriptors = {}
    for index, item in enumerate(raw):
        mask = _mask(item)
        area = int(mask.sum())
        if area >= int(sam["minimum_mask_area_px"]):
            descriptors[index] = {"index": index, "box": _box(mask), "area": area,
                                  "hash": _hash(mask), "mask": mask}
    primary = [index for index in descriptors
               if _quality(raw[index], float(sam["pred_iou_threshold"]), float(sam["stability_threshold"]))]
    secondary = [index for index in descriptors
                 if _quality(raw[index], float(policy["secondary_pred_iou_threshold"]),
                             float(policy["minimum_stability"]))]
    candidates = []
    for body in primary:
        if body not in allowed:
            continue
        a = descriptors[body]
        x0, y0, x1, y1 = a["box"]
        width, height = x1 - x0, y1 - y0
        if not policy["body_aspect_ratio"][0] <= height / width <= policy["body_aspect_ratio"][1]:
            continue
        for lower in secondary:
            if body == lower:
                continue
            b = descriptors[lower]
            X0, Y0, X1, Y1 = b["box"]
            W, H = X1 - X0, Y1 - Y0
            gap = Y0 - y1
            overlap = max(0, min(x1, X1) - max(x0, X0)) / min(width, W)
            if (not 0 <= gap <= max(float(policy["maximum_gap_px"]),
                                    float(policy["maximum_gap_height_fraction"]) * height)
                    or not policy["width_ratio"][0] <= W / width <= policy["width_ratio"][1]
                    or not policy["lower_height_ratio"][0] <= H / height <= policy["lower_height_ratio"][1]
                    or not policy["area_ratio"][0] <= b["area"] / a["area"] <= policy["area_ratio"][1]
                    or abs((X0 + X1) - (x0 + x1)) / 2 > float(policy["maximum_center_offset_width_fraction"]) * width
                    or overlap < float(policy["minimum_horizontal_overlap"])):
                continue
            candidates.append({"body_index": body, "lower_index": lower,
                               "box_xyxy": [min(x0, X0), min(y0, Y0), max(x1, X1), max(y1, Y1)],
                               "positive_points_xy": [_interior(a["mask"]), _interior(b["mask"])],
                               "source_part_mask_sha256": [a["hash"], b["hash"]],
                               "source_parts": [{"raw_index": index, "mask_sha256": descriptors[index]["hash"],
                                                 "bbox_xyxy_half_open": descriptors[index]["box"],
                                                 "predicted_iou": float(raw[index]["predicted_iou"]),
                                                 "stability_score": float(raw[index]["stability_score"])}
                                                for index in (body, lower)],
                               "lower_box_xyxy": b["box"], "vertical_gap_px": gap,
                               "horizontal_overlap_fraction": overlap})
    # Ambiguous pairings cannot silently combine adjacent physical objects.
    body_degree = {index: sum(p["body_index"] == index for p in candidates) for index in primary}
    lower_degree = {index: sum(p["lower_index"] == index for p in candidates) for index in secondary}
    candidates = [pair for pair in candidates if body_degree[pair["body_index"]] == 1
                  and lower_degree[pair["lower_index"]] == 1]
    candidates.sort(key=lambda pair: (pair["box_xyxy"], pair["source_part_mask_sha256"]))
    result, used = [], set()
    for pair in candidates:
        parts = {pair["body_index"], pair["lower_index"]}
        if not used.intersection(parts):
            result.append(pair)
            used.update(parts)
    return primary, secondary, result


def assess_refinement(mask, predicted_iou, stability, pair, raw, sam):
    """Require native quality and retained lower-part support for contact use."""
    policy = options(sam)
    mask = np.asarray(mask, dtype=bool)
    source = _mask(raw[pair["body_index"]]) | _mask(raw[pair["lower_index"]])
    if mask.shape != source.shape:
        raise ValueError("Refinement and source part dimensions differ")
    box, area = _box(mask), int(mask.sum())
    coverage = float((mask & source).sum() / source.sum())
    inside = [bool(mask[int(y), int(x)]) for x, y in pair["positive_points_xy"]]
    reasons = []
    if (not np.isfinite([predicted_iou, stability]).all()
            or predicted_iou < float(sam["pred_iou_threshold"])
            or stability < float(sam["stability_threshold"])):
        reasons.append("native_quality_below_primary_gate")
    if not all(inside):
        reasons.append("source_positive_point_missing")
    if coverage < float(policy["minimum_source_parts_coverage"]):
        reasons.append("insufficient_source_parts_coverage")
    if box is None or box[3] < pair["lower_box_xyxy"][3] - float(policy["maximum_lower_extent_loss_px"]):
        reasons.append("lower_contact_extent_missing")
    if area > float(policy["maximum_area_growth"]) * int(source.sum()):
        reasons.append("excessive_area_growth")
    margin = float(policy["maximum_box_expansion_px"])
    prompt = pair["box_xyxy"]
    if box is not None and any((box[0] < prompt[0] - margin, box[1] < prompt[1] - margin,
                                box[2] > prompt[2] + margin, box[3] > prompt[3] + margin)):
        reasons.append("mask_extends_outside_prompt_region")
    return {"accepted": not reasons, "reasons": reasons, "predicted_iou": float(predicted_iou),
            "stability_score": float(stability), "bbox_xyxy_half_open": box, "area_px": area,
            "source_parts_coverage": coverage, "positive_points_inside": inside,
            "mask_sha256": _hash(mask)}


def refine_keyframe(raw, rgb, image_predictor, sam, eligible_primary_indices=None):
    """Use the genuine native image predictor; this function has no label API."""
    policy = options(sam)
    metadata = {"enabled": policy["enabled"], "generator_returned_mask_count": len(raw),
                "native_predict_calls": 0, "accepted_masks": 0, "pairs": [], "policy": policy,
                "evaluation_boxes_supplied": False,
                "counts_scope": "AMG returned masks after native floor/NMS; primary and secondary counts also meet minimum area; secondary count includes qualifying primary masks",
                "secondary_count_includes_primary": True}
    if not policy["enabled"]:
        metadata.update({"primary_mask_count": sum(
            _quality(item, float(sam["pred_iou_threshold"]), float(sam["stability_threshold"]))
            and int(_mask(item).sum()) >= int(sam["minimum_mask_area_px"]) for item in raw),
                         "secondary_mask_count": sum(
            _quality(item, float(policy["secondary_pred_iou_threshold"]), float(policy["minimum_stability"]))
            and int(_mask(item).sum()) >= int(sam["minimum_mask_area_px"]) for item in raw),
                         "prompt_pair_count": 0, "post_refinement_candidate_count": len(raw)})
        return raw, metadata
    primary, secondary, pairs = select_pairs(raw, sam, eligible_primary_indices)
    metadata.update({"primary_mask_count": len(primary), "secondary_mask_count": len(secondary),
                     "prompt_pair_count": len(pairs)})
    if not pairs:
        metadata["post_refinement_candidate_count"] = len(primary)
        return [raw[index] for index in primary], metadata
    import torch
    from sam2.utils.amg import calculate_stability_score
    replaced, accepted_items = set(), []
    started = time.perf_counter()
    try:
        image_predictor.set_image(rgb)
        for pair in pairs:
            logits, scores, _ = image_predictor.predict(
                point_coords=np.asarray(pair["positive_points_xy"], dtype=np.float32),
                point_labels=np.ones(2, dtype=np.int32), box=np.asarray(pair["box_xyxy"], dtype=np.float32),
                multimask_output=True, return_logits=True)
            metadata["native_predict_calls"] += 1
            stability = calculate_stability_score(
                torch.as_tensor(logits), float(sam["mask_threshold"]),
                float(policy["stability_score_offset"])).detach().cpu().numpy()
            masks = np.asarray(logits) > float(sam["mask_threshold"])
            assessed = [assess_refinement(mask, float(scores[index]), float(stability[index]), pair, raw, sam)
                        for index, mask in enumerate(masks)]
            choices = [index for index, result in enumerate(assessed) if result["accepted"]]
            selected = (min(choices, key=lambda index: (-assessed[index]["predicted_iou"],
                                                        -assessed[index]["stability_score"],
                                                        -assessed[index]["area_px"], assessed[index]["mask_sha256"]))
                        if choices else None)
            provenance = {"kind": "automatic_part_prompt_native_SAM2ImagePredictor",
                          "box_convention": "half_open_pixels", **pair,
                          "multimask_candidates": assessed, "selected_multimask_index": selected}
            metadata["pairs"].append(provenance)
            if selected is None:
                continue
            result = assessed[selected]
            accepted_items.append({"segmentation": masks[selected], "predicted_iou": result["predicted_iou"],
                                   "stability_score": result["stability_score"],
                                   "point_coords": pair["positive_points_xy"], "proposal_provenance": provenance})
            replaced.update((pair["body_index"], pair["lower_index"]))
            metadata["accepted_masks"] += 1
    finally:
        image_predictor.reset_predictor()
    metadata["elapsed_s"] = time.perf_counter() - started
    result = [raw[index] for index in primary if index not in replaced] + accepted_items
    metadata["post_refinement_candidate_count"] = len(result)
    return result, metadata
