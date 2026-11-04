"""Causal ego-transform composition; synthetic geometry, no SAM substitutions."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

import cv2
import numpy as np

EXPERIMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT))
import mapping
import motion


def fit(matrix, *, ratio=.9, error=.2, inliers=80, matches=100,
        coverage=.7, cells=6, fb=.05):
    return {"H": np.asarray(matrix, dtype=float).tolist(), "valid": True,
            "reason": "ok", "ratio": ratio, "reprojection_error": error,
            "inliers": inliers, "matches": matches,
            "coverage_fraction": coverage, "occupied_cells": cells,
            "median_forward_backward_error": fb}


class HomographyComposition(unittest.TestCase):
    def test_column_vector_transform_order_and_scale_normalization(self):
        translation = np.array([[1., 0., 7.], [0., 1., -3.], [0., 0., 1.]])
        perspective = np.array([[1.1, .03, 0.], [0., .95, 0.], [.001, .002, 1.]])
        result = motion.compose_ego([fit(translation * 3.), fit(perspective * 2.)], start_frame=8)
        self.assertTrue(result["valid"], result)
        expected = perspective @ translation
        expected /= expected[2, 2]
        np.testing.assert_allclose(result["H"], expected, atol=1e-14)
        point = np.array([100., 180.])
        separately = motion._project(perspective, motion._project(translation, point))
        np.testing.assert_allclose(motion._project(result["H"], point), separately, atol=1e-12)
        self.assertEqual((result["from_frame"], result["to_frame"]), (8, 10))
        self.assertEqual([(r["from_frame"], r["to_frame"]) for r in result["components"]], [(8, 9), (9, 10)])

    def test_quality_never_exceeds_weakest_component_and_errors_are_explicit(self):
        first = fit(np.eye(3), ratio=.8, error=.2, inliers=70, matches=90, coverage=.4, cells=4, fb=.1)
        second = fit(np.eye(3), ratio=.6, error=.7, inliers=40, matches=80, coverage=.7, cells=6, fb=.3)
        result = motion.compose_ego([first, second])
        self.assertEqual(result["ratio"], .6)
        self.assertEqual(result["inliers"], 40)
        self.assertEqual(result["matches"], 80)
        self.assertEqual(result["coverage_fraction"], .4)
        self.assertEqual(result["occupied_cells"], 4)
        self.assertEqual(result["median_forward_backward_error"], .3)
        self.assertAlmostEqual(result["reprojection_error"], .9)
        self.assertIn("not_a_lagged_fit", result["reprojection_error_kind"])
        first["H"][0][0] = 99.
        self.assertEqual(result["components"][0]["H"][0][0], 1.)

    def test_missing_or_rejected_middle_fit_cannot_be_bridged(self):
        failed = motion._ego_failure("insufficient_homography_inliers", inliers=3, matches=100, ratio=.03)
        result = motion.compose_ego([fit(np.eye(3)), failed, fit(np.eye(3))], start_frame=12)
        self.assertFalse(result["valid"])
        self.assertIsNone(result["H"])
        self.assertEqual(result["ratio"], 0.)
        self.assertIn("invalid_ego_component:1:insufficient_homography_inliers", result["reason"])
        self.assertEqual(result["components"][1]["from_frame"], 13)

    def test_empty_nonfinite_and_singular_transforms_fail_closed(self):
        cases = [[], [fit(np.zeros((3, 3)))], [fit(np.eye(3)), fit(np.full((3, 3), np.nan))]]
        for steps in cases:
            with self.subTest(steps=len(steps)):
                result = motion.compose_ego(steps)
                self.assertFalse(result["valid"])
                self.assertIsNone(result["H"])


class ComposedImageMotion(unittest.TestCase):
    def setUp(self):
        cv2.setNumThreads(1)
        rng = np.random.default_rng(34)
        gray = cv2.GaussianBlur(rng.integers(0, 256, (180, 240), dtype=np.uint8), (3, 3), 0)
        rgb = np.repeat(gray[:, :, None], 3, axis=2)
        self.frames = [cv2.warpAffine(rgb, np.array([[1., 0., 2. * i], [0., 1., float(i)]]),
                                     (240, 180), borderMode=cv2.BORDER_REFLECT) for i in range(5)]
        self.cfg = {"motion_lag_frames": 2,
                    "ego": {"mode": "composed_adjacent", "roi": [.1, .1, .9, .9],
                            "exclusion_dilate_px": 2, "max_corners": 700, "quality_level": .01,
                            "min_distance_px": 4, "block_size": 7, "lk_window_px": 21, "lk_levels": 3,
                            "lk_max_iterations": 30, "lk_epsilon": .01, "fb_error_px": 1.,
                            "ransac_reprojection_px": 1.5, "ransac_max_iterations": 2000,
                            "ransac_confidence": .995, "min_matches": 15, "min_inliers": 15,
                            "min_inlier_ratio": .5, "min_coverage_fraction": .08,
                            "coverage_grid": [3, 2], "min_occupied_cells": 3,
                            "max_corner_displacement_fraction": .35, "rng_seed": 0},
                    "emission": {"consecutive_frames": 6},
                    "clips": {"fixture": {"viewpoint_note": "synthetic geometry"}}}

    def analyze(self, cfg):
        bundle = {"frames": self.frames, "masks": [{} for _ in self.frames], "tracks": {},
                  "timestamps_s": [i * .1 for i in range(len(self.frames))]}
        with tempfile.TemporaryDirectory() as directory:
            return mapping.analyze(bundle, cfg, "fixture", 0., directory)

    def test_real_optical_flow_chain_recovers_known_lag_translation(self):
        result = self.analyze(self.cfg)
        self.assertFalse(result["ego_motion"][1]["valid"])
        for index in range(2, 5):
            ego = result["ego_motion"][index]
            self.assertTrue(ego["valid"], ego)
            self.assertEqual(ego["component_count"], 2)
            self.assertEqual((ego["from_frame"], ego["to_frame"]), (index - 2, index))
            np.testing.assert_allclose(motion._project(ego["H"], [120., 100.])[0], [124., 102.], atol=.3)
        self.assertEqual(result["candidates"], [])

    def test_default_mode_remains_direct_and_invalid_mode_is_rejected(self):
        direct = copy.deepcopy(self.cfg)
        del direct["ego"]["mode"]
        result = self.analyze(direct)
        self.assertTrue(result["ego_motion"][2]["valid"])
        self.assertNotIn("components", result["ego_motion"][2])
        invalid = copy.deepcopy(self.cfg)
        invalid["ego"]["mode"] = "unregistered"
        with self.assertRaisesRegex(ValueError, "Unsupported ego-motion mode"):
            self.analyze(invalid)


if __name__ == "__main__":
    unittest.main()
