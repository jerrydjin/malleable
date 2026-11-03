"""Detection and confirmation use one function. A reply is not an input."""

import unittest

from rules import evaluate, load_prereg, point_in_polygon, polygon_area


def frames(areas, t0=0.0, dt=1.0 / 3.0):
    return [{"lane_pixels": a, "source_s": t0 + i * dt} for i, a in enumerate(areas)]


class RuleTests(unittest.TestCase):
    def setUp(self):
        self.pre = load_prereg()
        self.threshold = self.pre["threshold_lane_pixels"]
        self.need = self.pre["consecutive_required"]

    def test_lane_area_and_points_match_the_preregistration(self):
        polygon = self.pre["lane_polygon_xy"]
        self.assertEqual(polygon_area(polygon), self.pre["lane_polygon_area_px"])
        for clip, point in self.pre["points_xy"].items():
            self.assertTrue(
                point_in_polygon(point[0], point[1], polygon), clip
            )

    def test_three_frames_at_the_threshold_detect(self):
        out = evaluate(frames([10000, 10000, 10000]), self.threshold, self.need)
        self.assertTrue(out["detected"])
        self.assertEqual(out["longest_consecutive_positive"], 3)
        self.assertEqual(out["positive_frames"], 3)
        self.assertEqual(out["since_s"], 0.0)
        self.assertAlmostEqual(out["confirm_at_s"], 2.0 / 3.0)

    def test_one_pixel_under_the_threshold_does_not_detect(self):
        out = evaluate(frames([9999, 9999, 9999]), self.threshold, self.need)
        self.assertFalse(out["detected"])
        self.assertEqual(out["longest_consecutive_positive"], 0)
        self.assertIsNone(out["since_s"])

    def test_a_broken_run_does_not_reach_three(self):
        out = evaluate(frames([10000, 10000, 0, 10000, 10000]), self.threshold, self.need)
        self.assertFalse(out["detected"])
        self.assertEqual(out["longest_consecutive_positive"], 2)

    def test_an_earlier_short_run_does_not_hide_a_later_detection(self):
        out = evaluate(
            frames([10000, 10000, 0, 10000, 10000, 10000]),
            self.threshold,
            self.need,
        )
        self.assertTrue(out["detected"])
        self.assertEqual(out["since_s"], 1.0)
        self.assertAlmostEqual(out["confirm_at_s"], 1.0 + 2.0 / 3.0)

    def test_confirmation_is_the_same_function(self):
        areas = [0, 12000, 13000, 14000, 1000]
        proposal = evaluate(frames(areas, t0=11.0), self.threshold, self.need)
        confirmation = evaluate(frames(areas, t0=14.5), self.threshold, self.need)
        self.assertEqual(proposal["detected"], confirmation["detected"])
        self.assertTrue(confirmation["detected"])
        self.assertGreater(confirmation["confirm_at_s"], proposal["since_s"])

    def test_clear_road_areas_do_not_detect(self):
        out = evaluate(frames([0, 100, 5000, 9999, 0, 0]), self.threshold, self.need)
        self.assertFalse(out["detected"])

    def test_a_label_is_not_an_input(self):
        out = evaluate(frames([0, 0, 0]), self.threshold, self.need)
        self.assertFalse(out["detected"])
        # The rule has no parameter for a model reply. Passing areas twice
        # still ignores any label a caller might wish were decisive.
        again = evaluate(frames([0, 0, 0]), self.threshold, self.need)
        self.assertEqual(out["detected"], again["detected"])


if __name__ == "__main__":
    unittest.main()
