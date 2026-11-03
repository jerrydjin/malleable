"""Analyze genuine video-predictor masks; propose one edit per tracked instance."""
from collections import Counter, defaultdict
import hashlib
from pathlib import Path

import cv2
import numpy as np

from motion import assign_lane, classify_track, estimate_ego
from tracker import role_at


class EmissionGate:
    """Host-side temporal gate. Labels cannot alter its decisions."""

    def __init__(self, config):
        self.config = config
        self.runs = {}
        self.emitted = set()
        self.suppressed_duplicates = []

    def observe(self, track_id, frame, observation, source_s, current_masks):
        lane = observation.get("lane", "unknown")
        eligible = (observation.get("class") == "STATIONARY"
                    and lane.startswith("lane_")
                    and observation.get("role") == "foreground")
        previous = self.runs.get(track_id)
        if not eligible:
            self.runs.pop(track_id, None)
            return None
        if previous is not None and previous["frame"] == frame - 1 and previous["lane"] == lane:
            run = {**previous, "count": previous["count"] + 1, "frame": frame}
        else:
            run = {"count": 1, "frame": frame, "first_frame": frame,
                   "since_s": source_s, "lane": lane}
        self.runs[track_id] = run
        if run["count"] < int(self.config["emission"]["consecutive_frames"]) or track_id in self.emitted:
            return None
        mask = current_masks[track_id]
        for existing in sorted(self.emitted):
            other = current_masks.get(existing)
            if other is None:
                continue
            denominator = min(int(mask.sum()), int(other.sum()))
            containment = int(np.logical_and(mask, other).sum()) / denominator if denominator else 0.
            if containment >= float(self.config["emission"]["duplicate_containment"]):
                self.emitted.add(track_id)
                self.suppressed_duplicates.append({"track_id": track_id, "existing_track_id": existing,
                                                   "frame": frame, "containment": containment})
                return None
        self.emitted.add(track_id)
        return {"track_id": track_id, **run}


def _png_bytes(rgb_or_mask, mask=False):
    pixels = np.asarray(rgb_or_mask)
    if mask:
        pixels = pixels.astype(np.uint8) * 255
    else:
        pixels = cv2.cvtColor(pixels, cv2.COLOR_RGB2BGR)
    ok, encoded = cv2.imencode(".png", pixels)
    if not ok:
        raise RuntimeError("evidence PNG encoding failed")
    return encoded.tobytes()


def analyze(bundle, config, clip, source_start_s, evidence_dir):
    frames, masks, tracks = bundle["frames"], bundle["masks"], bundle["tracks"]
    if len(frames) != len(masks) or len(frames) != len(bundle["timestamps_s"]):
        raise ValueError("frame/mask/timestamp counts differ")
    evidence_dir = Path(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    lag = int(config["motion_lag_frames"])
    if lag <= 0:
        raise ValueError("motion lag must be positive")
    foreground = []
    for index, (frame, objects) in enumerate(zip(frames, masks)):
        admitted = np.zeros(frame.shape[:2], dtype=bool)
        for ident, mask in objects.items():
            if role_at(tracks[str(ident)], index) == "foreground":
                admitted |= mask
        foreground.append(admitted)
    gate = EmissionGate(config)
    observations, ego_rows, candidates = [], [], []
    viewpoint = config["clips"][clip]["viewpoint_note"] if clip in config["clips"] else "held-out clip"
    for index, (frame, objects) in enumerate(zip(frames, masks)):
        source_s = float(source_start_s) + float(bundle["timestamps_s"][index])
        if index >= lag:
            ego = estimate_ego(frames[index-lag], frame, foreground[index-lag], foreground[index], config)
        else:
            ego = {"H": None, "valid": False, "reason": "insufficient_history", "inliers": 0,
                   "ratio": 0., "reprojection_error": None}
        ego_rows.append({"frame": index, "source_s": source_s, **ego})
        for ident in sorted(objects):
            mask = objects[ident]
            if not mask.any():
                continue
            role = role_at(tracks[str(ident)], index)
            if role != "foreground":
                measurement = {"class": "UNKNOWN", "residual_px": None, "relative_residual": None,
                               "ego_motion_px": None, "observed_motion_px": None,
                               "contact_xy": None, "confidence": 0., "reason": "background_surface",
                               "featurecount": 0}
            elif index < lag or ident not in masks[index-lag] or not masks[index-lag][ident].any():
                measurement = {"class": "UNKNOWN", "residual_px": None, "relative_residual": None,
                               "ego_motion_px": None, "observed_motion_px": None,
                               "contact_xy": None, "confidence": 0., "reason": "no_track_history",
                               "featurecount": 0}
            else:
                measurement = classify_track(frames[index-lag], frame, masks[index-lag][ident],
                                             mask, ego, config)
            lane = assign_lane(measurement.get("contact_xy"), (frame.shape[1], frame.shape[0]), config)
            row = {"clip": clip, "viewpoint_note": viewpoint, "track_id": ident, "frame": index,
                   "source_s": source_s, "role": role, "lane": lane, **measurement}
            observations.append(row)
            event = gate.observe(ident, index, row, source_s, objects)
            if event is None:
                continue
            image = _png_bytes(frame)
            mask_png = _png_bytes(mask, mask=True)
            stem = f"{clip}-{ident}-{index}"
            (evidence_dir / f"{stem}.png").write_bytes(image)
            (evidence_dir / f"{stem}-mask.png").write_bytes(mask_png)
            x, y = measurement["contact_xy"]
            evidence = {
                "clip": clip, "track_id": ident, "lane": lane,
                "position": {"coordinate_system": "road_reference_image", "reference_frame": index,
                             "x_px": float(x), "y_px": float(y), "metric_position_m": None},
                "confidence": float(measurement["confidence"]), "since_s": float(event["since_s"]),
                "stationary_frames": int(event["count"]),
                "required_stationary_frames": int(config["emission"]["consecutive_frames"]),
                "image_sha256": hashlib.sha256(image).hexdigest(),
                "mask_sha256": hashlib.sha256(mask_png).hexdigest(),
            }
            candidates.append({"evidence": evidence})
    grouped = defaultdict(list)
    for row in observations:
        grouped[row["track_id"]].append(row)
    summaries = []
    for ident, rows in sorted(grouped.items()):
        counts = Counter(row["class"] for row in rows)
        longest = {}
        for kind in ("STATIONARY", "MOVING"):
            run = best = 0
            previous = None
            for row in rows:
                if row["class"] == kind:
                    run = run + 1 if previous == row["frame"] - 1 else 1
                else:
                    run = 0
                best = max(best, run)
                previous = row["frame"]
            longest[kind] = best
        best = longest["STATIONARY"]
        final_class = ("STATIONARY" if best >= int(config["emission"]["consecutive_frames"])
                       else "MOVING" if longest["MOVING"] >= int(config["emission"]["consecutive_frames"])
                       else "UNKNOWN")
        residuals = [row["residual_px"] for row in rows if row.get("residual_px") is not None]
        relative = [row["relative_residual"] for row in rows if row.get("relative_residual") is not None]
        lane_counts = Counter(row["lane"] for row in rows if row["lane"] != "unknown")
        lane = min(lane_counts, key=lambda value: (-lane_counts[value], value)) if lane_counts else "unknown"
        summaries.append({
            "clip": clip, "viewpoint_note": viewpoint, "track_id": ident, "role": rows[0]["role"],
            "first_frame": rows[0]["frame"], "last_frame": rows[-1]["frame"],
            "source_start_s": rows[0]["source_s"], "source_end_s": rows[-1]["source_s"],
            "observations": len(rows), "stationary_frames": counts["STATIONARY"],
            "moving_frames": counts["MOVING"], "unknown_frames": counts["UNKNOWN"],
            "longest_stationary_run": best,
            "longest_moving_run": longest["MOVING"],
            "residual_flow_median_px": float(np.median(residuals)) if residuals else None,
            "relative_residual_median": float(np.median(relative)) if relative else None,
            "lane": lane, "class": final_class,
            "label": "background surface" if rows[0]["role"] != "foreground" else "unlabelled object",
            "confidence_median": float(np.median([row["confidence"] for row in rows])),
            "edit_emitted": any(c["evidence"]["track_id"] == ident for c in candidates),
        })
    return {"clip": clip, "viewpoint_note": viewpoint, "frame_count": len(frames),
            "tracks": summaries, "observations": observations, "ego_motion": ego_rows,
            "candidates": candidates, "duplicate_emissions_suppressed": gate.suppressed_duplicates}
