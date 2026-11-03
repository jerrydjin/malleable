#!/usr/bin/env python3
"""Whole-frame SAM 2.1 automatic proposals and genuine video mask propagation.

This module never downloads checkpoints, opens held-out paths by itself, or
substitutes cached 16b masks for tracking. Cache completion is published only
after every sampled frame and its mask file have been written and hashed.
"""
from __future__ import annotations

import copy
from collections import OrderedDict
from collections.abc import Sequence
from contextlib import contextmanager
import fcntl
import gc
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any
import uuid

import cv2
import numpy as np


FORMAT_VERSION = 1
CACHE_OWNER = "phase16d.sam2-video-tracker"


class CheckpointUnavailable(RuntimeError):
    """The configured native SAM 2.1 checkpoint is unavailable locally."""


class CacheMismatch(RuntimeError):
    """A cache does not match its current inputs or its recorded file hashes."""


class CacheBusy(CacheMismatch):
    """Another process currently owns the same cache's check/run/publish lock."""


class TrackingCapacityExceeded(RuntimeError):
    """Retaining all new proposals would exceed the explicitly configured cap."""


def _sha(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            result.update(block)
    return result.hexdigest()


def _json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


@contextmanager
def _cache_lock(cache_dir: Path):
    """Serialize cooperating writers without a stale-lock-file recovery guess."""
    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    path = cache_dir.with_name(f".{cache_dir.name}.tracker.lock")
    with path.open("a+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise CacheBusy(f"Tracking cache is already in use: {cache_dir}") from error
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _directory_signature(directory: Path) -> tuple | None:
    """Detect even non-cooperating destination changes before replacement."""
    if not directory.exists():
        return None
    if not directory.is_dir() or directory.is_symlink():
        raise CacheMismatch("Cache destination must be a normal directory")
    record = []
    for path in sorted(directory.rglob("*")):
        relative = str(path.relative_to(directory))
        if path.is_symlink():
            raise CacheMismatch("Tracker cache may not contain symbolic links")
        record.append((relative, "directory", None) if path.is_dir()
                      else (relative, "file", _sha(path)))
    return tuple(record)


def tracking_config(config: dict) -> dict:
    """Motion/emission tuning can reuse masks; tracking changes cannot."""
    return {"seed": int(config.get("seed", 0)),
            "working_width": int(config["working_width"]),
            "frame_stride": int(config["frame_stride"]),
            "sam": copy.deepcopy(config["sam"])}


def _bbox(mask: np.ndarray) -> list[int]:
    ys, xs = np.nonzero(mask)
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def _overlap(left: np.ndarray, right: np.ndarray) -> tuple[float, float, float]:
    a, b = int(left.sum()), int(right.sum())
    if not a or not b:
        return 0., 0., math.inf
    intersection = int(np.count_nonzero(left & right))
    return intersection / (a + b - intersection), intersection / min(a, b), max(a, b) / min(a, b)


def prepare_proposals(raw: list[dict], shape: tuple[int, int], sam: dict) -> tuple[list[dict], dict]:
    """Quality-retained AMG proposals in a deterministic order, with explicit filters.

    A large road/sky mask containing a small object does not suppress that
    object: containment counts as a duplicate only at comparable mask areas.
    """
    counts = {"raw_proposals": len(raw), "empty_or_small": 0,
              "duplicate_proposals": 0, "retained_proposals": 0}
    candidates = []
    minimum = int(sam["minimum_mask_area_px"])
    for item in raw:
        mask = np.asarray(item["segmentation"], dtype=bool)
        if mask.shape != shape:
            raise ValueError(f"AMG mask shape {mask.shape} differs from frame {shape}")
        area = int(mask.sum())
        if area < minimum or area == 0:
            counts["empty_or_small"] += 1
            continue
        box = _bbox(mask)
        score = float(item.get("predicted_iou", 0.))
        stability = float(item.get("stability_score", 0.))
        if not math.isfinite(score) or not math.isfinite(stability):
            raise ValueError("Non-finite SAM proposal quality")
        candidates.append({"mask": mask, "area_px": area, "bbox_xyxy": box,
                           "predicted_iou": score, "stability_score": stability,
                           "point_coords": np.asarray(item.get("point_coords", []), dtype=float).tolist(),
                           "mask_sha256": hashlib.sha256(np.packbits(mask, bitorder="little").tobytes()).hexdigest()})
    # Quality decides duplicate retention; a second geometry ordering makes IDs
    # stable when the external AMG list is returned in a different order.
    candidates.sort(key=lambda p: (-p["predicted_iou"], -p["stability_score"],
                                   -p["area_px"], p["bbox_xyxy"], p["mask_sha256"]))
    retained = []
    for candidate in candidates:
        duplicate = False
        for earlier in retained:
            iou, containment, area_ratio = _overlap(candidate["mask"], earlier["mask"])
            if iou >= float(sam["duplicate_iou"]) or (
                    containment >= float(sam["duplicate_containment"])
                    and area_ratio <= float(sam["association_max_area_ratio"])):
                duplicate = True
                break
        if duplicate:
            counts["duplicate_proposals"] += 1
        else:
            retained.append(candidate)
    retained.sort(key=lambda p: (p["bbox_xyxy"][1], p["bbox_xyxy"][0],
                                 -p["area_px"], p["mask_sha256"]))
    counts["retained_proposals"] = len(retained)
    return retained, counts


def associate_proposals(proposals: list[dict], existing: dict[int, np.ndarray], sam: dict) -> dict[int, dict]:
    """Deterministic one-to-one proposal→persisted video-ID association."""
    candidates = []
    for index, proposal in enumerate(proposals):
        for ident in sorted(existing):
            iou, containment, area_ratio = _overlap(proposal["mask"], existing[ident])
            if area_ratio > float(sam["association_max_area_ratio"]):
                continue
            if iou < float(sam["association_iou"]) and containment < float(sam["association_containment"]):
                continue
            score = max(iou, containment * 0.5)
            candidates.append((-score, -iou, -containment, area_ratio, ident, index))
    matched, used_ids = {}, set()
    for _, neg_iou, neg_containment, area_ratio, ident, index in sorted(candidates):
        if index in matched or ident in used_ids:
            continue
        matched[index] = {"track_id": int(ident), "iou": -neg_iou,
                          "containment": -neg_containment, "area_ratio": area_ratio}
        used_ids.add(ident)
    return matched


def mask_role(mask: np.ndarray, sam: dict) -> tuple[str, dict]:
    """Declared image-geometry hypothesis for road/sky/hood background stuff."""
    height, width = mask.shape
    box = _bbox(mask)
    area_fraction = float(mask.mean())
    band_y = max(1, int(math.ceil(height * float(sam["top_border_fraction"]))))
    band_x = max(1, int(math.ceil(width * float(sam["top_border_fraction"]))))
    touches = [bool(mask[:band_y].any()), bool(mask[-band_y:].any()),
               bool(mask[:, :band_x].any()), bool(mask[:, -band_x:].any())]
    border_count = sum(touches)
    reason = "compact_instance_hypothesis"
    role = "foreground"
    if area_fraction >= float(sam["stuff_area_fraction"]) and border_count >= int(sam["stuff_border_count"]):
        role, reason = "background_surface", "large_mask_touching_multiple_image_borders"
    elif touches[0] and box[3] / height <= float(sam["sky_max_y_fraction"]):
        role, reason = "background_surface", "top_border_upper_image_mask"
    elif box[1] / height >= float(sam["hood_min_y_fraction"]) and area_fraction >= float(sam["hood_min_area_fraction"]):
        role, reason = "background_surface", "bottom_hood_region_mask"
    return role, {"reason": reason, "area_fraction": area_fraction,
                  "border_count": border_count, "bbox_xyxy": box}


def role_at(track: dict, frame_index: int) -> str | None:
    """Read the causal role; ``track['role']`` is only its end-of-clip summary."""
    role = None
    for observation in track.get("role_history", []):
        if int(observation["frame_index"]) > frame_index:
            break
        role = observation["role"]
    return role


def _record_role(track: dict, frame_index: int, observed_role: str, detail: dict) -> None:
    """Background classification is conservative and sticky from observation on."""
    history = track.setdefault("role_history", [])
    if history and int(history[-1]["frame_index"]) > frame_index:
        raise ValueError("Role observations must be in temporal order")
    previous = role_at(track, frame_index)
    effective = "background_surface" if previous == "background_surface" else observed_role
    effective_detail = detail if effective == observed_role else {
        "reason": "previously_observed_background_surface_role_retained",
        "current_observed_detail": detail}
    record = {"frame_index": int(frame_index), "role": effective,
              "observed_role": observed_role, "detail": copy.deepcopy(effective_detail)}
    if history and int(history[-1]["frame_index"]) == frame_index:
        history[-1] = record
    else:
        history.append(record)
    track["role"], track["role_detail"] = effective, copy.deepcopy(effective_detail)


def require_capacity(existing_count: int, new_count: int, maximum: int) -> None:
    if existing_count + new_count > maximum:
        raise TrackingCapacityExceeded(
            f"Retaining all proposals requires {existing_count + new_count} tracks "
            f"({existing_count} existing + {new_count} new), exceeding maximum_tracks={maximum}; "
            "no proposal truncation was applied")


def _write_mask_frame(path: Path, masks: dict[int, np.ndarray], shape: tuple[int, int]) -> None:
    identifiers = np.array(sorted(masks), dtype=np.int64)
    pixel_count = int(shape[0] * shape[1])
    packed = np.empty((len(identifiers), (pixel_count + 7) // 8), dtype=np.uint8)
    for row, ident in enumerate(identifiers):
        mask = np.asarray(masks[int(ident)], dtype=bool)
        if mask.shape != shape:
            raise ValueError("Propagated mask dimensions do not match decoded frame")
        packed[row] = np.packbits(mask.reshape(-1), bitorder="little")
    np.savez_compressed(path, ids=identifiers, shape=np.array(shape, dtype=np.int64), packed=packed)


def _read_mask_frame(path: Path) -> dict[int, np.ndarray]:
    with np.load(path, allow_pickle=False) as record:
        identifiers = record["ids"].tolist()
        shape = tuple(int(n) for n in record["shape"])
        packed = record["packed"]
        if len(shape) != 2 or any(n <= 0 for n in shape) or len(set(identifiers)) != len(identifiers):
            raise CacheMismatch("Malformed packed mask file")
        if packed.shape != (len(identifiers), (shape[0] * shape[1] + 7) // 8):
            raise CacheMismatch("Packed mask dimensions do not agree with metadata")
        return {int(ident): np.unpackbits(packed[row], bitorder="little", count=shape[0] * shape[1])
                .reshape(shape).astype(bool) for row, ident in enumerate(identifiers)}


class ReadThroughSequence(Sequence):
    """Disk-backed ordered records with bounded read-through caching."""

    def __init__(self, paths, reader, cache_size=8):
        if int(cache_size) <= 0:
            raise ValueError("Read-through cache_size must be positive")
        self.paths, self.reader = tuple(paths), reader
        self.cache_size, self.cache = int(cache_size), OrderedDict()

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        if not isinstance(index, (int, np.integer)):
            raise TypeError("Sequence indices must be integers or slices")
        index = int(index)
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        if index in self.cache:
            self.cache.move_to_end(index)
            return self.cache[index]
        value = self.reader(self.paths[index])
        self.cache[index] = value
        while len(self.cache) > self.cache_size:
            self.cache.popitem(last=False)
        return value


class NativeJPEGFrames(ReadThroughSequence):
    """The native eager JPEG loader's exact FP32 preprocessing, loaded on demand.

    Native init_state's async option retains every image (and uses FP64 here).
    This adapter instead retains only a fixed number of normalized tensors.
    """

    def __init__(self, paths, image_size, cache_size=2):
        import torch
        from sam2.utils.misc import _load_img_as_tensor
        mean = torch.tensor((0.485, 0.456, 0.406), dtype=torch.float32)[:, None, None]
        std = torch.tensor((0.229, 0.224, 0.225), dtype=torch.float32)[:, None, None]

        def read(path):
            # Native eager loading assigns the helper's FP64 image into an FP32
            # tensor *before* normalization; preserve that rounding exactly.
            image, _, _ = _load_img_as_tensor(str(path), int(image_size))
            image = image.to(dtype=torch.float32)
            image.sub_(mean).div_(std)
            return image

        super().__init__(paths, read, cache_size)


def _bounded_native_state(predictor, paths, cache_size):
    """Keep one genuine native session, with a bounded image backing Sequence."""
    # init_state always eagerly loads its input directory. Warm its original
    # feature/cache machinery on the exact first JPEG, then expose the remaining
    # JPEGs through the same integer-indexed tensor interface.
    with tempfile.TemporaryDirectory(prefix=".native-init-", dir=Path(paths[0]).parent.parent) as directory:
        os_path = Path(directory) / "00000.jpg"
        os_path.hardlink_to(paths[0])
        state = predictor.init_state(directory, offload_video_to_cpu=True,
                                     offload_state_to_cpu=True, async_loading_frames=False)
    state["images"] = NativeJPEGFrames(paths, predictor.image_size, cache_size)
    state["num_frames"] = len(paths)
    return state


def prune_native_history(state, frame_index, *, num_maskmem, memory_stride,
                         max_obj_ptrs, max_cond_frames):
    """Drop outputs that forward native SAM can never attend again.

    The current boundary frame may be corrected/repropagated, so retain its
    entire backwards lookup radius as well as every later frame. The two most
    recent older conditioning frames survive even outside this radius. Inputs
    and tracked-frame bookkeeping have the same bounded lifetime.
    """
    if min(num_maskmem, memory_stride, max_obj_ptrs) <= 0 or max_cond_frames < 2:
        raise ValueError("Bounded history requires positive radii and 2+ conditioning frames")
    radius = max(num_maskmem * memory_stride + 2, max_obj_ptrs + 1)
    keep_from = int(frame_index) - radius
    for obj_idx, outputs in state["output_dict_per_obj"].items():
        cond = outputs["cond_frame_outputs"]
        older = sorted((index for index in cond if index < keep_from), reverse=True)
        keep_old_cond = set(older[:max_cond_frames])
        for storage in (cond, outputs["non_cond_frame_outputs"]):
            for index in list(storage):
                if index < keep_from and not (storage is cond and index in keep_old_cond):
                    del storage[index]
        # Prompt tensors are not read once their output has been consolidated.
        # Only the current boundary can receive a correction again; keeping old
        # 1024-square FP32 prompt masks would defeat the history bound.
        for name in ("point_inputs_per_obj", "mask_inputs_per_obj"):
            records = state[name][obj_idx]
            for index in list(records):
                if index < frame_index:
                    del records[index]
        records = state["frames_tracked_per_obj"][obj_idx]
        for index in list(records):
            if index < keep_from:
                del records[index]
        for records in state["temp_output_dict_per_obj"][obj_idx].values():
            for index in list(records):
                if index < frame_index:
                    raise RuntimeError("Unconsolidated native output predates the propagation boundary")
    return radius


def tracking_fingerprint(masks: Sequence, frame_indices: Sequence) -> str:
    """Result identity excludes elapsed wall times and cache paths."""
    result = hashlib.sha256()
    if len(masks) != len(frame_indices):
        raise ValueError("Mask frames and source frame indices differ")
    for index, frame in zip(frame_indices, masks):
        result.update(f"frame:{index}\n".encode())
        for ident in sorted(frame):
            mask = np.asarray(frame[ident], dtype=bool)
            result.update(f"track:{ident}:{mask.shape[0]}:{mask.shape[1]}\n".encode())
            result.update(np.packbits(mask.reshape(-1), bitorder="little").tobytes())
    return result.hexdigest()


def _decode(input_path: Path, directory: Path, config: dict, limit_frames: int | None) -> dict:
    capture = cv2.VideoCapture(str(input_path))
    if not capture.isOpened():
        raise ValueError(f"Unable to decode input video: {input_path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    if not math.isfinite(fps) or fps <= 0:
        capture.release()
        raise ValueError("Input video has no positive finite frame rate")
    stride, width = int(config["frame_stride"]), int(config["working_width"])
    if stride <= 0 or width <= 0 or (limit_frames is not None and limit_frames <= 0):
        capture.release()
        raise ValueError("Positive stride, width and optional sampled-frame limit required")
    directory.mkdir(parents=True)
    selected, source_index, original_size, output_size = [], 0, None, None
    try:
        while True:
            ok, image = capture.read()
            if not ok:
                break
            if original_size is None:
                original_size = [int(image.shape[1]), int(image.shape[0])]
                output_size = [width, max(1, int(round(image.shape[0] * width / image.shape[1])))]
            if source_index % stride == 0:
                resized = cv2.resize(image, tuple(output_size), interpolation=cv2.INTER_AREA)
                path = directory / f"{len(selected):05d}.jpg"
                if not cv2.imwrite(str(path), resized, [cv2.IMWRITE_JPEG_QUALITY, 98]):
                    raise RuntimeError("Could not write a sampled video frame")
                selected.append(source_index)
                if limit_frames is not None and len(selected) >= limit_frames:
                    source_index += 1
                    break
            source_index += 1
    finally:
        capture.release()
    if not selected:
        raise ValueError("Input video decoded zero sampled frames")
    return {"source_fps": fps, "source_frame_indices": selected,
            "timestamps_s": [index / fps for index in selected],
            "source_frames_read": source_index, "source_size_wh": original_size,
            "working_size_wh": output_size, "sampled_frames": len(selected),
            "jpeg_quality": 98, "sampling": "source frame indices divisible by frame_stride, starting at zero"}


def _read_rgb(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise CacheMismatch(f"Unable to read cached RGB frame: {path}")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def _verified_source(sam2_package: Any, configured_revision: str) -> dict:
    provenance = Path(__file__).with_name("runtime") / "sam2-source.json"
    record = json.loads(provenance.read_text())
    if record["revision"] != configured_revision:
        raise ValueError("Configured SAM source revision differs from recorded package provenance")
    package = Path(sam2_package.__file__).resolve().parent
    checked = []
    for entry in record["files"]:
        if not entry["path"].startswith("sam2/"):
            continue
        relative = entry["path"].removeprefix("sam2/")
        actual = _sha(package / relative)
        if actual != entry["sha256"]:
            raise ValueError(f"Installed SAM package source differs from pin: {entry['path']}")
        checked.append({"path": entry["path"], "sha256": actual})
    if not checked:
        raise ValueError("No installed SAM source files were verified")
    return {"revision": configured_revision, "verified_package_files": checked}


def _run(input_path: Path, config: dict, output: Path, checkpoint: Path,
         identity: dict, limit_frames: int | None) -> dict:
    import torch
    import torchvision
    import sam2
    from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
    from sam2.build_sam import HF_MODEL_ID_TO_FILENAMES, build_sam2_video_predictor

    sam = config["sam"]
    device = str(sam["device"])
    if sam["dtype"] != "float32":
        raise ValueError("This tracker implements explicitly recorded float32 inference only")
    if device != "cpu" and not (device.startswith("cuda") and torch.cuda.is_available()):
        raise RuntimeError(f"Configured SAM device is unavailable: {device}")
    torch.manual_seed(int(config.get("seed", 0)))
    torch.set_num_threads(int(sam["torch_threads"]))
    torch.use_deterministic_algorithms(bool(sam["deterministic_algorithms"]))
    cv2.setRNGSeed(int(config.get("seed", 0)))
    cv2.setNumThreads(1)
    provenance = _verified_source(sam2, str(sam["source_revision"]))
    expected = HF_MODEL_ID_TO_FILENAMES.get(str(sam["model_id"]))
    if expected is None or str(sam["model_config"]) != expected[0]:
        raise ValueError("SAM model ID and native architecture config do not agree")
    decode_started = time.perf_counter()
    decoded = _decode(input_path, output / "frames", config, limit_frames)
    decode_seconds = time.perf_counter() - decode_started
    paths = sorted((output / "frames").glob("*.jpg"))
    decoded_cache_size = int(sam.get("decoded_frame_cache_size", 8))
    video_cache_size = int(sam.get("video_frame_cache_size", 2))
    max_cond_frames = int(sam.get("max_cond_frames_in_attn", 2))
    retire_after = int(sam.get("retire_after_empty_frames", 20))
    if max_cond_frames < 2 or retire_after <= 0:
        raise ValueError("Bounded tracking requires 2+ conditioning frames and positive empty-frame retirement")
    frames = ReadThroughSequence(paths, _read_rgb, decoded_cache_size)
    height, width = frames[0].shape[:2]
    started = time.perf_counter()
    predictor = build_sam2_video_predictor(str(sam["model_config"]), str(checkpoint),
                                          device=device, apply_postprocessing=False, vos_optimized=False,
                                          hydra_overrides_extra=["++model.add_all_frames_to_correct_as_cond=true",
                                                                 f"++model.max_cond_frames_in_attn={max_cond_frames}"])
    predictor.to(dtype=torch.float32)
    if not predictor.add_all_frames_to_correct_as_cond:
        raise RuntimeError("AMG keyframe refreshes must remain conditioning frames during propagation")
    generator = SAM2AutomaticMaskGenerator(
        predictor, points_per_side=int(sam["points_per_side"]), points_per_batch=int(sam["points_per_batch"]),
        pred_iou_thresh=float(sam["pred_iou_threshold"]), stability_score_thresh=float(sam["stability_threshold"]),
        mask_threshold=float(sam["mask_threshold"]), box_nms_thresh=float(sam["box_nms_threshold"]),
        crop_n_layers=0, min_mask_region_area=0, output_mode="binary_mask", multimask_output=True)
    model_load_seconds = time.perf_counter() - started
    tracks, boundary_masks, keyframes = {}, {}, []
    mask_directory = output / "masks"
    mask_directory.mkdir()
    written_frames, last_visible = set(), {}
    maximum_active_tracks, maximum_native_records = 0, 0
    history_radius = None
    calls = {"automatic_mask_generation": 0, "add_new_mask": 0,
             "propagate_chunks": 0, "propagated_frame_outputs": 0}
    interval = int(sam["keyframe_interval_frames"])
    if interval <= 0:
        raise ValueError("keyframe_interval_frames must be positive")
    with torch.inference_mode():
        initialized = time.perf_counter()
        state = _bounded_native_state(predictor, paths, video_cache_size)
        state_init_seconds = time.perf_counter() - initialized
        for keyframe in range(0, len(frames), interval):
            generated = time.perf_counter()
            raw = generator.generate(frames[keyframe])
            amg_seconds = time.perf_counter() - generated
            calls["automatic_mask_generation"] += 1
            proposals, counts = prepare_proposals(raw, (height, width), sam)
            associations = associate_proposals(proposals, boundary_masks, sam)
            new_count = len(proposals) - len(associations)
            require_capacity(len(state["obj_ids"]), new_count, int(sam["maximum_tracks"]))
            updates = []
            seed_started = time.perf_counter()
            for index, proposal in enumerate(proposals):
                role, role_detail = mask_role(proposal["mask"], sam)
                if index in associations:
                    ident = associations[index]["track_id"]
                    item = tracks[str(ident)]
                    item["keyframe_observations"].append(keyframe)
                    _record_role(item, keyframe, role, role_detail)
                    update = {"proposal_index": index, **associations[index], "new_track": False}
                else:
                    ident = len(tracks) + 1
                    tracks[str(ident)] = {"track_id": ident, "role": role, "role_detail": role_detail,
                                          "seed_frame": keyframe, "seed_source_frame": decoded["source_frame_indices"][keyframe],
                                          "seed_bbox_xyxy": proposal["bbox_xyxy"], "seed_area_px": proposal["area_px"],
                                          "seed_predicted_iou": proposal["predicted_iou"],
                                          "seed_stability_score": proposal["stability_score"],
                                          "seed_point_coords": proposal["point_coords"],
                                          "keyframe_observations": [keyframe],
                                          "mask_source": "SAM2AutomaticMaskGenerator -> SAM2VideoPredictor.add_new_mask"}
                    _record_role(tracks[str(ident)], keyframe, role, role_detail)
                    update = {"proposal_index": index, "track_id": ident, "new_track": True}
                predictor.add_new_mask(state, frame_idx=keyframe, obj_id=ident, mask=proposal["mask"])
                calls["add_new_mask"] += 1
                last_visible.setdefault(ident, keyframe)
                updates.append(update)
            maximum_active_tracks = max(maximum_active_tracks, len(state["obj_ids"]))
            seed_seconds = time.perf_counter() - seed_started
            end = min(keyframe + interval, len(frames) - 1)
            propagation_started = time.perf_counter()
            if state["obj_ids"]:
                calls["propagate_chunks"] += 1
                for frame_index, identifiers, logits in predictor.propagate_in_video(
                        state, start_frame_idx=keyframe, max_frame_num_to_track=end - keyframe):
                    values = (logits.detach().float().cpu().numpy() > float(sam["mask_threshold"]))
                    if values.shape != (len(identifiers), 1, height, width):
                        raise RuntimeError(f"Unexpected SAM video output shape {values.shape}")
                    boundary_masks = {int(ident): values[row, 0]
                                      for row, ident in enumerate(identifiers)}
                    _write_mask_frame(mask_directory / f"{frame_index:05d}.npz", boundary_masks, (height, width))
                    written_frames.add(int(frame_index))
                    for ident, mask in boundary_masks.items():
                        if mask.any():
                            last_visible[ident] = int(frame_index)
                    history_radius = prune_native_history(
                        state, int(frame_index), num_maskmem=int(predictor.num_maskmem),
                        memory_stride=int(predictor.memory_temporal_stride_for_eval),
                        max_obj_ptrs=int(predictor.max_obj_ptrs_in_encoder), max_cond_frames=max_cond_frames)
                    maximum_native_records = max(maximum_native_records, max(
                        (sum(len(records) for records in storage.values())
                         for storage in state["output_dict_per_obj"].values()), default=0))
                    calls["propagated_frame_outputs"] += 1
                # Native remove_object renumbers internal indices only. External
                # IDs and all previously published track evidence stay stable.
                for ident in list(state["obj_ids"]):
                    if end - last_visible[ident] >= retire_after:
                        predictor.remove_object(state, ident, strict=True, need_output=False)
                        tracks[str(ident)].update({"retired_frame": end,
                                                  "retirement_reason": "consecutive_empty_native_masks"})
            else:
                # Real AMG zero-proposal result, not invented propagated masks.
                boundary_masks = {}
                for frame_index in range(keyframe, end + 1):
                    _write_mask_frame(mask_directory / f"{frame_index:05d}.npz", {}, (height, width))
                    written_frames.add(frame_index)
            keyframes.append({"frame_index": keyframe, "source_frame_index": decoded["source_frame_indices"][keyframe],
                              "timestamp_s": decoded["timestamps_s"][keyframe], **counts,
                              "matched_existing": len(associations), "new_tracks": new_count,
                              "total_tracks": len(tracks), "associations": updates,
                              "automatic_generation_s": amg_seconds, "mask_seeding_s": seed_seconds,
                              "propagation_s": time.perf_counter() - propagation_started,
                              "propagation_start": keyframe, "propagation_end_inclusive": end})
    if written_frames != set(range(len(frames))):
        raise RuntimeError("Video predictor did not provide every sampled frame")
    ordered = ReadThroughSequence(
        [mask_directory / f"{index:05d}.npz" for index in range(len(frames))],
        _read_mask_frame, decoded_cache_size)
    for item in tracks.values():
        item.update({"visible_frame_indices": [], "first_frame": None, "last_frame": None,
                     "visible_frames": 0, "minimum_area_px": 0, "maximum_area_px": 0})
    # One streaming pass computes per-track summaries without retaining the
    # clip's expanded masks (packed files remain the source of truth).
    for index, frame in enumerate(ordered):
        for ident, mask in frame.items():
            area = int(mask.sum())
            if not area:
                continue
            item = tracks[str(ident)]
            item["visible_frame_indices"].append(index)
            if item["first_frame"] is None:
                item["first_frame"] = index
            item["last_frame"] = index
            item["visible_frames"] += 1
            item["minimum_area_px"] = min(item["minimum_area_px"], area) if item["minimum_area_px"] else area
            item["maximum_area_px"] = max(item["maximum_area_px"], area)
    (output / "tracks.json").write_text(json.dumps(tracks, indent=2, sort_keys=True) + "\n")
    manifest = [{"path": str(path.relative_to(output)), "sha256": _sha(path), "bytes": path.stat().st_size}
                for path in sorted(output.rglob("*")) if path.is_file()]
    try:
        sam_version = importlib.metadata.version("SAM-2")
    except importlib.metadata.PackageNotFoundError:
        sam_version = "unavailable"
    return {"format_version": FORMAT_VERSION, "owner": CACHE_OWNER, "state": "complete",
            "identity": identity, "input_path": str(input_path), "model_id": sam["model_id"],
            "model_source": provenance, "model_config": sam["model_config"], "device": device, "dtype": "float32",
            "tracking_config": tracking_config(config), "decoded": decoded,
            "versions": {"torch": torch.__version__, "torchvision": torchvision.__version__,
                         "numpy": np.__version__, "opencv": cv2.__version__, "sam2": sam_version},
            "backend_parameters": {"apply_postprocessing": False, "vos_optimized": False,
                                   "offload_video_to_cpu": True, "offload_state_to_cpu": True,
                                   "add_all_frames_to_correct_as_cond": True,
                                   "max_cond_frames_in_attn": max_cond_frames,
                                   "video_frame_cache_size": video_cache_size,
                                   "decoded_frame_cache_size": decoded_cache_size,
                                   "native_history_radius_frames": history_radius,
                                   "retire_after_empty_frames": retire_after,
                                   "maximum_tracks_scope": "simultaneously active native objects; IDs never reused",
                                   "native_initialization": "official init_state on first source JPEG; exact eager-equivalent lazy FP32 image Sequence",
                                   "mask_storage": "packed NPZ per frame, boundary correction replaces same frame",
                                   "amg_grid": "uniform over the full frame", "amg_crop_n_layers": 0},
            "keyframes": keyframes, "calls": calls, "track_count": len(tracks),
            "maximum_active_tracks": maximum_active_tracks,
            "maximum_native_history_records_per_object": maximum_native_records,
            "retired_track_count": sum("retired_frame" in item for item in tracks.values()),
            "foreground_tracks": sum(item["role"] == "foreground" for item in tracks.values()),
            "background_surface_tracks": sum(item["role"] == "background_surface" for item in tracks.values()),
            "mask_frame_count": sum(len(frame) for frame in ordered),
            "nonempty_mask_frames": sum(bool(mask.any()) for frame in ordered for mask in frame.values()),
            "model_parameter_count": sum(parameter.numel() for parameter in predictor.parameters()),
            "result_fingerprint": tracking_fingerprint(ordered, decoded["source_frame_indices"]),
            "timings_s": {"decode": decode_seconds, "model_load": model_load_seconds,
                          "video_state_init": state_init_seconds}, "files": manifest,
            "limitations": ["Automatic grid masks do not guarantee every physical object is segmented.",
                            "Stable IDs are SAM video object IDs associated across keyframes by mask geometry; semantic identity after occlusion is not guaranteed.",
                            "Foreground/background roles are configured image-geometry hypotheses, not semantic road/sky labels; role_at(history,frame) is causal and the scalar role is only a final summary."]}


def track_clip(input_path: str | Path, config: dict, cache_dir: str | Path,
               limit_frames: int | None = None, force: bool = False) -> dict:
    """Run real SAM tracking or reuse an exactly matching, verified cache."""
    config = copy.deepcopy(config)
    checkpoint = Path(config["sam"]["checkpoint"]).expanduser().resolve()
    if not checkpoint.is_file():
        raise CheckpointUnavailable(f"Native SAM 2.1 checkpoint is unavailable: {checkpoint}. "
                                    "No inference or checkpoint download was attempted.")
    input_path, cache_dir = Path(input_path).resolve(), Path(cache_dir).resolve()
    if not input_path.is_file():
        raise ValueError(f"Input clip is unavailable: {input_path}")
    if input_path.is_relative_to(cache_dir) or checkpoint.is_relative_to(cache_dir):
        raise CacheMismatch("Input video and checkpoint must be outside the replaceable tracker cache")
    identity = {"source_sha256": _sha(input_path), "checkpoint_sha256": _sha(checkpoint),
                "tracking_config_sha256": _json_hash(tracking_config(config)),
                "tracker_code_sha256": _sha(Path(__file__)), "limit_frames": limit_frames}
    with _cache_lock(cache_dir):
        before = _directory_signature(cache_dir)
        metadata_path = cache_dir / "metadata.json"
        if before:
            if not metadata_path.is_file():
                raise CacheMismatch("Refusing to replace a nonempty directory without tracker metadata")
            recorded = json.loads(metadata_path.read_text())
            if recorded.get("owner") != CACHE_OWNER:
                raise CacheMismatch("Refusing to replace an unrelated cache")
            if recorded.get("identity") == identity and not force:
                load_tracking(cache_dir)
                return recorded
            if not force:
                raise CacheMismatch("Tracking inputs/config/checkpoint/code differ; use force=True for an explicit development rerun")
        work = Path(tempfile.mkdtemp(prefix=f".{cache_dir.name}.tracking-", dir=cache_dir.parent))
        try:
            metadata = _run(input_path, config, work, checkpoint, identity, limit_frames)
            if _sha(input_path) != identity["source_sha256"] or _sha(checkpoint) != identity["checkpoint_sha256"]:
                raise CacheMismatch("Input video or checkpoint changed during inference")
            (work / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True, allow_nan=False) + "\n")
            if _directory_signature(cache_dir) != before:
                raise CacheMismatch("Cache destination changed during inference; refusing replacement")
            # An incomplete/failed inference never replaces a complete cache.
            old = None
            if cache_dir.exists():
                old = cache_dir.with_name(f".{cache_dir.name}.previous-{uuid.uuid4().hex}")
                cache_dir.rename(old)
            try:
                work.rename(cache_dir)
            except BaseException:
                if old is not None:
                    old.rename(cache_dir)
                raise
            if old is not None:
                shutil.rmtree(old)
            return metadata
        finally:
            if work.exists():
                shutil.rmtree(work)
            gc.collect()


def load_tracking(cache_dir: str | Path) -> dict:
    """Load verified real tracking artifacts, without loading model weights."""
    cache_dir = Path(cache_dir).resolve()
    metadata = json.loads((cache_dir / "metadata.json").read_text())
    if metadata.get("owner") != CACHE_OWNER or metadata.get("state") != "complete" or metadata.get("format_version") != FORMAT_VERSION:
        raise CacheMismatch("Tracking cache is not a completed supported artifact")
    for entry in metadata["files"]:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise CacheMismatch("Cache manifest contains a nonlocal path")
        path = cache_dir / relative
        if not path.is_file() or path.stat().st_size != entry["bytes"] or _sha(path) != entry["sha256"]:
            raise CacheMismatch(f"Tracking cache file hash/size differs: {relative}")
    count = int(metadata["decoded"]["sampled_frames"])
    cache_size = int(metadata["tracking_config"]["sam"].get("decoded_frame_cache_size", 8))
    frames = ReadThroughSequence([cache_dir / "frames" / f"{index:05d}.jpg" for index in range(count)],
                                 _read_rgb, cache_size)
    masks = ReadThroughSequence([cache_dir / "masks" / f"{index:05d}.npz" for index in range(count)],
                                _read_mask_frame, cache_size)
    if tracking_fingerprint(masks, metadata["decoded"]["source_frame_indices"]) != metadata["result_fingerprint"]:
        raise CacheMismatch("Tracking result fingerprint differs")
    tracks = json.loads((cache_dir / "tracks.json").read_text())
    if any(not item.get("role_history") for item in tracks.values()):
        raise CacheMismatch("Tracking cache lacks causal per-frame role history")
    return {"frames": frames, "timestamps_s": metadata["decoded"]["timestamps_s"],
            "masks": masks, "tracks": tracks, "metadata": metadata}
