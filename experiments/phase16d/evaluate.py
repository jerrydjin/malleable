"""Evaluation-only development targets; never imported by perception modules.

Accepts verified, fully loaded tracker bundles and host analyses. This module
does not load a model, open footage, read caches, or change any input. Geometry
chooses the target track before its motion classification or edits are read.
"""
from __future__ import annotations

import hashlib
import json
import math
import re

import numpy as np


B_VIEWPOINT = "same source, different viewpoint"
_HASH = re.compile(r"[0-9a-fA-F]{64}\Z")


def _close(left, right):
    try:
        return math.isfinite(float(left)) and abs(float(left) - float(right)) < 1e-6
    except (TypeError, ValueError):
        return False


def _runs(rows, required):
    """Missing observations, UNKNOWN, role changes and class changes reset runs."""
    longest = {"STATIONARY": 0, "MOVING": 0}
    previous_frame, previous_kind, run = None, None, 0
    for row in sorted(rows, key=lambda value: value["frame"]):
        kind = row["class"] if row.get("role") == "foreground" else "UNKNOWN"
        if kind in longest:
            run = run + 1 if (previous_frame == row["frame"] - 1 and previous_kind == kind) else 1
            longest[kind] = max(longest[kind], run)
        else:
            run = 0
        previous_frame, previous_kind = row["frame"], kind
    stationary = longest["STATIONARY"] >= required
    moving = longest["MOVING"] >= required
    observed = ("MIXED" if stationary and moving else "STATIONARY" if stationary
                else "MOVING" if moving else "UNKNOWN")
    return {"class": observed, "longest_stationary_run": longest["STATIONARY"],
            "longest_moving_run": longest["MOVING"]}


def _role_at(track, frame):
    role = None
    for item in track.get("role_history", []):
        if item["frame_index"] > frame:
            break
        role = item["role"]
    return role


def _clip_errors(clip, analysis, bundle, spec):
    errors = []
    frames, masks, times = bundle.get("frames", []), bundle.get("masks", []), bundle.get("timestamps_s", [])
    count = spec["sampled_frames"]
    metadata = bundle.get("metadata", {})
    decoded = metadata.get("decoded", {})
    if metadata.get("state") != "complete" or metadata.get("owner") != "phase16d.sam2-video-tracker":
        errors.append("tracking_not_complete")
    if metadata.get("identity", {}).get("source_sha256") != spec["source_sha256"]:
        errors.append("source_hash_mismatch")
    if (len(frames) != count or len(masks) != count or len(times) != count
            or analysis.get("frame_count") != count or decoded.get("sampled_frames") != count
            or decoded.get("source_frames_read") != spec["source_frames"]):
        errors.append("incomplete_clip")
    expected_indices = list(range(0, spec["source_frames"], spec["frame_stride"]))
    expected_times = [i / spec["source_fps"] for i in expected_indices]
    if (decoded.get("source_frame_indices") != expected_indices
            or not _close(decoded.get("source_fps"), spec["source_fps"])
            or len(times) != len(expected_times)
            or any(not _close(a, b) for a, b in zip(times, expected_times))
            or decoded.get("timestamps_s") != times):
        errors.append("sampling_or_timestamps_mismatch")
    if decoded.get("source_size_wh") != spec["source_size_wh"]:
        errors.append("source_dimensions_mismatch")
    if analysis.get("clip") != clip or analysis.get("viewpoint_note") != spec["viewpoint_note"]:
        errors.append("analysis_clip_or_viewpoint_mismatch")
    if clip == "B" and spec["viewpoint_note"] != B_VIEWPOINT:
        errors.append("B_viewpoint_note_mismatch")
    expected_pairs = set()
    working_size = decoded.get("working_size_wh")
    for index, frame in enumerate(frames):
        if list(np.asarray(frame).shape[:2][::-1]) != working_size:
            errors.append("working_dimensions_mismatch")
            break
    for index, objects in enumerate(masks):
        for ident, mask in objects.items():
            if list(np.asarray(mask).shape[::-1]) != working_size:
                errors.append("mask_dimensions_mismatch")
            if np.asarray(mask).any():
                expected_pairs.add((index, int(ident)))
    observed_pairs = set()
    for row in analysis.get("observations", []):
        frame, ident = row.get("frame"), row.get("track_id")
        if (type(frame) is not int or type(ident) is not int or frame < 0 or frame >= len(times)):
            errors.append("invalid_observation_identity")
            continue
        pair = (frame, ident)
        if pair in observed_pairs:
            errors.append("duplicate_observation")
        observed_pairs.add(pair)
        if (row.get("clip") != clip or row.get("viewpoint_note") != spec["viewpoint_note"]
                or not _close(row.get("source_s"), spec["source_start_s"] + times[frame])):
            errors.append("observation_source_time_or_viewpoint_mismatch")
        if row.get("class") not in ("STATIONARY", "MOVING", "UNKNOWN"):
            errors.append("invalid_observation_class")
        track = bundle.get("tracks", {}).get(str(ident), {})
        expected_role = _role_at(track, frame)
        if expected_role not in ("foreground", "background_surface") or row.get("role") != expected_role:
            errors.append("observation_causal_role_mismatch")
    if observed_pairs != expected_pairs:
        errors.append("observations_do_not_cover_nonempty_masks")
    if "anchor_frame" in spec:
        anchor = spec["anchor_frame"]
        if anchor >= len(times) or not _close(spec["source_start_s"] + times[anchor], spec["anchor_source_s"]):
            errors.append("annotation_source_time_mismatch")
    return sorted(set(errors))


def _match(bundle, spec, target, policy):
    """Select by fixed anchor geometry, including fragments in edit checks."""
    anchor = spec["anchor_frame"]
    if anchor >= len(bundle.get("masks", [])):
        return {"track_id": None, "related_track_ids": [], "matches": [], "error": "missing_anchor"}
    height, width = np.asarray(bundle["frames"][anchor]).shape[:2]
    source_width, source_height = spec["source_size_wh"]
    box = target["box_xyxy"]
    x0, y0 = math.floor(box[0] * width / source_width), math.floor(box[1] * height / source_height)
    x1, y1 = math.ceil(box[2] * width / source_width), math.ceil(box[3] * height / source_height)
    box_area = (x1 - x0) * (y1 - y0)
    matches = []
    for ident, raw_mask in bundle["masks"][anchor].items():
        mask = np.asarray(raw_mask, dtype=bool)
        area = int(mask.sum())
        if not area:
            continue
        intersection = int(mask[y0:y1, x0:x1].sum())
        inside, coverage = intersection / area, intersection / box_area
        if (inside < policy["minimum_mask_inside_box_fraction"]
                or coverage < policy["minimum_box_coverage"]):
            continue
        ys, xs = np.nonzero(mask)
        mx0, my0, mx1, my1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
        bbox_intersection = max(0, min(mx1, x1) - max(mx0, x0)) * max(0, min(my1, y1) - max(my0, y0))
        iou = bbox_intersection / (box_area + (mx1 - mx0) * (my1 - my0) - bbox_intersection)
        matches.append({"track_id": int(ident), "bbox_iou": float(iou),
                        "mask_inside_box_fraction": inside, "box_coverage": coverage})
    matches.sort(key=lambda value: (-value["bbox_iou"], value["track_id"]))
    primary = [m for m in matches if m["bbox_iou"] >= policy["minimum_primary_bbox_iou"]]
    error = None
    if not primary:
        error = "target_unmatched"
    elif len(primary) > 1 and primary[0]["bbox_iou"] - primary[1]["bbox_iou"] < policy["minimum_primary_score_margin"]:
        error = "target_match_ambiguous"
    return {"track_id": primary[0]["track_id"] if primary and error is None else None,
            "related_track_ids": sorted(m["track_id"] for m in matches),
            "working_box_xyxy": [x0, y0, x1, y1], "matches": matches, "error": error}


def _edit_errors(edit, candidate, analysis, spec, required, working_size):
    errors = []
    if (edit.get("status") != "Proposed" or edit.get("confirmations") != []
            or edit.get("merged_at") is not None or edit.get("map_id") != "unlocalized_clip_road"
            or edit.get("link") != 0 or edit.get("route") != [] or edit.get("blocks") != "lane"):
        errors.append("edit_not_unmerged_scene_local_proposal")
    if edit.get("clip") == "B" and edit.get("viewpoint_note") != B_VIEWPOINT:
        errors.append("B_edit_viewpoint_note_mismatch")
    if candidate is None:
        return errors + ["edit_has_no_unique_host_candidate"]
    evidence = candidate.get("evidence", {})
    for edit_key, evidence_key in (("clip", "clip"), ("track_id", "track_id"), ("lane_blocked", "lane"),
                                   ("position", "position"), ("confidence", "confidence"),
                                   ("since_s", "since_s"), ("stationary_frames", "stationary_frames"),
                                   ("required_stationary_frames", "required_stationary_frames")):
        if edit.get(edit_key) != evidence.get(evidence_key):
            errors.append("edit_host_evidence_mismatch")
    if not re.fullmatch(r"lane_(0|[1-9][0-9]*)", str(evidence.get("lane", ""))):
        errors.append("edit_not_in_travel_lane")
    stationary_frames = evidence.get("stationary_frames")
    if (evidence.get("required_stationary_frames") != required
            or type(stationary_frames) is not int or stationary_frames < required):
        errors.append("edit_temporal_requirement_mismatch")
    if edit.get("confidence_kind") != "heuristic":
        errors.append("edit_confidence_not_heuristic")
    confidence = evidence.get("confidence")
    if not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
        errors.append("invalid_edit_confidence")
    position = evidence.get("position", {})
    reference = position.get("reference_frame")
    pixel_position_valid = (isinstance(working_size, list) and len(working_size) == 2)
    for axis, limit in zip(("x_px", "y_px"), working_size if pixel_position_valid else (0, 0)):
        coordinate = position.get(axis)
        pixel_position_valid = (pixel_position_valid and isinstance(coordinate, (int, float))
                                and math.isfinite(coordinate) and 0 <= coordinate < limit)
    if (position.get("coordinate_system") != "road_reference_image"
            or position.get("metric_position_m") is not None
            or not pixel_position_valid
            or type(reference) is not int or reference < 0 or reference >= spec["sampled_frames"]):
        errors.append("edit_position_not_scene_local")
    elif type(stationary_frames) is int and stationary_frames >= required:
        by_frame = {r["frame"]: r for r in analysis["observations"] if r["track_id"] == edit["track_id"]}
        start = reference - stationary_frames + 1
        supporting = [by_frame.get(i, {}) for i in range(start, reference + 1)]
        if (start < 0 or any(r.get("class") != "STATIONARY" or r.get("role") != "foreground"
                             or r.get("lane") != evidence.get("lane") for r in supporting)
                or not _close(evidence.get("since_s"), spec["source_start_s"] + start * spec["frame_stride"] / spec["source_fps"])):
            errors.append("edit_not_supported_by_stationary_lane_run")
    for key in ("image_sha256", "mask_sha256"):
        value = evidence.get(key, "")
        if not isinstance(value, str) or not _HASH.fullmatch(value) or edit.get("evidence", {}).get(key) != value:
            errors.append("edit_evidence_hash_mismatch")
    return sorted(set(errors))


def evaluate_development(analyses, bundles, records, plan):
    """Return five development rows and an aggregate gate, without side effects.

    ``bundles`` must already be hash-verified by tracker.load_tracking. Labels
    may be explicitly deferred during development; callers must separately
    require a live-label attempt for the final snapshot before freezing.
    """
    if (plan.get("version") != 1 or plan.get("scope") != "development_only"
            or plan.get("evaluation_only") is not True or set(plan.get("clips", {})) != {"A", "B", "C"}
            or type(plan.get("required_consecutive_frames")) is not int or plan["required_consecutive_frames"] <= 0):
        raise ValueError("a supported evaluation-only A/B/C development plan is required")
    required = plan["required_consecutive_frames"]
    input_errors = []
    if set(analyses) != {"A", "B", "C"} or set(bundles) != {"A", "B", "C"}:
        input_errors.append("exactly_three_complete_development_clips_required")
    edits = records.get("edits", [])
    safety_errors = []
    if records.get("merge_reviews_applied") != 0 or records.get("vehicle_motion_actions") != 0:
        safety_errors.append("record_merge_or_motion_action_present")
    if records.get("map_id") != "unlocalized_clip_road":
        safety_errors.append("record_map_not_scene_local")
    if any(e.get("clip") not in plan["clips"] for e in edits):
        safety_errors.append("undeclared_clip_edit")
    clip_checks, rows, unmatched = {}, [], []
    for clip, spec in plan["clips"].items():
        analysis, bundle = analyses.get(clip, {}), bundles.get(clip, {})
        errors = _clip_errors(clip, analysis, bundle, spec)
        clip_checks[clip] = {"pass": not errors, "errors": errors}
        candidates = analysis.get("candidates", [])
        clip_edits = [e for e in edits if e.get("clip") == clip]
        edit_errors = {}
        for edit in clip_edits:
            matching = [c for c in candidates if c.get("evidence", {}).get("track_id") == edit.get("track_id")]
            current_errors = _edit_errors(edit, matching[0] if len(matching) == 1 else None,
                                          analysis, spec, required,
                                          bundle.get("metadata", {}).get("decoded", {}).get("working_size_wh"))
            edit_errors.setdefault(edit.get("track_id"), []).extend(current_errors)
            safety_errors.extend(f"{clip}:{e}" for e in current_errors)
        if not spec["targets"]:
            reasons = list(errors)
            if candidates or clip_edits:
                reasons.append("clear_road_emitted_candidate_or_edit")
            rows.append({"id": "C_clear_road", "clip": clip, "target": "clear-road control",
                         "viewpoint_note": spec["viewpoint_note"], "candidate_count": len(candidates),
                         "edit_count": len(clip_edits), "pass": not reasons, "reasons": reasons})
            continue
        chosen, related_all = {}, set()
        for target in spec["targets"]:
            reasons = list(errors)
            match = _match(bundle, spec, target, plan["matching"]) if not errors else {
                "track_id": None, "related_track_ids": [], "matches": [], "error": "clip_validation_failed"}
            if match["error"]:
                reasons.append(match["error"])
            ident, related = match["track_id"], set(match["related_track_ids"])
            related_all |= related
            observations = [r for r in analysis.get("observations", []) if r.get("track_id") == ident] if ident is not None else []
            runs = _runs(observations, required)
            if runs["class"] != target["expected_class"]:
                reasons.append("target_motion_class_mismatch")
            target_candidates = [c for c in candidates if c.get("evidence", {}).get("track_id") in related]
            target_edits = [e for e in clip_edits if e.get("track_id") in related]
            reasons.extend(reason for edit in target_edits for reason in edit_errors.get(edit.get("track_id"), []))
            expected = target["expected_edits"]
            if len(target_candidates) != expected or len(target_edits) != expected:
                reasons.append("target_candidate_or_edit_count_mismatch")
            row = {"id": target["id"], "clip": clip, "target": target["name"],
                   "viewpoint_note": spec["viewpoint_note"], "expected_class": target["expected_class"],
                   "expected_edits": expected, "matching": match, **runs,
                   "candidate_count": len(target_candidates), "edit_count": len(target_edits),
                   "pass": not reasons, "reasons": sorted(set(reasons))}
            rows.append(row)
            if ident is not None:
                if ident in chosen:
                    for conflict in (chosen[ident], row):
                        conflict["pass"] = False
                        conflict["reasons"].append("same_track_matches_multiple_targets")
                chosen[ident] = row
        unmatched.extend({"clip": clip, "track_id": e.get("track_id"), "id": e.get("id")}
                         for e in clip_edits if e.get("track_id") not in related_all)
    safety_errors = sorted(set(safety_errors))
    return {"version": 1, "scope": "development_only",
            "evaluation_plan_sha256": hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
            "required_consecutive_frames": required,
            "labels_deferred": records.get("labels_deferred"),
            "model_calls": records.get("model_calls"),
            "input_errors": input_errors, "clip_checks": clip_checks,
            "safety_checks": {"pass": not safety_errors, "errors": safety_errors},
            "rows": rows, "unmatched_edits_for_review": unmatched,
            "all_pass": not input_errors and not safety_errors and len(rows) == 5 and all(r["pass"] for r in rows)}
