"""Host history confirmation keeps MOVING and edit persistence separate."""
import copy
import csv
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

EXPERIMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT))
from mapping import EmissionGate
from motion import classify_motion_history
from outputs import write_tracks_csv


def observations(kinds, start=0, support="lower_band"):
    return [{"frame": start + index, "class": kind, "role": "foreground", "lane": "lane_1",
             "flow_support": support} for index, kind in enumerate(kinds)]


class MotionHistoryTests(unittest.TestCase):
    def test_three_moving_observations_confirm_only_when_explicitly_configured(self):
        rows = observations(["MOVING"] * 3)
        self.assertEqual(classify_motion_history(rows, 6)["class"], "UNKNOWN")
        summary = classify_motion_history(rows, 6, 3, True)
        self.assertEqual(summary["class"], "MOVING")
        self.assertEqual(summary["longest_moving_run"], 3)
        self.assertEqual(summary["longest_supported_moving_run"], 3)
        self.assertEqual(summary["required_stationary_motion_frames"], 6)
        self.assertEqual(summary["required_moving_motion_frames"], 3)
        self.assertTrue(summary["moving_require_lower_band_support"])

    def test_three_stationary_observations_do_not_confirm_or_emit(self):
        rows = observations(["STATIONARY"] * 3)
        self.assertEqual(classify_motion_history(rows, 6, 3, True)["class"], "UNKNOWN")
        gate = EmissionGate({"emission": {"consecutive_frames": 6, "duplicate_containment": .7}})
        mask = np.ones((12, 12), dtype=bool)
        for row in rows:
            self.assertIsNone(gate.observe(1, row["frame"], row, row["frame"] / 10, {1: mask}))
        self.assertEqual(gate.emitted, set())
        for row in observations(["STATIONARY"] * 3, start=3):
            event = gate.observe(1, row["frame"], row, row["frame"] / 10, {1: mask})
        self.assertEqual(event["count"], 6)
        self.assertEqual(event["frame"], 5)

    def test_moving_confirmation_never_emits(self):
        gate = EmissionGate({"emission": {"consecutive_frames": 6, "duplicate_containment": .7}})
        rows = observations(["MOVING"] * 9)
        self.assertEqual(classify_motion_history(rows, 6, 3, True)["class"], "MOVING")
        for row in rows:
            self.assertIsNone(gate.observe(1, row["frame"], row, row["frame"] / 10, {1: np.ones((12, 12), bool)}))
        self.assertEqual(gate.emitted, set())

    def test_unknown_interrupts_moving_confirmation(self):
        rows = observations(["MOVING", "MOVING", "UNKNOWN", "MOVING", "MOVING"])
        summary = classify_motion_history(rows, 6, 3, True)
        self.assertEqual(summary["class"], "UNKNOWN")
        self.assertEqual(summary["longest_moving_run"], 2)
        self.assertEqual(summary["longest_supported_moving_run"], 2)

    def test_missing_frames_and_background_roles_interrupt_moving_confirmation(self):
        rows = observations(["MOVING"] * 3)
        rows[2]["frame"] = 3
        self.assertEqual(classify_motion_history(rows, 6, 3, True)["class"], "UNKNOWN")
        rows = observations(["MOVING"] * 3)
        rows[1]["role"] = "background_surface"
        self.assertEqual(classify_motion_history(rows, 6, 3, True)["class"], "UNKNOWN")

    def test_both_confirmations_are_mixed_and_do_not_hide_movement(self):
        rows = observations(["STATIONARY"] * 6 + ["MOVING"] * 3)
        summary = classify_motion_history(rows, 6, 3, True)
        self.assertEqual(summary["class"], "MIXED")
        self.assertEqual(summary["longest_stationary_run"], 6)
        self.assertEqual(summary["longest_moving_run"], 3)
        self.assertEqual(summary["longest_supported_moving_run"], 3)

    def test_six_fallback_moving_rows_remain_provisional(self):
        rows = observations(["MOVING"] * 6, support="whole_mask_fallback")
        summary = classify_motion_history(rows, 6, 3, True)
        self.assertEqual(summary["class"], "UNKNOWN")
        self.assertEqual(summary["longest_moving_run"], 6)
        self.assertEqual(summary["longest_supported_moving_run"], 0)
        self.assertEqual([row["class"] for row in rows], ["MOVING"] * 6)

    def test_missing_support_is_not_assumed_to_be_lower_band(self):
        rows = observations(["MOVING"] * 3)
        for row in rows:
            del row["flow_support"]
        summary = classify_motion_history(rows, 6, 3, True)
        self.assertEqual(summary["class"], "UNKNOWN")
        self.assertEqual(summary["longest_moving_run"], 3)
        self.assertEqual(summary["longest_supported_moving_run"], 0)
        legacy = classify_motion_history(rows, 6, 3)
        self.assertEqual(legacy["class"], "MOVING")
        self.assertFalse(legacy["moving_require_lower_band_support"])

    def test_support_gap_resets_confirmation_without_hiding_raw_run(self):
        rows = observations(["MOVING"] * 5)
        rows[2]["flow_support"] = "whole_mask_fallback"
        summary = classify_motion_history(rows, 6, 3, True)
        self.assertEqual(summary["class"], "UNKNOWN")
        self.assertEqual(summary["longest_moving_run"], 5)
        self.assertEqual(summary["longest_supported_moving_run"], 2)
        rows.extend(observations(["MOVING"], start=5))
        self.assertEqual(classify_motion_history(rows, 6, 3, True)["class"], "MOVING")

    def test_unconfirmed_fallback_run_does_not_replace_stationary_confirmation(self):
        rows = observations(["STATIONARY"] * 6)
        rows.extend(observations(["MOVING"] * 6, start=6, support="whole_mask_fallback"))
        summary = classify_motion_history(rows, 6, 3, True)
        self.assertEqual(summary["class"], "STATIONARY")
        self.assertEqual(summary["longest_moving_run"], 6)
        self.assertEqual(summary["longest_supported_moving_run"], 0)

    def test_frame_measurements_are_preserved(self):
        rows = observations(["MOVING"] * 3 + ["UNKNOWN", "STATIONARY"])
        before = copy.deepcopy(rows)
        classify_motion_history(rows, 6, 3, True)
        self.assertEqual(rows, before)

    def test_csv_carries_the_actual_confirmation_policy(self):
        summary = classify_motion_history(observations(["MOVING"] * 3), 6, 3, True)
        summary.update({"track_id": 1, "role": "foreground", "label": "unlabelled object"})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tracks.csv"
            write_tracks_csv([{"clip": "A", "tracks": [summary]}], path)
            with path.open(newline="") as stream:
                row = next(csv.DictReader(stream))
        self.assertEqual(row["class"], "MOVING")
        self.assertEqual(row["required_moving_motion_frames"], "3")
        self.assertEqual(row["required_stationary_motion_frames"], "6")
        self.assertEqual(row["longest_supported_moving_run"], "3")
        self.assertEqual(row["moving_require_lower_band_support"], "True")
        self.assertEqual(row["motion_confirmation_policy"], "asymmetric_consecutive_windows")

    def test_confirmation_windows_must_be_positive_integer_counts(self):
        for stationary, moving in ((0, 3), (6, 0), (True, 3), (6, 2.5)):
            with self.assertRaises(ValueError):
                classify_motion_history([], stationary, moving, True)

    def test_support_requirement_must_be_boolean(self):
        for value in (None, 1, "true"):
            with self.assertRaises(ValueError):
                classify_motion_history([], 6, 3, value)


if __name__ == "__main__":
    unittest.main()
