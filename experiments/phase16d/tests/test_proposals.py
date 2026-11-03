"""Host geometry/contact safeguards; genuine SAM inference is tested separately."""
import copy
import importlib.util
from pathlib import Path
import unittest

import numpy as np

EXPERIMENT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("phase16d_proposals", EXPERIMENT / "proposals.py")
proposals = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proposals)


def rectangle(box, score):
    mask = np.zeros((100, 160), dtype=bool)
    x0, y0, x1, y1 = box
    mask[y0:y1, x0:x1] = True
    return {"segmentation": mask, "predicted_iou": score, "stability_score": .96}


class AutomaticParts(unittest.TestCase):
    def setUp(self):
        self.sam = {"pred_iou_threshold": .8, "stability_threshold": .9,
                    "minimum_mask_area_px": 20, "mask_threshold": 0.,
                    "part_refinement": {"enabled": True}}
        self.body = rectangle((50, 20, 80, 60), .94)
        self.lower = rectangle((51, 63, 79, 76), .7)
        self.other = rectangle((110, 25, 138, 59), .95)
        self.raw = [self.body, self.lower, self.other]

    def test_adjacent_parts_generate_interior_prompts_without_promoting_low_quality_part(self):
        primary, secondary, pairs = proposals.select_pairs(self.raw, self.sam)
        self.assertEqual(primary, [0, 2])
        self.assertEqual(secondary, [0, 1, 2])
        self.assertEqual(len(pairs), 1)
        pair = pairs[0]
        self.assertEqual((pair["body_index"], pair["lower_index"]), (0, 1))
        self.assertEqual(pair["box_xyxy"], [50, 20, 80, 76])
        for index, point in zip((0, 1), pair["positive_points_xy"]):
            self.assertTrue(self.raw[index]["segmentation"][point[1], point[0]])
        self.assertEqual(proposals.automatic_iou_floor(self.sam), .65)
        self.assertEqual(self.sam["pred_iou_threshold"], .8)

    def test_pair_selection_is_stable_under_input_order(self):
        first = proposals.select_pairs(self.raw, self.sam)[2]
        second = proposals.select_pairs(list(reversed(self.raw)), self.sam)[2]
        self.assertEqual(first[0]["source_part_mask_sha256"], second[0]["source_part_mask_sha256"])
        self.assertEqual(first[0]["positive_points_xy"], second[0]["positive_points_xy"])

    def test_background_body_and_wide_road_patch_cannot_form_refinement(self):
        self.assertFalse(proposals.select_pairs(self.raw, self.sam, eligible_primary_indices=[])[2])
        wide_patch = rectangle((20, 63, 120, 76), .75)
        self.assertFalse(proposals.select_pairs([self.body, wide_patch], self.sam)[2])

    def test_one_lower_part_compatible_with_two_bodies_is_rejected(self):
        ambiguous_body = rectangle((52, 20, 82, 60), .93)
        self.assertFalse(proposals.select_pairs([self.body, ambiguous_body, self.lower], self.sam)[2])

    def test_secondary_part_must_still_have_minimum_quality_and_stability(self):
        for key, value in (("predicted_iou", .64), ("stability_score", .89)):
            weak = copy.deepcopy(self.lower)
            weak[key] = value
            self.assertFalse(proposals.select_pairs([self.body, weak], self.sam)[2])

    def test_refined_contact_requires_both_parts_and_original_quality_gates(self):
        pair = proposals.select_pairs(self.raw, self.sam)[2][0]
        whole = self.body["segmentation"] | self.lower["segmentation"]
        self.assertTrue(proposals.assess_refinement(whole, .91, .95, pair, self.raw, self.sam)["accepted"])
        for score, stability in ((.799, .95), (.91, .899)):
            result = proposals.assess_refinement(whole, score, stability, pair, self.raw, self.sam)
            self.assertFalse(result["accepted"])
            self.assertIn("native_quality_below_primary_gate", result["reasons"])
        body_only = proposals.assess_refinement(self.body["segmentation"], .99, .99, pair, self.raw, self.sam)
        self.assertFalse(body_only["accepted"])
        self.assertIn("source_positive_point_missing", body_only["reasons"])
        self.assertIn("lower_contact_extent_missing", body_only["reasons"])

    def test_high_quality_background_spill_is_rejected(self):
        pair = proposals.select_pairs(self.raw, self.sam)[2][0]
        spill = np.ones((100, 160), dtype=bool)
        result = proposals.assess_refinement(spill, .99, .99, pair, self.raw, self.sam)
        self.assertFalse(result["accepted"])
        self.assertIn("excessive_area_growth", result["reasons"])
        self.assertIn("mask_extends_outside_prompt_region", result["reasons"])


if __name__ == "__main__":
    unittest.main()
