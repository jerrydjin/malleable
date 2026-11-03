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
