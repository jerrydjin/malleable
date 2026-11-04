"""Geometry/cache invariants plus an actual checkpoint-dependent tracking repeat."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

EXPERIMENT = Path(__file__).resolve().parents[1]
ROOT = EXPERIMENT.parents[1]
SPEC = importlib.util.spec_from_file_location("phase16d_tracker", EXPERIMENT / "tracker.py")
tracker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tracker)


def config():
    return json.loads((EXPERIMENT / "config.json").read_text())


def rectangle(shape, box):
    mask = np.zeros(shape, dtype=bool)
    x0, y0, x1, y1 = box
    mask[y0:y1, x0:x1] = True
    return mask


def proposal(mask, score=.95):
    return {"segmentation": mask, "predicted_iou": score, "stability_score": .98,
            "point_coords": [[10., 20.]]}


class ProposalTests(unittest.TestCase):
    def setUp(self):
        # Synthetic geometry uses a fixed fixture independent of permitted DEV
        # tuning of the actual footage config. The real integration test below
        # always exercises the current complete experiment configuration.
        self.sam = {"minimum_mask_area_px": 8, "duplicate_iou": .85,
                    "duplicate_containment": .9, "association_iou": .3,
                    "association_containment": .75, "association_max_area_ratio": 4.,
                    "stuff_area_fraction": .25, "stuff_border_count": 3,
                    "top_border_fraction": .02, "sky_max_y_fraction": .5,
                    "hood_min_y_fraction": .9, "hood_min_area_fraction": .05}

    def test_proposal_order_and_duplicate_retention_are_deterministic(self):
        left = rectangle((100, 120), (10, 20, 30, 55))
        right = rectangle((100, 120), (65, 20, 90, 55))
        raw = [proposal(right), proposal(left), proposal(left, .90)]
        first, counts = tracker.prepare_proposals(raw, left.shape, self.sam)
        second, other_counts = tracker.prepare_proposals(list(reversed(raw)), left.shape, self.sam)
        self.assertEqual(counts, other_counts)
        self.assertEqual(counts["duplicate_proposals"], 1)
        self.assertEqual([p["mask_sha256"] for p in first], [p["mask_sha256"] for p in second])
        self.assertEqual(first[0]["bbox_xyxy"], [10, 20, 29, 54])

    def test_large_background_containment_does_not_delete_a_small_object(self):
        road = rectangle((100, 120), (0, 35, 120, 100))
        vehicle = rectangle((100, 120), (45, 50, 65, 65))
        retained, counts = tracker.prepare_proposals([proposal(road), proposal(vehicle)], road.shape, self.sam)
        self.assertEqual(counts["retained_proposals"], 2)
        self.assertEqual({p["area_px"] for p in retained}, {7800, 300})
        self.assertEqual(tracker.mask_role(road, self.sam)[0], "background_surface")
        self.assertEqual(tracker.mask_role(vehicle, self.sam)[0], "foreground")

    def test_association_is_one_to_one_and_preserves_video_ids(self):
        old_left = rectangle((100, 140), (10, 20, 35, 60))
        old_right = rectangle((100, 140), (75, 20, 100, 60))
        new_left = rectangle((100, 140), (12, 21, 37, 61))
        new_right = rectangle((100, 140), (77, 21, 102, 61))
        newcomer = rectangle((100, 140), (110, 70, 135, 95))
        proposals, _ = tracker.prepare_proposals([proposal(new_right), proposal(newcomer), proposal(new_left)], old_left.shape, self.sam)
        matches = tracker.associate_proposals(proposals, {20: old_right, 8: old_left}, self.sam)
        self.assertEqual([matches[i]["track_id"] for i in sorted(matches)], [8, 20])
        self.assertEqual(len(matches), 2)
        self.assertEqual(len({match["track_id"] for match in matches.values()}), 2)

    def test_track_cap_raises_instead_of_truncating_proposals(self):
        tracker.require_capacity(127, 1, 128)
        with self.assertRaisesRegex(tracker.TrackingCapacityExceeded, "no proposal truncation"):
            tracker.require_capacity(127, 2, 128)

    def test_later_background_role_does_not_rewrite_earlier_foreground(self):
        track = {"seed_frame": 3, "role_history": []}
        tracker._record_role(track, 3, "foreground", {"reason": "compact"})
        tracker._record_role(track, 8, "background_surface", {"reason": "large road mask"})
        self.assertIsNone(tracker.role_at(track, 2))
        self.assertEqual(tracker.role_at(track, 3), "foreground")
        self.assertEqual(tracker.role_at(track, 7), "foreground")
        self.assertEqual(tracker.role_at(track, 8), "background_surface")
        self.assertEqual(track["role"], "background_surface")
        tracker._record_role(track, 10, "foreground", {"reason": "smaller current mask"})
        self.assertEqual(tracker.role_at(track, 10), "background_surface")
        self.assertEqual(tracker.role_at(track, 7), "foreground")


class CacheTests(unittest.TestCase):
    def test_packed_masks_round_trip_and_stable_fingerprint(self):
        left = rectangle((29, 37), (2, 4, 9, 17))
        right = rectangle((29, 37), (18, 11, 29, 25))
        masks = {8: right, 2: left}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "masks.npz"
            tracker._write_mask_frame(path, masks, left.shape)
            loaded = tracker._read_mask_frame(path)
        self.assertEqual(sorted(loaded), [2, 8])
        for ident in masks:
            np.testing.assert_array_equal(masks[ident], loaded[ident])
        fingerprint = tracker.tracking_fingerprint([masks, loaded], [0, 3])
        self.assertEqual(fingerprint, tracker.tracking_fingerprint([loaded, masks], [0, 3]))
        self.assertNotEqual(fingerprint, tracker.tracking_fingerprint([loaded, masks], [0, 6]))

    def test_tracking_cache_key_changes_for_sampling_but_not_motion_thresholds(self):
        initial = config()
        motion_change = copy.deepcopy(initial)
        motion_change["motion"]["stationary_max_residual_px"] += 1.
        sampling_change = copy.deepcopy(initial)
        sampling_change["frame_stride"] += 1
        self.assertEqual(tracker.tracking_config(initial), tracker.tracking_config(motion_change))
        self.assertNotEqual(tracker.tracking_config(initial), tracker.tracking_config(sampling_change))

    def test_missing_checkpoint_refuses_before_decode_or_cache_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = config()
            cfg["sam"]["checkpoint"] = str(Path(directory) / "unavailable.pt")
            cache = Path(directory) / "cache"
            with self.assertRaises(tracker.CheckpointUnavailable):
                tracker.track_clip(Path(directory) / "unopened.mp4", cfg, cache)
            self.assertFalse(cache.exists())

    def test_cache_lock_rejects_a_second_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache"
            with tracker._cache_lock(cache):
                with self.assertRaises(tracker.CacheBusy):
                    with tracker._cache_lock(cache):
                        self.fail("A second writer acquired the same cache")
            with tracker._cache_lock(cache):
                pass

    def test_destination_signature_detects_unrelated_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache"
            self.assertIsNone(tracker._directory_signature(cache))
            cache.mkdir()
            empty = tracker._directory_signature(cache)
            (cache / "unrelated.txt").write_text("keep this file")
            self.assertNotEqual(empty, tracker._directory_signature(cache))


class BoundedMemoryTests(unittest.TestCase):
    @staticmethod
    def history_state(cond_indices, noncond_indices):
        indices = sorted(set(cond_indices) | set(noncond_indices))
        return {
            "output_dict_per_obj": {0: {
                "cond_frame_outputs": {index: index for index in cond_indices},
                "non_cond_frame_outputs": {index: index for index in noncond_indices}}},
            "point_inputs_per_obj": {0: {index: index for index in indices}},
            "mask_inputs_per_obj": {0: {index: index for index in indices}},
            "frames_tracked_per_obj": {0: {index: index for index in indices}},
            "temp_output_dict_per_obj": {0: {"cond_frame_outputs": {}, "non_cond_frame_outputs": {}}},
        }

    def test_read_through_masks_stream_the_same_fingerprint_with_bounded_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, original = [], []
            for index in range(24):
                objects = {index + 1: rectangle((19, 23), (index % 10, 2, index % 10 + 8, 17))}
                path = Path(directory) / f"{index:05d}.npz"
                tracker._write_mask_frame(path, objects, (19, 23))
                paths.append(path)
                original.append(objects)
            streamed = tracker.ReadThroughSequence(paths, tracker._read_mask_frame, cache_size=2)
            indices = list(range(0, 72, 3))
            self.assertEqual(tracker.tracking_fingerprint(original, indices),
                             tracker.tracking_fingerprint(streamed, indices))
            self.assertEqual(len(streamed.cache), 2)
            self.assertEqual(list(streamed.cache), [22, 23])
            self.assertEqual(list(streamed[-1]), [24])
            self.assertEqual(len(streamed[:3]), 3)
            self.assertEqual(len(streamed.cache), 2)
            with self.assertRaises(IndexError):
                streamed[24]

    def test_lazy_native_jpegs_match_actual_official_eager_preprocessing_exactly(self):
        import torch
        from PIL import Image
        from sam2.utils.misc import load_video_frames_from_jpg_images
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            rng = np.random.default_rng(491)
            for index in range(7):
                path = Path(directory) / f"{index:05d}.jpg"
                Image.fromarray(rng.integers(0, 256, (19, 27, 3), dtype=np.uint8)).save(path)
                paths.append(path)
            native, height, width = load_video_frames_from_jpg_images(
                directory, 32, offload_video_to_cpu=True, compute_device=torch.device("cpu"))
            lazy = tracker.NativeJPEGFrames(paths, 32, cache_size=2)
            self.assertEqual((height, width), (19, 27))
            for index in [0, 6, 1, 5, 2, 4, 3, 0]:
                self.assertEqual(lazy[index].dtype, torch.float32)
                self.assertTrue(torch.equal(lazy[index], native[index]))
                self.assertLessEqual(len(lazy.cache), 2)

    def test_history_pruning_preserves_all_native_forward_conditioning_and_pointer_lookups(self):
        from sam2.modeling.sam2_utils import select_closest_cond_frames
        reference_cond = {index: index for index in range(0, 1000, 10)}
        reference_noncond = {index: index for index in range(1000) if index % 10}
        state = {
            "output_dict_per_obj": {0: {"cond_frame_outputs": dict(reference_cond),
                                        "non_cond_frame_outputs": dict(reference_noncond)}},
            "point_inputs_per_obj": {0: {index: index for index in range(1000)}},
            "mask_inputs_per_obj": {0: {index: index for index in range(1000)}},
            "frames_tracked_per_obj": {0: {index: index for index in range(1000)}},
            "temp_output_dict_per_obj": {0: {"cond_frame_outputs": {}, "non_cond_frame_outputs": {}}},
        }
        radius = tracker.prune_native_history(state, 999, num_maskmem=7, memory_stride=1,
                                               max_obj_ptrs=16, max_cond_frames=2)
        current = state["output_dict_per_obj"][0]
        self.assertEqual(radius, 17)
        self.assertLessEqual(sum(map(len, current.values())), radius + 3)
        self.assertEqual(list(state["mask_inputs_per_obj"][0]), [999])
        self.assertEqual(list(state["point_inputs_per_obj"][0]), [999])
        self.assertLessEqual(len(state["frames_tracked_per_obj"][0]), radius + 1)
        # Use the installed official selector, not a replacement model. Check
        # current-boundary corrections and every future lookup into this history.
        for frame in range(999, 1040):
            selected, unselected = select_closest_cond_frames(frame, reference_cond, 2)
            actual_selected, actual_unselected = select_closest_cond_frames(
                frame, current["cond_frame_outputs"], 2)
            self.assertEqual(selected, actual_selected)
            for previous in range(frame - 15, frame):
                expected = reference_noncond.get(previous, unselected.get(previous))
                actual = current["non_cond_frame_outputs"].get(previous, actual_unselected.get(previous))
                self.assertEqual(expected, actual)

    def test_explicit_history_cap_retains_boundary_and_native_conditioning_selection(self):
        from sam2.modeling.sam2_utils import select_closest_cond_frames
        state = self.history_state(range(0, 101, 10), [index for index in range(101) if index % 10])
        reference_cond = dict(state["output_dict_per_obj"][0]["cond_frame_outputs"])
        tracker.prune_native_history(state, 100, num_maskmem=7, memory_stride=1,
                                     max_obj_ptrs=16, max_cond_frames=2,
                                     nonconditioning_history_frames=2)
        current = state["output_dict_per_obj"][0]
        self.assertEqual(sorted(current["cond_frame_outputs"]), [90, 100])
        self.assertEqual(sorted(current["non_cond_frame_outputs"]), [98, 99])
        self.assertEqual(list(state["mask_inputs_per_obj"][0]), [100])
        self.assertIn(100, state["frames_tracked_per_obj"][0])
        for frame in (100, 101):
            expected, _ = select_closest_cond_frames(frame, reference_cond, 2)
            selected, _ = select_closest_cond_frames(frame, current["cond_frame_outputs"], 2)
            self.assertEqual(expected, selected)
        # The current boundary can become conditioning at the next AMG refresh;
        # its prior nonconditioning output and tracked-frame entry survive too.
        state = self.history_state(range(0, 100, 10), [index for index in range(100) if index % 10])
        tracker.prune_native_history(state, 99, num_maskmem=7, memory_stride=1,
                                     max_obj_ptrs=16, max_cond_frames=2,
                                     nonconditioning_history_frames=2)
        self.assertEqual(sorted(state["output_dict_per_obj"][0]["non_cond_frame_outputs"]), [98, 99])
        self.assertIn(99, state["frames_tracked_per_obj"][0])

    def test_explicit_history_cap_bounds_records_and_exposes_missing_history(self):
        state = self.history_state([0], [])
        outputs = state["output_dict_per_obj"][0]
        for frame in range(1, 1001):
            storage = outputs["cond_frame_outputs"] if frame % 10 == 0 else outputs["non_cond_frame_outputs"]
            storage[frame] = frame
            state["frames_tracked_per_obj"][0][frame] = frame
            tracker.prune_native_history(state, frame, num_maskmem=7, memory_stride=1,
                                         max_obj_ptrs=16, max_cond_frames=2,
                                         nonconditioning_history_frames=2)
            self.assertLessEqual(len(outputs["cond_frame_outputs"]), 2)
            self.assertLessEqual(len(outputs["non_cond_frame_outputs"]), 2)
            self.assertIn(frame, outputs["cond_frame_outputs"] | outputs["non_cond_frame_outputs"])
        self.assertIsNone(outputs["non_cond_frame_outputs"].get(997))
        self.assertIsNone(outputs["cond_frame_outputs"].get(980))
        self.assertEqual(outputs["non_cond_frame_outputs"].get(999), 999)

    def test_explicit_history_cap_rejects_noncausal_or_invalid_context(self):
        arguments = dict(num_maskmem=7, memory_stride=1, max_obj_ptrs=16, max_cond_frames=2)
        for value in (0, -1, True, 1.5, "2"):
            with self.assertRaisesRegex(ValueError, "positive integer"):
                tracker.prune_native_history(self.history_state([0], [1]), 1,
                                             nonconditioning_history_frames=value, **arguments)
        with self.assertRaisesRegex(ValueError, "causal forward"):
            tracker.prune_native_history(self.history_state([0, 2], [1]), 1,
                                         nonconditioning_history_frames=2, **arguments)
        with self.assertRaisesRegex(RuntimeError, "conditioning anchor"):
            tracker.prune_native_history(self.history_state([], [1]), 1,
                                         nonconditioning_history_frames=2, **arguments)
        with self.assertRaisesRegex(RuntimeError, "current propagation boundary"):
            tracker.prune_native_history(self.history_state([0], [1]), 2,
                                         nonconditioning_history_frames=2, **arguments)


class ActualTrackingDeterminism(unittest.TestCase):
    def test_fixed_development_clip_first_three_sampled_frames_repeat(self):
        cfg = config()
        checkpoint = Path(cfg["sam"]["checkpoint"]).expanduser()
        if not checkpoint.is_file():
            self.skipTest("Actual SAM tracker determinism UNMEASURED: local native checkpoint is absent")
        # Within the same fixed three-frame test, cross repeated keyframes so
        # existing-ID AMG refreshes cannot be silently discarded as non-cond.
        cfg["sam"]["keyframe_interval_frames"] = 1
        clip = ROOT / "experiments/phase16b/footage/clip_A.mp4"
        with tempfile.TemporaryDirectory(prefix="phase16d-real-repeat-") as directory:
            first = tracker.track_clip(clip, cfg, Path(directory) / "first", limit_frames=3)
            second = tracker.track_clip(clip, cfg, Path(directory) / "second", limit_frames=3)
            self.assertGreater(first["track_count"], 0, "Real integration check must contain tracked masks")
            stride = int(cfg["frame_stride"])
            self.assertEqual(first["decoded"]["source_frame_indices"], [0, stride, 2 * stride])
            self.assertEqual(first["result_fingerprint"], second["result_fingerprint"])
            loaded = tracker.load_tracking(Path(directory) / "first")
            self.assertEqual(len(loaded["frames"]), 3)
            self.assertEqual(len(loaded["masks"]), 3)
            self.assertGreater(first["calls"]["automatic_mask_generation"], 0)
            self.assertGreater(first["calls"]["propagated_frame_outputs"], 0)
            self.assertTrue(first["backend_parameters"]["add_all_frames_to_correct_as_cond"])
            self.assertEqual(first["backend_parameters"]["max_cond_frames_in_attn"],
                             int(cfg["sam"].get("max_cond_frames_in_attn", 2)))
            self.assertEqual(first["backend_parameters"]["nonconditioning_history_frames"],
                             cfg["sam"].get("nonconditioning_history_frames"))
            if cfg["sam"].get("nonconditioning_history_frames") is not None:
                self.assertLessEqual(first["maximum_native_history_records_per_object"],
                                     cfg["sam"]["nonconditioning_history_frames"]
                                     + cfg["sam"].get("max_cond_frames_in_attn", 2))
            self.assertIsInstance(loaded["frames"], tracker.ReadThroughSequence)
            self.assertIsInstance(loaded["masks"], tracker.ReadThroughSequence)
            self.assertGreater(sum(frame["matched_existing"] for frame in first["keyframes"][1:]), 0)


if __name__ == "__main__":
    unittest.main()
