"""Synthetic evaluation fixtures only; no footage, SAM, model client or network."""
import copy
import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluate import B_VIEWPOINT, evaluate_development


PLAN = json.loads((Path(__file__).resolve().parents[1] / "dev-targets.json").read_text())


def fixture():
    """Perfect synthetic masks at one tenth of annotation resolution."""
    plan = copy.deepcopy(PLAN)
    analyses, bundles = {}, {}
    records = {"version": 1, "map_id": "unlocalized_clip_road", "model_calls": 0,
               "labels_deferred": True, "edits": [], "abstentions": [],
               "merge_reviews_applied": 0, "vehicle_motion_actions": 0}
    for clip, spec in plan["clips"].items():
        count = spec["sampled_frames"]
        times = [i / 10 for i in range(count)]
        objects = {}
        for ident, target in enumerate(spec["targets"], 1):
            x0, y0, x1, y1 = target["box_xyxy"]
            mask = np.zeros((108, 192), dtype=bool)
            mask[int(y0 // 10):int(np.ceil(y1 / 10)), int(x0 // 10):int(np.ceil(x1 / 10))] = True
            objects[ident] = mask
        bundles[clip] = {
            "frames": [np.zeros((108, 192, 3), dtype=np.uint8) for _ in range(count)],
            "masks": [{k: m.copy() for k, m in objects.items()} for _ in range(count)],
            "tracks": {str(k): {"role_history": [{"frame_index": 0, "role": "foreground"}]} for k in objects},
            "timestamps_s": times,
            "metadata": {"owner": "phase16d.sam2-video-tracker", "state": "complete",
                         "identity": {"source_sha256": spec["source_sha256"]},
                         "decoded": {"source_fps": 30, "source_size_wh": [1920, 1080],
                                     "working_size_wh": [192, 108], "sampled_frames": count,
                                     "source_frames_read": spec["source_frames"],
                                     "source_frame_indices": list(range(0, spec["source_frames"], 3)),
                                     "timestamps_s": times.copy()}},
        }
        analyses[clip] = {"clip": clip, "viewpoint_note": spec["viewpoint_note"], "frame_count": count,
                          "observations": [], "candidates": []}
        for frame in range(count):
            for ident, target in enumerate(spec["targets"], 1):
                analyses[clip]["observations"].append({
                    "clip": clip, "viewpoint_note": spec["viewpoint_note"], "track_id": ident,
                    "frame": frame, "source_s": spec["source_start_s"] + times[frame],
                    "role": "foreground", "class": target["expected_class"] if frame >= 3 else "UNKNOWN",
                    "flow_support": "lower_band",
                    "lane": "lane_1" if ident == 1 else "lane_0"})
        if spec["targets"]:
            add_edit(clip, 1, analyses, records, plan)
    return analyses, bundles, records, plan


def add_edit(clip, ident, analyses, records, plan):
    spec = plan["clips"][clip]
    evidence = {
        "clip": clip, "track_id": ident, "lane": "lane_1" if ident == 1 else "lane_0",
        "position": {"coordinate_system": "road_reference_image", "reference_frame": 8,
                     "x_px": 110., "y_px": 65., "metric_position_m": None},
        "confidence": .7, "since_s": spec["source_start_s"] + .3,
        "stationary_frames": 6, "required_stationary_frames": 6,
        "image_sha256": "1" * 64, "mask_sha256": "2" * 64,
    }
    analyses[clip]["candidates"].append({"evidence": evidence})
    records["edits"].append({
        "id": f"phase16d:{clip}:{ident}", "clip": clip, "track_id": ident,
        "viewpoint_note": B_VIEWPOINT if clip == "B" else "A/C development clip",
        "map_id": "unlocalized_clip_road", "link": 0, "route": [], "blocks": "lane",
        "status": "Proposed", "confirmations": [], "merged_at": None,
        "position": copy.deepcopy(evidence["position"]), "lane_blocked": evidence["lane"],
        "confidence": .7, "confidence_kind": "heuristic", "since_s": evidence["since_s"],
        "stationary_frames": 6, "required_stationary_frames": 6,
        "evidence": {"image_sha256": "1" * 64, "mask_sha256": "2" * 64,
                     "label": "unknown stationary lane object"},
        "label_provenance": {"source": "fallback", "fallback_reason": "dev_label_deferred"},
    })


class DevelopmentEvaluationTests(unittest.TestCase):
    def evaluate(self, data):
        return evaluate_development(*data)

    def row(self, output, ident):
        return next(row for row in output["rows"] if row["id"] == ident)

    def test_complete_five_targets_with_scaled_geometry_and_source_offsets(self):
        output = self.evaluate(fixture())
        self.assertTrue(output["all_pass"], output)
        self.assertEqual(len(output["rows"]), 5)
        self.assertEqual(self.row(output, "A_red_stationary")["matching"]["working_box_xyxy"], [100, 48, 120, 68])
        self.assertEqual(self.row(output, "B_white_moving")["viewpoint_note"], B_VIEWPOINT)
        self.assertTrue(output["labels_deferred"])
        json.dumps(output, allow_nan=False)

    def test_one_moving_frame_cannot_pass_moving_target(self):
        data = fixture()
        for row in data[0]["A"]["observations"]:
            if row["track_id"] == 2:
                row["class"] = "MOVING" if row["frame"] == 20 else "UNKNOWN"
        output = self.evaluate(data)
        row = self.row(output, "A_white_moving")
        self.assertFalse(row["pass"])
        self.assertEqual(row["longest_moving_run"], 1)
        self.assertEqual(row["class"], "UNKNOWN")

    def test_missing_masks_reset_runs_without_becoming_sampling_gaps(self):
        data = fixture()
        moving_required = data[3].get("required_moving_consecutive_frames", data[3]["required_consecutive_frames"])
        missing = set(range(3, data[3]["clips"]["A"]["sampled_frames"], moving_required))
        for frame in missing:
            del data[1]["A"]["masks"][frame][2]
        data[0]["A"]["observations"] = [r for r in data[0]["A"]["observations"]
                                                 if not (r["track_id"] == 2 and r["frame"] in missing)]
        output = self.evaluate(data)
        self.assertTrue(output["clip_checks"]["A"]["pass"])
        self.assertEqual(self.row(output, "A_white_moving")["longest_moving_run"], moving_required - 1)
        self.assertFalse(output["all_pass"])

    def test_two_strong_incompatible_runs_are_mixed(self):
        data = fixture()
        for row in data[0]["A"]["observations"]:
            if row["track_id"] == 1 and 10 <= row["frame"] < 16:
                row["class"] = "MOVING"
        output = self.evaluate(data)
        self.assertEqual(self.row(output, "A_red_stationary")["class"], "MIXED")
        self.assertFalse(self.row(output, "A_red_stationary")["pass"])

    def test_ambiguous_geometry_cannot_select_by_desired_class(self):
        data = fixture()
        for frame in range(30):
            data[1]["A"]["masks"][frame][3] = data[1]["A"]["masks"][frame][1].copy()
        data[1]["A"]["tracks"]["3"] = {"role_history": [{"frame_index": 0, "role": "foreground"}]}
        duplicate = [dict(r, track_id=3, **{"class": "MOVING"})
                     for r in data[0]["A"]["observations"] if r["track_id"] == 1]
        data[0]["A"]["observations"].extend(duplicate)
        output = self.evaluate(data)
        self.assertIn("target_match_ambiguous", self.row(output, "A_red_stationary")["reasons"])
        self.assertIsNone(self.row(output, "A_red_stationary")["matching"]["track_id"])

    def test_unmatched_target_fails_even_with_correct_track_class(self):
        data = fixture()
        del data[1]["A"]["masks"][20][1]
        data[0]["A"]["observations"] = [r for r in data[0]["A"]["observations"]
                                                 if not (r["track_id"] == 1 and r["frame"] == 20)]
        output = self.evaluate(data)
        self.assertIn("target_unmatched", self.row(output, "A_red_stationary")["reasons"])

    def test_false_edit_on_white_fragment_cannot_hide_behind_moving_whole_mask(self):
        data = fixture()
        for frame in range(30):
            mask = np.zeros((108, 192), dtype=bool)
            mask[50:59, 86:94] = True
            data[1]["A"]["masks"][frame][3] = mask
        data[1]["A"]["tracks"]["3"] = {"role_history": [{"frame_index": 0, "role": "foreground"}]}
        data[0]["A"]["observations"].extend(
            dict(r, track_id=3, **{"class": "STATIONARY" if r["frame"] >= 3 else "UNKNOWN"})
            for r in list(data[0]["A"]["observations"]) if r["track_id"] == 2)
        add_edit("A", 3, data[0], data[2], data[3])
        output = self.evaluate(data)
        white = self.row(output, "A_white_moving")
        self.assertEqual(white["class"], "MOVING")
        self.assertEqual(white["matching"]["track_id"], 2)
        self.assertEqual(white["matching"]["related_track_ids"], [2, 3])
        self.assertEqual(white["edit_count"], 1)
        self.assertFalse(white["pass"])

    def test_empty_or_partial_clear_control_cannot_pass(self):
        for count in (0, 25):
            with self.subTest(count=count):
                data = fixture()
                bundle = data[1]["C"]
                for key in ("frames", "masks", "timestamps_s"):
                    bundle[key] = bundle[key][:count]
                data[0]["C"]["frame_count"] = count
                output = self.evaluate(data)
                self.assertFalse(self.row(output, "C_clear_road")["pass"])
                self.assertIn("incomplete_clip", output["clip_checks"]["C"]["errors"])

    def test_clear_control_candidate_is_failure_even_when_adapter_abstains(self):
        data = fixture()
        data[0]["C"]["candidates"] = [{"evidence": {"track_id": 77}}]
        output = self.evaluate(data)
        self.assertFalse(self.row(output, "C_clear_road")["pass"])

    def test_wrong_source_offset_or_duplicate_observation_fails(self):
        data = fixture()
        data[0]["A"]["observations"][0]["source_s"] -= 11
        data[0]["B"]["observations"].append(copy.deepcopy(data[0]["B"]["observations"][0]))
        output = self.evaluate(data)
        self.assertIn("observation_source_time_or_viewpoint_mismatch", output["clip_checks"]["A"]["errors"])
        self.assertIn("duplicate_observation", output["clip_checks"]["B"]["errors"])
        self.assertFalse(output["all_pass"])

    def test_label_cannot_merge_or_rewrite_host_mapping(self):
        for field, value, reason in (("status", "Merged", "edit_not_unmerged_scene_local_proposal"),
                                     ("lane_blocked", "lane_8", "edit_host_evidence_mismatch"),
                                     ("viewpoint_note", "independent camera", "B_edit_viewpoint_note_mismatch")):
            with self.subTest(field=field):
                data = fixture()
                data[2]["edits"][1][field] = value
                output = self.evaluate(data)
                self.assertFalse(output["all_pass"])
                self.assertIn("B:" + reason, output["safety_checks"]["errors"])

    def test_stationary_edit_requires_actual_support_not_only_claimed_count(self):
        data = fixture()
        for row in data[0]["A"]["observations"]:
            if row["track_id"] == 1 and row["frame"] == 6:
                row["lane"] = "shoulder"
        output = self.evaluate(data)
        self.assertIn("A:edit_not_supported_by_stationary_lane_run", output["safety_checks"]["errors"])
        self.assertFalse(output["all_pass"])

    def test_missing_development_clip_returns_failed_five_rows(self):
        data = fixture()
        del data[0]["C"]
        del data[1]["C"]
        output = self.evaluate(data)
        self.assertFalse(output["all_pass"])
        self.assertEqual(len(output["rows"]), 5)

    def test_invalid_shared_pixel_position_cannot_pass_host_evidence_match(self):
        for coordinate in (float("nan"), -1, 192):
            with self.subTest(coordinate=coordinate):
                data = fixture()
                data[0]["A"]["candidates"][0]["evidence"]["position"]["x_px"] = coordinate
                data[2]["edits"][0]["position"]["x_px"] = coordinate
                output = self.evaluate(data)
                self.assertIn("A:edit_position_not_scene_local", output["safety_checks"]["errors"])
                self.assertFalse(self.row(output, "A_red_stationary")["pass"])

    def test_analysis_cannot_override_causal_background_role(self):
        data = fixture()
        data[1]["A"]["tracks"]["1"]["role_history"].append({"frame_index": 10, "role": "background_surface"})
        output = self.evaluate(data)
        self.assertIn("observation_causal_role_mismatch", output["clip_checks"]["A"]["errors"])
        self.assertFalse(output["all_pass"])


if __name__ == "__main__":
    unittest.main()
