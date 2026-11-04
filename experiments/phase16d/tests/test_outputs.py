"""Synthetic export checks; no model, external footage, network, or held-out data."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import cv2

SPEC = importlib.util.spec_from_file_location("phase16d_outputs", Path(__file__).resolve().parents[1] / "outputs.py")
outputs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(outputs)


def fixture():
    frames, masks, observations = [], [], []
    kinds = ["UNKNOWN", "STATIONARY", "MOVING", "MOVING"]
    for index in range(4):
        frames.append(np.full((80, 128, 3), 70 + index*10, dtype=np.uint8))
        road = np.zeros((80, 128), dtype=bool)
        road[45:, :] = True
        obj = np.zeros((80, 128), dtype=bool)
        obj[40:65, 50+index:70+index] = True
        masks.append({1: obj, 2: road, 3: np.zeros((80, 128), dtype=bool)})
        for ident in (1, 2):
            observations.append({"clip": "B", "track_id": ident, "frame": index,
                                 "source_s": 14.5+index/10, "lane": "lane_1" if ident == 1 else "unknown",
                                 "class": kinds[index] if ident == 1 else "UNKNOWN", "confidence": .75})
    bundle = {"frames": frames, "masks": masks, "timestamps_s": [0., .1, .2, .3],
              "tracks": {"1": {"role": "foreground"}, "2": {"role": "background_surface"},
                         "3": {"role": "foreground"}},
              "metadata": {"identity": {"source_sha256": "a"*64, "checkpoint_sha256": "b"*64},
                           "result_fingerprint": "c"*64, "model_id": "synthetic test fixture",
                           "decoded": {"source_fps": 30.}, "tracking_config": {"frame_stride": 3}}}
    summaries = []
    for ident in (1, 2):
        summaries.append({"track_id": ident, "role": bundle["tracks"][str(ident)]["role"],
                          "first_frame": 0, "last_frame": 3, "source_start_s": 14.5, "source_end_s": 14.8,
                          "observations": 4, "stationary_frames": 1 if ident == 1 else 0,
                          "moving_frames": 2 if ident == 1 else 0, "unknown_frames": 1 if ident == 1 else 4,
                          "longest_stationary_run": 1 if ident == 1 else 0,
                          "longest_moving_run": 2 if ident == 1 else 0,
                          "residual_flow_median_px": 1.25 if ident == 1 else None,
                          "relative_residual_median": .5 if ident == 1 else None,
                          "lane": "lane_1" if ident == 1 else "unknown", "class": "UNKNOWN",
                          "label": "unlabelled object" if ident == 1 else "background surface",
                          "confidence_median": .75, "edit_emitted": False})
    analysis = {"clip": "B", "viewpoint_note": outputs.VIEWPOINT_B, "frame_count": 4,
                "tracks": summaries, "observations": observations}
    config = {"clips": {"B": {"source_start_s": 14.5, "viewpoint_note": outputs.VIEWPOINT_B}}}
    return bundle, analysis, config


def proposed_edit():
    return {"id": "phase16d:B:1", "clip": "B", "track_id": 1, "status": "Proposed",
            "position": {"coordinate_system": "road_reference_image", "reference_frame": 1,
                         "x_px": 60.0, "y_px": 60.0},
            "evidence": {"label": "stationary lane object"},
            "label_provenance": {"source": "model"}}


class OverlayTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe required")
    def test_h264_actual_cadence_all_masks_and_every_b_frame(self):
        bundle, analysis, config = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "B.mp4"
            original = outputs._render_frame
            with patch.object(outputs, "_render_frame", wraps=original) as draw:
                result = outputs.render_overlay(bundle, analysis, path, "B", config)
            self.assertEqual(draw.call_count, 4)
            for call in draw.call_args_list:
                self.assertIn(outputs.VIEWPOINT_B, " ".join(call.args[6]))
            self.assertEqual(result["frames_per_second"], "10")
            self.assertEqual(result["frame_spacing_s"], .1)
            self.assertEqual(result["duration_s"], .4)
            self.assertEqual(result["codec"], "h264")
            self.assertEqual(result["pixel_format"], "yuv420p")
            self.assertEqual(result["mask_draw_count"], 8)
            self.assertEqual(result["frame_count"], 4)
            self.assertTrue(all(frame["viewpoint_note"] == outputs.VIEWPOINT_B for frame in result["frames"]))
            self.assertTrue(all([item["track_id"] for item in frame["objects"]] == [1, 2]
                                for frame in result["frames"]))
            self.assertEqual([frame["objects"][0]["class"] for frame in result["frames"]],
                             ["UNKNOWN", "STATIONARY", "MOVING", "MOVING"])
            self.assertEqual(result["output_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(json.loads(path.with_suffix(".mp4.json").read_text()), result)
            self.assertFalse(result["labels_used_for_motion"])

    def test_missing_measurement_does_not_publish_video(self):
        bundle, analysis, config = fixture()
        analysis["observations"].pop()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "B.mp4"
            with self.assertRaisesRegex(ValueError, "Missing measurement"):
                outputs.render_overlay(bundle, analysis, path, "B", config)
            self.assertFalse(path.exists())

    def test_empty_bundle_does_not_create_placeholder(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "absent.mp4"
            with self.assertRaises(ValueError):
                outputs.render_overlay({"frames": [], "masks": [], "timestamps_s": []},
                                       {}, path, "absent", {})
            self.assertFalse(path.exists())

    def test_irregular_timestamps_are_not_resampled(self):
        bundle, analysis, config = fixture()
        bundle["timestamps_s"][-1] = .4
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "timestamps"):
                outputs.render_overlay(bundle, analysis, Path(directory) / "B.mp4", "B", config)

    def test_single_frame_requires_real_cadence_metadata(self):
        bundle, _, _ = fixture()
        bundle["timestamps_s"] = [0.]
        timestamps, fps = outputs._cadence(bundle)
        self.assertEqual(str(fps), "10")
        bundle["metadata"] = {}
        with self.assertRaisesRegex(ValueError, "single-frame"):
            outputs._cadence(bundle)


class ProposalMarkerTests(unittest.TestCase):
    def test_markers_begin_at_emission_and_preserve_actual_record_and_motion(self):
        bundle, analysis, config = fixture()
        edit = proposed_edit()
        records = outputs._observations(bundle, analysis, "B", config, None, [edit])
        self.assertNotIn("proposed_edit", records[0]["objects"][0])
        markers = [record["objects"][0]["proposed_edit"] for record in records[1:]]
        self.assertTrue(all(marker["edit_id"] == edit["id"] and marker["status"] == "Proposed"
                            for marker in markers))
        self.assertEqual([marker["draw_reference_position"] for marker in markers], [True, False, False])
        self.assertTrue(all(marker["reference_frame"] == 1 and marker["reference_position_xy"] == [60., 60.]
                            for marker in markers))
        self.assertEqual([record["objects"][0]["class"] for record in records],
                         ["UNKNOWN", "STATIONARY", "MOVING", "MOVING"])

    def test_recorded_cross_is_not_reused_as_later_pose_and_badge_follows_mask(self):
        bundle, analysis, config = fixture()
        analysis["observations"] = [row for row in analysis["observations"] if row["track_id"] == 1]
        for index in range(4):
            bundle["frames"][index] = np.full((80, 640, 3), 70 + index*10, dtype=np.uint8)
            mask = np.zeros((80, 640), dtype=bool)
            left = 50 if index < 2 else 300
            mask[40:65, left:left+20] = True
            bundle["masks"][index] = {1: mask, 2: np.zeros_like(mask)}
            # Zero-visible surface is intentionally absent from this rendering fixture.
        records = outputs._observations(bundle, analysis, "B", config, None, [proposed_edit()])
        banner = ["Clip B"]
        top = 36
        rendered = [outputs._render_frame(bundle["frames"][i], bundle["masks"][i], records[i],
                                          outputs._font(13), 640, 180, banner, [], .35)
                    for i in range(3)]
        colour = np.asarray(outputs.PROPOSED_EDIT_COLOUR)
        self.assertFalse(np.all(rendered[0] == colour, axis=2).any())
        np.testing.assert_array_equal(rendered[1][top+60, 60], colour)
        self.assertFalse(np.array_equal(rendered[2][top+60, 60], colour))
        _, later_x = np.nonzero(np.all(rendered[2] == colour, axis=2))
        self.assertGreater(len(later_x), 0)
        self.assertGreaterEqual(int(later_x.min()), 298)

    def test_no_edit_and_nonproposed_records_do_not_create_markers(self):
        bundle, analysis, config = fixture()
        for edits in ([], [{**proposed_edit(), "status": "Merged"}]):
            records = outputs._observations(bundle, analysis, "B", config, None, edits)
            self.assertTrue(all("proposed_edit" not in item for record in records for item in record["objects"]))

    def test_invalid_proposed_reference_does_not_publish_an_overlay(self):
        bundle, analysis, config = fixture()
        invalid = []
        for reference in (-1, 4, True, "1"):
            edit = proposed_edit(); edit["position"]["reference_frame"] = reference; invalid.append(edit)
        for key, value in (("x_px", float("nan")), ("y_px", float("inf")),
                           ("coordinate_system", "metric_world")):
            edit = proposed_edit(); edit["position"][key] = value; invalid.append(edit)
        edit = proposed_edit(); del edit["id"]; invalid.append(edit)
        edit = proposed_edit(); del edit["position"]["x_px"]; invalid.append(edit)
        with tempfile.TemporaryDirectory() as directory:
            for index, edit in enumerate(invalid):
                path = Path(directory) / f"invalid-{index}.mp4"
                with self.subTest(edit=edit), self.assertRaises(ValueError):
                    outputs.render_overlay(bundle, analysis, path, "B", config, edits=[edit])
                self.assertFalse(path.exists())

    def test_outside_reference_position_is_recorded_without_clamping(self):
        bundle, analysis, config = fixture()
        edit = proposed_edit(); edit["position"]["x_px"] = -2.5
        records = outputs._observations(bundle, analysis, "B", config, None, [edit])
        marker = records[1]["objects"][0]["proposed_edit"]
        self.assertEqual(marker["reference_position_xy"], [-2.5, 60.])
        self.assertFalse(marker["reference_position_visible"])
        self.assertFalse(marker["draw_reference_position"])
        self.assertEqual(marker["badge_position_source"], "current_visible_mask_bounds")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe required")
    def test_actual_h264_contains_reference_marker_and_provenance_counts(self):
        bundle, analysis, config = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "B.mp4"
            metadata = outputs.render_overlay(bundle, analysis, path, "B", config, edits=[proposed_edit()])
            self.assertEqual(metadata["proposed_edit_badge_draw_count"], 3)
            self.assertEqual(metadata["proposed_edit_reference_point_draw_count"], 1)
            capture = cv2.VideoCapture(str(path))
            decoded = []
            for _ in range(2):
                ok, frame = capture.read(); self.assertTrue(ok)
                decoded.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            capture.release()
            # Lossy H264 changes exact RGB values; the bright-orange reference
            # marker must remain visible around its real image point plus banner.
            top = (len(outputs._wrap(f"Clip B | {outputs.VIEWPOINT_B}", outputs._font(13), 468))+1)*18
            orange = lambda im: ((im[..., 0] > 205) & (im[..., 1] > 70)
                                  & (im[..., 1] < 190) & (im[..., 2] < 70))
            self.assertEqual(int(orange(decoded[0][top+49:top+71, 49:71]).sum()), 0)
            self.assertGreater(int(orange(decoded[1][top+49:top+71, 49:71]).sum()), 15)
            self.assertEqual(json.loads(path.with_suffix(".mp4.json").read_text()), metadata)


class TableTests(unittest.TestCase):
    def test_csv_preserves_scores_and_provenance_and_zero_visible_track(self):
        bundle, analysis, _ = fixture()
        edits = {"edits": [{"clip": "B", "track_id": 1,
                            "evidence": {"label": "model supplied label"},
                            "label_provenance": {"source": "model"}}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tracks.csv"
            result = outputs.write_tracks_csv({"B": analysis}, path, edits=edits, bundles={"B": bundle})
            with path.open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(result["rows"], 3)
            self.assertFalse(result["scores_recomputed"])
            self.assertEqual(rows[0]["class"], "UNKNOWN")
            self.assertEqual(rows[0]["moving_frames"], "2")
            self.assertEqual(rows[0]["label_source"], "model")
            self.assertEqual(rows[0]["label"], "model supplied label")
            self.assertEqual(rows[0]["confidence_kind"], "heuristic")
            self.assertEqual(rows[0]["source_sha256"], "a"*64)
            self.assertEqual(rows[2]["observations"], "0")
            self.assertEqual(rows[2]["first_frame"], "")
            self.assertEqual(rows[2]["class"], "UNKNOWN")
            self.assertTrue(all(row["viewpoint_note"] == outputs.VIEWPOINT_B for row in rows))

    def test_annotation_cannot_claim_model_provenance(self):
        bundle, analysis, _ = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tracks.csv"
            outputs.write_tracks_csv([analysis], path,
                                     labels={"B": {1: {"label": "manual", "source": "model"}}})
            with path.open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["label_source"], "annotation")

    def test_jsonl_retains_actual_edit_and_rejects_duplicate(self):
        row = {"clip": "B", "track_id": 7, "viewpoint_note": outputs.VIEWPOINT_B,
               "status": "Proposed", "label_provenance": {"source": "fallback", "fallback_reason": "test"}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "edits.jsonl"
            result = outputs.write_edits_jsonl({"edits": [row]}, path)
            self.assertEqual(result["rows"], 1)
            self.assertEqual(json.loads(path.read_text()), row)
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                outputs.write_edits_jsonl([row, row], path)
            self.assertEqual(json.loads(path.read_text()), row)

    def test_jsonl_empty_is_zero_edits_and_wrong_viewpoint_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "edits.jsonl"
            result = outputs.write_edits_jsonl({"edits": []}, path)
            self.assertEqual(result["rows"], 0)
            self.assertEqual(path.read_bytes(), b"")
            with self.assertRaisesRegex(ValueError, "same source, different viewpoint"):
                outputs.write_edits_jsonl([{"clip": "B", "track_id": 1, "viewpoint_note": "incorrect"}], path)
            with self.assertRaisesRegex(ValueError, "lacks an edits"):
                outputs.write_edits_jsonl({"state": "not_run"}, path)


if __name__ == "__main__":
    unittest.main()
