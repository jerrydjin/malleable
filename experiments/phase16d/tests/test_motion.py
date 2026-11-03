"""Deterministic synthetic geometry checks; no SAM/network/held-out footage."""
import importlib.util
from pathlib import Path
import unittest

import cv2
import numpy as np

SPEC = importlib.util.spec_from_file_location("phase16d_motion", Path(__file__).resolve().parents[1] / "motion.py")
motion = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(motion)


def config():
    return {
        "ego": {"roi": [.08, .60, .92, .80], "exclusion_dilate_px": 5,
                "max_corners": 1500, "quality_level": .005, "min_distance_px": 5,
                "block_size": 7, "lk_window_px": 21, "lk_levels": 3,
                "lk_max_iterations": 30, "lk_epsilon": .01, "fb_error_px": 1.,
                "ransac_reprojection_px": 1.5, "ransac_max_iterations": 5000,
                "ransac_confidence": .995, "min_matches": 15, "min_inliers": 15,
                "min_inlier_ratio": .5, "min_coverage_fraction": .08,
                "coverage_grid": [3, 2], "min_occupied_cells": 3,
                "max_corner_displacement_fraction": .35, "rng_seed": 0},
        "motion": {"mask_erode_px": 1, "lower_band_fraction": .35,
                   "contact_quantile": .98, "min_features": 4,
                   "affine_reprojection_px": 1.5, "affine_max_iterations": 2000,
                   "affine_confidence": .99, "min_affine_inlier_ratio": .5,
                   "min_ego_motion_px": 1., "stationary_max_residual_px": 2.,
                   "stationary_max_relative_residual": .35,
                   "moving_min_relative_residual": .60, "min_confidence": .35},
        "lanes": {"boundaries": [[[.5, .4], [x, .9]] for x in (0., .25, .5, .75, 1.)],
                  "valid_y_range": [.5, .85], "boundary_margin_px": 2.},
    }


def forward_road_homography(cx=320., cy=150., focal=500., height=1.5, travel=1.5):
    # u=cx+fX/Z, v=cy+fh/Z and Z'=Z-T. This is a physically derived
    # ground-plane camera-motion fixture, not a handpicked classification vector.
    k = travel / (focal * height)
    return np.array([[1., -cx*k, cx*k*cy], [0., 1.-cy*k, k*cy*cy], [0., -k, 1.+k*cy]])


class ResidualTests(unittest.TestCase):
    def setUp(self):
        self.cfg = config()
        self.anchor = np.array([420., 225.])
        h = forward_road_homography()
        homogeneous = h @ np.r_[self.anchor, 1.]
        self.ego_flow = homogeneous[:2] / homogeneous[2] - self.anchor

    def test_stationary_ground_contact(self):
        result = motion.classify_residual(self.ego_flow, self.ego_flow, self.cfg)
        self.assertEqual(result["class"], "STATIONARY")
        self.assertEqual(result["residual_px"], 0.)

    def test_comoving_vehicle_with_zero_image_flow_is_moving(self):
        result = motion.classify_residual([0., 0.], self.ego_flow, self.cfg)
        self.assertEqual(result["class"], "MOVING")
        self.assertAlmostEqual(result["relative_residual"], 1.)

    def test_stationary_measurement_noise(self):
        result = motion.classify_residual(self.ego_flow + [.5, -.5], self.ego_flow, self.cfg)
        self.assertEqual(result["class"], "STATIONARY")
        self.assertAlmostEqual(result["residual_px"], 2 ** -.5)

    def test_unobservable_zero_ego_motion_is_unknown(self):
        result = motion.classify_residual([0., 0.], [0., 0.], self.cfg)
        self.assertEqual(result["class"], "UNKNOWN")
        self.assertIsNone(result["relative_residual"])

    def test_low_quality_cannot_be_stationary(self):
        result = motion.classify_residual(self.ego_flow, self.ego_flow, self.cfg, quality=.1)
        self.assertEqual(result["class"], "UNKNOWN")
        self.assertEqual(result["reason"], "low_motion_quality")


class ImageMotionTests(unittest.TestCase):
    def setUp(self):
        self.cfg = config()
        rng = np.random.default_rng(6)
        pixels = rng.integers(0, 256, (240, 320), dtype=np.uint8)
        self.gray = cv2.GaussianBlur(pixels, (3, 3), 0)
        self.rgb = np.repeat(self.gray[:, :, None], 3, axis=2)
        self.affine = np.array([[1., 0., 3.], [0., 1., 2.]])
        self.translated = cv2.warpAffine(self.rgb, self.affine, (320, 240), borderMode=cv2.BORDER_REFLECT)

    def test_background_homography_recovers_known_translation_deterministically(self):
        foreground = np.zeros(self.gray.shape, dtype=bool)
        foreground[150:177, 140:180] = True
        moved_foreground = cv2.warpAffine(foreground.astype(np.uint8), self.affine, (320, 240)) != 0
        first = motion.estimate_ego(self.rgb, self.translated, foreground, moved_foreground, self.cfg)
        second = motion.estimate_ego(self.rgb, self.translated, foreground, moved_foreground, self.cfg)
        self.assertTrue(first["valid"], first)
        self.assertEqual(first, second)
        point = np.array([130., 165., 1.])
        predicted = np.asarray(first["H"]) @ point
        np.testing.assert_allclose(predicted[:2] / predicted[2], point[:2] + [3., 2.], atol=.25)

    def test_missing_background_support_is_not_zero_motion(self):
        excluded = np.ones(self.gray.shape, dtype=bool)
        result = motion.estimate_ego(self.rgb, self.translated, excluded, excluded, self.cfg)
        self.assertFalse(result["valid"])
        self.assertIsNone(result["H"])

    def test_contact_feature_motion_matches_static_road(self):
        mask = np.zeros(self.gray.shape, dtype=bool)
        mask[100:180, 100:180] = True
        moved = cv2.warpAffine(mask.astype(np.uint8), self.affine, (320, 240)) != 0
        ego = {"valid": True, "H": [[1., 0., 3.], [0., 1., 2.], [0., 0., 1.]], "ratio": 1., "reason": "ok"}
        result = motion.classify_track(self.rgb, self.translated, mask, moved, ego, self.cfg)
        self.assertEqual(result["class"], "STATIONARY", result)
        self.assertGreaterEqual(result["featurecount"], self.cfg["motion"]["min_features"])
        self.assertLess(result["residual_px"], .25)

    def test_same_image_object_against_observable_ego_is_moving(self):
        mask = np.zeros(self.gray.shape, dtype=bool)
        mask[100:180, 100:180] = True
        ego = {"valid": True, "H": [[1., 0., 3.], [0., 1., 2.], [0., 0., 1.]], "ratio": 1., "reason": "ok"}
        result = motion.classify_track(self.rgb, self.rgb, mask, mask, ego, self.cfg)
        self.assertEqual(result["class"], "MOVING", result)
        self.assertLess(result["observed_motion_px"], .1)


class LaneTests(unittest.TestCase):
    def test_lane_shoulder_and_uncertainty(self):
        cfg = config()
        self.assertEqual(motion.assign_lane([600., 800.], (1000, 1000), cfg), "lane_2")
        self.assertEqual(motion.assign_lane([950., 800.], (1000, 1000), cfg), "shoulder")
        self.assertEqual(motion.assign_lane([600., 300.], (1000, 1000), cfg), "unknown")
        self.assertEqual(motion.assign_lane([500., 800.], (1000, 1000), cfg), "unknown")
        self.assertEqual(motion.assign_lane(None, (1000, 1000), cfg), "unknown")


if __name__ == "__main__":
    unittest.main()
