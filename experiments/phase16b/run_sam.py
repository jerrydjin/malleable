#!/usr/bin/env python3
"""Run preregistered SAM 2.1 tiny prompts on clips A, B and C.

Refuses to start unless prereg.json is committed and clean. Does not edit
thresholds. CPU only.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw
import numpy as np

from rules import evaluate, load_prereg, point_in_polygon, polygon_area


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "experiments" / "phase16b"
MASKS = OUT / "masks"
FRAMES = OUT / "output"
OVERLAYS = OUT / "overlays"


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_committed_prereg():
    rel = "experiments/phase16b/prereg.json"
    md = "experiments/phase16b/prereg.md"
    for path in (rel, md):
        probe = subprocess.run(["git", "cat-file", "-e", f"HEAD:{path}"], cwd=ROOT)
        if probe.returncode != 0:
            raise SystemExit(f"{path} is not in HEAD; commit the preregistration before SAM")
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--", rel, md], cwd=ROOT, text=True
    )
    if dirty.strip():
        raise SystemExit("preregistration is dirty; commit it before SAM")
    recorded = FRAMES / "prereg.sha256"
    current = sha256(OUT / "prereg.json")
    if recorded.exists() and recorded.read_text().strip() != current:
        raise SystemExit("prereg.json changed after a SAM run started; refusing to continue")
    FRAMES.mkdir(parents=True, exist_ok=True)
    recorded.write_text(current + "\n")
    return current


def ffmpeg_frames(clip, dest, stride):
    dest.mkdir(parents=True, exist_ok=True)
    existing = sorted(dest.glob("f*.png"))
    if existing:
        return existing
    subprocess.check_call(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(clip),
            "-vf", f"select=not(mod(n\\,{stride}))", "-vsync", "vfr",
            str(dest / "f%04d.png"),
        ]
    )
    return sorted(dest.glob("f*.png"))


def lane_raster(width, height, polygon):
    image = Image.new("L", (width, height), 0)
    ImageDraw.Draw(image).polygon([tuple(p) for p in polygon], fill=255)
    return np.asarray(image) > 0


def load_model(model_id):
    os.environ.pop("HF_HUB_OFFLINE", None)
    os.environ.pop("TRANSFORMERS_OFFLINE", None)
    import torch
    import transformers
    from huggingface_hub import snapshot_download
    from transformers import Sam2Model, Sam2Processor

    snapshot = Path(snapshot_download(model_id))
    revision = snapshot.name
    torch.manual_seed(0)
    torch.set_num_threads(1)
    processor = Sam2Processor.from_pretrained(str(snapshot), local_files_only=True)
    model = Sam2Model.from_pretrained(
        str(snapshot), local_files_only=True, torch_dtype=torch.float32
    ).to("cpu").eval()
    return {
        "torch": torch,
        "processor": processor,
        "model": model,
        "revision": revision,
        "torch_version": torch.__version__,
        "transformers_version": transformers.__version__,
    }


def segment(bundle, image, point):
    torch = bundle["torch"]
    processor = bundle["processor"]
    model = bundle["model"]
    x, y = point
    started = time.perf_counter()
    inputs = processor(
        images=image,
        input_points=[[[[x, y]]]],
        input_labels=[[[1]]],
        return_tensors="pt",
    ).to("cpu")
    with torch.inference_mode():
        outputs = model(**inputs, multimask_output=False)
    scores = outputs.iou_scores.detach().cpu().reshape(-1).tolist()
    masks = processor.post_process_masks(
        outputs.pred_masks.detach().cpu(),
        inputs["original_sizes"].cpu(),
        mask_threshold=0.0,
        binarize=True,
    )[0]
    infer_s = time.perf_counter() - started
    mask = masks.reshape(image.height, image.width).to(torch.uint8).numpy()
    return mask > 0, scores, infer_s


def save_mask(path, mask):
    Image.fromarray(mask.astype(np.uint8) * 255).save(path)


def bbox_and_fraction(mask):
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None, 0.0
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], float(mask.mean())


def overlay_video(frames, clip_id):
    OVERLAYS.mkdir(parents=True, exist_ok=True)
    directory = OVERLAYS / f"_{clip_id}"
    directory.mkdir(parents=True, exist_ok=True)
    for i, frame in enumerate(frames):
        image = np.array(Image.open(frame["png"]).convert("RGB"))
        mask = np.asarray(Image.open(frame["mask_path"]).convert("L")) > 0
        red = image.copy()
        red[mask] = (0.55 * red[mask] + 0.45 * np.array([255, 40, 40])).astype(np.uint8)
        drawn = Image.fromarray(red)
        pen = ImageDraw.Draw(drawn)
        polygon = frame["polygon"]
        pen.line([tuple(p) for p in polygon] + [tuple(polygon[0])], fill=(0, 220, 80), width=3)
        x, y = frame["point"]
        pen.ellipse((x - 8, y - 8, x + 8, y + 8), outline=(255, 220, 0), width=3)
        drawn.save(directory / f"{i:04d}.png")
    dest = OVERLAYS / f"{clip_id}.mp4"
    subprocess.check_call(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-framerate", "3",
            "-i", str(directory / "%04d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dest),
        ]
    )
    for png in directory.glob("*.png"):
        png.unlink()
    directory.rmdir()
    return dest


def main():
    os.chdir(ROOT)
    prereg_hash = require_committed_prereg()
    prereg = load_prereg()
    if polygon_area(prereg["lane_polygon_xy"]) != prereg["lane_polygon_area_px"]:
        raise SystemExit("lane polygon area does not match prereg.json")
    for clip, point in prereg["points_xy"].items():
        if not point_in_polygon(point[0], point[1], prereg["lane_polygon_xy"]):
            raise SystemExit(f"point for {clip} is outside the lane polygon")
    print("loading SAM", prereg["sam_model_id"], flush=True)
    bundle = load_model(prereg["sam_model_id"])
    versions = {
        "model_id": prereg["sam_model_id"],
        "hf_revision": bundle["revision"],
        "torch_version": bundle["torch_version"],
        "transformers_version": bundle["transformers_version"],
        "device": "cpu",
        "dtype": "float32",
        "seed": 0,
        "torch_threads": 1,
        "prereg_sha256": prereg_hash,
    }
    (FRAMES / "versions.json").write_text(json.dumps(versions, indent=2) + "\n")
    print(json.dumps(versions), flush=True)
    lane = None
    summaries = []
    for clip_id, clip in prereg["clips"].items():
        video = OUT / "footage" / f"clip_{clip_id}.mp4"
        extracted = ffmpeg_frames(video, FRAMES / f"sampled-{clip_id}", prereg["frame_stride"])
        expected = (clip["nb_frames"] + prereg["frame_stride"] - 1) // prereg["frame_stride"]
        if len(extracted) != expected:
            raise SystemExit(f"{clip_id}: expected {expected} sampled frames, got {len(extracted)}")
        point = prereg["points_xy"][clip_id]
        mask_dir = MASKS / clip_id
        mask_dir.mkdir(parents=True, exist_ok=True)
        rows = []
        for ordinal, png in enumerate(extracted):
            index = ordinal * prereg["frame_stride"]
            source_s = clip["start_s"] + index / prereg["source_fps"]
            mask_path = mask_dir / f"{index:04d}.png"
            with Image.open(png) as raw:
                image = raw.convert("RGB")
            if lane is None:
                lane = lane_raster(image.width, image.height, prereg["lane_polygon_xy"])
            if mask_path.exists() and (mask_dir / f"{index:04d}.json").exists():
                meta = json.loads((mask_dir / f"{index:04d}.json").read_text())
                print(f"{clip_id} frame {index} cached {meta['lane_pixels']} px", flush=True)
            else:
                mask, scores, infer_s = segment(bundle, image, point)
                lane_pixels = int(np.logical_and(mask, lane).sum())
                save_mask(mask_path, mask)
                meta = {
                    "clip": clip_id,
                    "index": index,
                    "source_s": source_s,
                    "lane_pixels": lane_pixels,
                    "infer_s": infer_s,
                    "iou_scores": scores,
                    "mask_sha256": sha256(mask_path),
                    "point_xy": point,
                }
                (mask_dir / f"{index:04d}.json").write_text(json.dumps(meta) + "\n")
                print(
                    f"{clip_id} frame {index} lane_pixels={lane_pixels} infer_s={infer_s:.3f}",
                    flush=True,
                )
            meta["png"] = str(png)
            meta["mask_path"] = str(mask_path.relative_to(ROOT))
            meta["polygon"] = prereg["lane_polygon_xy"]
            meta["point"] = point
            rows.append(meta)
        decision = evaluate(
            rows, prereg["threshold_lane_pixels"], prereg["consecutive_required"]
        )
        best = max(rows, key=lambda row: (row["lane_pixels"], -row["index"]))
        best_image = Image.open(best["png"]).convert("RGB")
        evidence_dir = FRAMES / clip_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        evidence_png = evidence_dir / "evidence.png"
        evidence_mask = evidence_dir / "evidence-mask.png"
        best_image.save(evidence_png)
        evidence_mask.write_bytes((ROOT / best["mask_path"]).read_bytes())
        mask_img = np.asarray(Image.open(evidence_mask).convert("L")) > 0
        box, fraction = bbox_and_fraction(mask_img)
        cache = {
            "version": 1,
            "model_id": prereg["sam_model_id"],
            "hf_revision": bundle["revision"],
            "torch_version": bundle["torch_version"],
            "transformers_version": bundle["transformers_version"],
            "device": "cpu",
            "dtype": "float32",
            "seed": 0,
            "torch_threads": 1,
            "prompt_points": [point],
            "prompt_labels": [1],
            "multimask_output": False,
            "mask_threshold": 0.0,
            "iou_scores": best["iou_scores"],
            "bbox_xyxy_inclusive": box,
            "area_fraction": fraction,
            "image_size_wh": [best_image.width, best_image.height],
            "source_url": "https://commons.wikimedia.org/wiki/File:400_SB_Crash.webm",
            "image_path": str(evidence_png.relative_to(ROOT)),
            "mask_path": str(evidence_mask.relative_to(ROOT)),
            "image_sha256": sha256(evidence_png),
            "mask_sha256": sha256(evidence_mask),
            "clip": clip_id,
            "viewpoint": clip["role"],
            "evidence_index": best["index"],
            "evidence_source_s": best["source_s"],
            "evidence_lane_pixels": best["lane_pixels"],
        }
        (evidence_dir / "sam.json").write_text(json.dumps(cache, indent=2) + "\n")
        frame_doc = {
            "clip": clip_id,
            "role": clip["role"],
            "decision": decision,
            "frames": [
                {k: v for k, v in row.items() if k not in ("png", "polygon", "point")}
                for row in rows
            ],
        }
        (FRAMES / f"frames-{clip_id}.json").write_text(json.dumps(frame_doc, indent=2) + "\n")
        overlay_video(rows, clip_id)
        summaries.append({
            "id": clip_id,
            "role": clip["role"],
            "source_window_s": [clip["start_s"], clip["start_s"] + clip["duration_s"]],
            "prompt_point_xy": point,
            "lane_polygon_xy": prereg["lane_polygon_xy"],
            **decision,
        })
        print(clip_id, json.dumps(decision), flush=True)
    summary = {
        "task": "Write only a hazard label and a reach. Do not decide merge and do not move a vehicle.",
        "sam_model_id": prereg["sam_model_id"],
        "threshold_lane_pixels": prereg["threshold_lane_pixels"],
        "consecutive_required": prereg["consecutive_required"],
        "frame_stride": prereg["frame_stride"],
        "viewpoint_note": "B is the SAME SOURCE, DIFFERENT VIEWPOINT. It is not a second vehicle and not an independent camera.",
        "clips": summaries,
    }
    (FRAMES / "detection-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (FRAMES / "versions.json").write_text(json.dumps(versions, indent=2) + "\n")
    for clip_id in prereg["clips"]:
        sampled = FRAMES / f"sampled-{clip_id}"
        if sampled.is_dir():
            for png in sampled.glob("*.png"):
                png.unlink()
            sampled.rmdir()
    print("SAM done", flush=True)


if __name__ == "__main__":
    sys.exit(main())
