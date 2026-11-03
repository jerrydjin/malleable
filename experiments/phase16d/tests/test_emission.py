import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mapping import EmissionGate


class EmissionTests(unittest.TestCase):
    def config(self):
        return {"emission": {"consecutive_frames": 3, "duplicate_containment": 0.7}}

    def test_n_frames_emit_once_and_later_frames_do_not_duplicate(self):
        gate = EmissionGate(self.config())
        masks = {1: np.ones((8, 8), dtype=bool)}
        row = {"class": "STATIONARY", "lane": "lane_1", "role": "foreground"}
        events = [gate.observe(1, frame, row, frame/10, masks) for frame in range(7)]
        self.assertIsNone(events[0])
        self.assertIsNone(events[1])
        self.assertEqual(events[2]["count"], 3)
        self.assertEqual(sum(event is not None for event in events), 1)

    def test_moving_unknown_shoulder_and_background_never_emit(self):
        for kind, lane, role in [("MOVING", "lane_0", "foreground"), ("UNKNOWN", "lane_0", "foreground"),
                                 ("STATIONARY", "shoulder", "foreground"), ("STATIONARY", "lane_0", "background_surface")]:
            gate = EmissionGate(self.config())
            for frame in range(8):
                self.assertIsNone(gate.observe(1, frame, {"class": kind, "lane": lane, "role": role},
                                               frame/10, {1: np.ones((8, 8), dtype=bool)}))

    def test_missing_frame_or_lane_change_resets_run(self):
        gate = EmissionGate(self.config())
        masks = {1: np.ones((8, 8), dtype=bool)}
        row = {"class": "STATIONARY", "lane": "lane_0", "role": "foreground"}
        gate.observe(1, 0, row, 0., masks)
        gate.observe(1, 1, row, .1, masks)
        self.assertIsNone(gate.observe(1, 3, row, .3, masks))
        self.assertIsNone(gate.observe(1, 4, {**row, "lane": "lane_1"}, .4, masks))

    def test_nested_duplicate_track_does_not_emit_a_second_edit(self):
        gate = EmissionGate(self.config())
        row = {"class": "STATIONARY", "lane": "lane_1", "role": "foreground"}
        mask = np.ones((8, 8), dtype=bool)
        for frame in range(3):
            gate.observe(1, frame, row, frame/10, {1: mask})
        for frame in range(3, 6):
            self.assertIsNone(gate.observe(2, frame, row, frame/10, {1: mask, 2: mask.copy()}))
        self.assertEqual(gate.suppressed_duplicates[0]["existing_track_id"], 1)


if __name__ == "__main__":
    unittest.main()
