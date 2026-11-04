"""Auditable exports of measured mapping results; never inference or rescoring.

Colours represent each frame's measured class. Labels may be added after motion
analysis, and never feed back into a motion measurement or an edit decision.
Confidence values elsewhere in these artifacts are heuristics, not probabilities.
"""
from __future__ import annotations

import csv
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

VIEWPOINT_B = "same source, different viewpoint"
COLOURS = {"MOVING": (35, 165, 255), "STATIONARY": (255, 75, 70),
           "UNKNOWN": (245, 205, 60)}
PROPOSED_EDIT_COLOUR = (255, 135, 15)
CSV_FIELDS = ["clip", "viewpoint_note", "track_id", "role", "first_frame", "last_frame",
              "source_start_s", "source_end_s", "observed_span_s", "observations",
              "stationary_frames", "moving_frames", "unknown_frames",
              "longest_stationary_run", "longest_moving_run", "longest_supported_moving_run",
              "required_stationary_motion_frames", "required_moving_motion_frames",
              "moving_require_lower_band_support", "motion_confirmation_policy",
              "residual_flow_median_px",
              "relative_residual_median", "lane", "class", "label", "label_source",
              "confidence_median", "confidence_kind", "edit_emitted", "visibility_note",
              "source_sha256", "tracking_result_fingerprint"]


def _plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Unsupported artifact value: {type(value).__name__}")


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, default=_plain)


def _hash_json(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _sidecar(path, record):
    path = Path(path)
    sidecar = path.with_suffix(path.suffix + ".json")
    temporary = sidecar.with_suffix(sidecar.suffix + ".tmp")
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True, allow_nan=False,
                                    default=_plain) + "\n")
    temporary.replace(sidecar)


def _edit_rows(edits):
    if edits is None:
        return []
    if isinstance(edits, dict) and "edits" not in edits:
        raise ValueError("Adapter object lacks an edits result")
    rows = edits["edits"] if isinstance(edits, dict) else edits
    if not isinstance(rows, (list, tuple)):
        raise ValueError("edits must be a list or an adapter object containing edits")
    return list(rows)


def _key(row):
    return str(row["clip"]), int(row["track_id"])


def _edit_index(edits):
    result = {}
    for row in _edit_rows(edits):
        key = _key(row)
        if key in result:
            raise ValueError(f"Duplicate edit for {key}")
        result[key] = row
    return result


def _label(clip, ident, summary, labels, indexed_edits):
    """Only actual adapter provenance can identify a model-produced label."""
    edit = indexed_edits.get((str(clip), int(ident)))
    if edit:
        text = edit.get("evidence", {}).get("label")
        source = edit.get("label_provenance", {}).get("source", "unspecified")
        if text:
            return str(text), str(source)
    value = None
    if labels:
        value = labels.get((str(clip), int(ident)))
        if value is None and isinstance(labels.get(str(clip)), dict):
            value = labels[str(clip)].get(int(ident), labels[str(clip)].get(str(ident)))
    if value is not None:
        return str(value.get("label", "") if isinstance(value, dict) else value), "annotation"
    return str(summary.get("label", "unlabelled object")), "unlabelled"


def _viewpoint(clip, analysis):
    return VIEWPOINT_B if str(clip) == "B" else str(analysis.get("viewpoint_note", ""))


def _provenance(bundle):
    metadata = bundle.get("metadata", {})
    return {"source_sha256": metadata.get("identity", {}).get("source_sha256"),
            "tracking_result_fingerprint": metadata.get("result_fingerprint"),
            "tracking_identity": metadata.get("identity", {}),
            "tracking_model_id": metadata.get("model_id"),
            "tracking_timings_s": metadata.get("timings_s", {})}


def _cadence(bundle):
    timestamps = np.asarray(bundle["timestamps_s"], dtype=float)
    if not len(timestamps) or not np.isfinite(timestamps).all():
        raise ValueError("Overlay requires finite source timestamps and at least one frame")
    if len(timestamps) > 1:
        deltas = np.diff(timestamps)
        if np.any(deltas <= 0):
            raise ValueError("Source timestamps must strictly increase")
        spacing = float(np.median(deltas))
        if not np.allclose(deltas, spacing, rtol=1e-5, atol=1e-8):
            raise ValueError("Nonuniform source timestamps require a variable-frame-rate export")
    else:
        metadata = bundle.get("metadata", {})
        source_fps = metadata.get("decoded", {}).get("source_fps")
        stride = metadata.get("tracking_config", {}).get("frame_stride")
        if not source_fps or not stride:
            raise ValueError("A single-frame export requires source fps and sampling stride metadata")
        spacing = float(stride) / float(source_fps)
    if not np.isfinite(spacing) or spacing <= 0:
        raise ValueError("Invalid source frame spacing")
    return timestamps, Fraction(1.0 / spacing).limit_denominator(100000)


def _font(size):
    # DejaVu is deterministic when installed; Pillow's bundled font is a fallback.
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default(size=size)


def _wrap(text, font, width):
    """Wrap every character instead of silently truncating an object label."""
    lines, line = [], ""
    for character in str(text).replace("\n", " "):
        if line and font.getlength(line + character) > width:
            lines.append(line)
            line = ""
        line += character
    return lines + [line]


def _proposed_edit_marker(edit, frame, frame_count, shape):
    """Keep recorded proposal geometry distinct from a later tracking badge."""
    if edit is None or edit.get("status") != "Proposed":
        return None
    position = edit.get("position", {})
    reference = position.get("reference_frame")
    if not isinstance(edit.get("id"), str) or not edit["id"]:
        raise ValueError("Proposed edit marker requires the actual edit ID")
    if (type(reference) is not int or not 0 <= reference < frame_count
            or position.get("coordinate_system") != "road_reference_image"):
        raise ValueError("Proposed edit marker requires a valid reference image frame")
    try:
        point = [float(position["x_px"]), float(position["y_px"])]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Proposed edit marker requires finite reference image coordinates") from error
    if not np.isfinite(point).all():
        raise ValueError("Proposed edit marker requires finite reference image coordinates")
    if frame < reference:
        return None
    h, w = shape[:2]
    visible = bool(0 <= point[0] < w and 0 <= point[1] < h)
    return {"edit_id": edit["id"], "status": "Proposed", "reference_frame": reference,
            "reference_position_xy": point, "coordinate_system": "road_reference_image",
            "reference_position_visible": visible,
            "draw_reference_position": frame == reference and visible,
            "badge_position_source": "current_visible_mask_bounds"}


def _observations(bundle, analysis, clip, cfg, labels, edits):
    frames, masks = bundle["frames"], bundle["masks"]
    if not len(frames) or len(frames) != len(masks) or len(frames) != len(bundle["timestamps_s"]):
        raise ValueError("Overlay requires matching, nonempty frame/mask/timestamp sequences")
    if int(analysis.get("frame_count", len(frames))) != len(frames):
        raise ValueError("Analysis frame count differs from tracking bundle")
    if str(analysis.get("clip", clip)) != str(clip):
        raise ValueError("Analysis belongs to a different clip")
    summaries = {int(row["track_id"]): row for row in analysis.get("tracks", [])}
    indexed = {}
    for row in analysis.get("observations", []):
        key = int(row["frame"]), int(row["track_id"])
        if key in indexed:
            raise ValueError(f"Duplicate observation {key}")
        if str(row.get("clip", clip)) != str(clip):
            raise ValueError("Observation belongs to a different clip")
        indexed[key] = row
    edit_lookup = _edit_index(edits)
    records = []
    clip_settings = cfg.get("clips", {}).get(str(clip), {})
    offsets = [float(row["source_s"])-float(bundle["timestamps_s"][index])
               for (index, _), row in indexed.items()
               if row.get("source_s") is not None and 0 <= index < len(frames)]
    source_start = float(clip_settings.get("source_start_s", offsets[0] if offsets else 0.))
    shape = frames[0].shape
    if len(shape) != 3 or shape[2] != 3:
        raise ValueError("Overlay frames must be RGB images")
    for index, (rgb, objects) in enumerate(zip(frames, masks)):
        if rgb.shape != shape or rgb.dtype != np.uint8:
            raise ValueError("Overlay frames must be equally sized uint8 RGB images")
        items, source_times = [], []
        for ident, raw_mask in sorted(objects.items(), key=lambda item: int(item[0])):
            ident = int(ident)
            mask = np.asarray(raw_mask, dtype=bool)
            if mask.shape != shape[:2]:
                raise ValueError("Mask shape differs from image")
            if not mask.any():
                continue
            row = indexed.get((index, ident))
            if row is None:
                raise ValueError(f"Missing measurement for visible mask {index}/{ident}")
            kind = row.get("class", "UNKNOWN")
            if kind not in COLOURS:
                raise ValueError(f"Unknown motion class {kind}")
            if row.get("source_s") is not None:
                source_times.append(float(row["source_s"]))
            text, source = _label(clip, ident, summaries.get(ident, {}), labels, edit_lookup)
            item = {"track_id": ident, "class": kind,
                    "role": row.get("role", summaries.get(ident, {}).get("role", "unknown")),
                    "lane": row.get("lane", "unknown"),
                    "label": text, "label_source": source,
                    "confidence": row.get("confidence"), "mask_area_px": int(mask.sum())}
            marker = _proposed_edit_marker(edit_lookup.get((str(clip), ident)), index, len(frames), shape)
            if marker is not None:
                item["proposed_edit"] = marker
            items.append(item)
        if source_times and not np.allclose(source_times, source_times[0], atol=1e-7, rtol=0):
            raise ValueError("Observations disagree on source timestamp")
        source_s = source_times[0] if source_times else source_start + float(bundle["timestamps_s"][index])
        records.append({"frame": index, "timestamp_s": float(bundle["timestamps_s"][index]),
                        "source_s": source_s, "viewpoint_note": _viewpoint(clip, analysis), "objects": items})
    offsets = [row["source_s"]-row["timestamp_s"] for row in records]
    if not np.allclose(offsets, offsets[0], atol=1e-7, rtol=0):
        raise ValueError("Observation source times disagree with tracking timestamps")
    return records


def _render_frame(rgb, objects, record, font, width, height, banner_lines, footer_lines, alpha):
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    top = (len(banner_lines) + 1) * 18
    h, w = rgb.shape[:2]
    image = rgb.copy()
    # Draw large surfaces first so smaller objects keep their class fill visible.
    draw_order = sorted(record["objects"], key=lambda item: (-item["mask_area_px"], item["track_id"]))
    for item in draw_order:
        mask = np.asarray(objects.get(item["track_id"], objects.get(str(item["track_id"]))), dtype=bool)
        colour = np.asarray(COLOURS[item["class"]], dtype=np.float32)
        image[mask] = np.rint((1-alpha)*image[mask] + alpha*colour).astype(np.uint8)
    # Draw all contours after fills, so overlapping masks retain visible outlines.
    for item in draw_order:
        mask = np.asarray(objects.get(item["track_id"], objects.get(str(item["track_id"]))), dtype=np.uint8)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(image, contours, -1, COLOURS[item["class"]], 1)
    canvas[top:top+h, :w] = image
    pil = Image.fromarray(canvas)
    draw = ImageDraw.Draw(pil)
    for line, text in enumerate(banner_lines):
        draw.text((6, 3+line*18), text, fill=(255, 255, 255), font=font)
    draw.text((6, 3+len(banner_lines)*18),
              f'frame {record["frame"]} | source {record["source_s"]:.3f} s',
              fill=(255, 255, 255), font=font)
    label_positions = {}
    for item in record["objects"]:
        mask = np.asarray(objects.get(item["track_id"], objects.get(str(item["track_id"]))), dtype=bool)
        y, x = np.nonzero(mask)
        text = f'#{item["track_id"]} {item["class"]}'
        position = (min(int(x.min()), max(0, w-int(font.getlength(text))-4)), top+int(y.min()))
        box = draw.textbbox(position, text, font=font)
        draw.rectangle(box, fill=(0, 0, 0))
        draw.text(position, text, fill=COLOURS[item["class"]], font=font)
        label_positions[item["track_id"]] = (position, box)
    # Proposal badges follow the track label and are painted after all ordinary
    # labels so a neighbouring track cannot cover the proposal status.
    for item in record["objects"]:
        if item.get("proposed_edit") is not None:
            badge = "PROPOSED EDIT"
            # This badge follows the visible track; it is not a new edit pose.
            position, label_box = label_positions[item["track_id"]]
            badge_x = label_box[2] + 5
            if badge_x + font.getlength(badge) + 3 <= w:
                badge_position = (badge_x, position[1])
            else:
                badge_position = (min(position[0], max(0, w-int(font.getlength(badge))-4)),
                                  min(position[1]+17, top+h-17))
            badge_box = draw.textbbox(badge_position, badge, font=font)
            draw.rectangle((badge_box[0]-2, badge_box[1]-1, badge_box[2]+2, badge_box[3]+1),
                           fill=(0, 0, 0), outline=PROPOSED_EDIT_COLOUR, width=1)
            draw.text(badge_position, badge, fill=PROPOSED_EDIT_COLOUR, font=font)
    # Draw recorded reference positions last, at the actual emission frame only.
    # Reusing this fixed point in later camera views would imply a false pose.
    for item in record["objects"]:
        marker = item.get("proposed_edit")
        if marker is None or not marker["draw_reference_position"]:
            continue
        px, py = marker["reference_position_xy"]
        py += top
        diamond = [(px, py-7), (px+7, py), (px, py+7), (px-7, py), (px, py-7)]
        draw.line(diamond, fill=(0, 0, 0), width=4)
        draw.line(diamond, fill=PROPOSED_EDIT_COLOUR, width=2)
        for line in (((px-9, py), (px+9, py)), ((px, py-9), (px, py+9))):
            draw.line(line, fill=(0, 0, 0), width=4)
            draw.line(line, fill=PROPOSED_EDIT_COLOUR, width=2)
    footer_y = top+h+3
    for kind, text in footer_lines:
        colour = PROPOSED_EDIT_COLOUR if kind == "PROPOSED_EDIT" else COLOURS.get(kind, (230, 230, 230))
        draw.text((6, footer_y), text, fill=colour, font=font)
        footer_y += 18
    return np.asarray(pil)


def render_overlay(bundle, analysis, path, clip, cfg, labels=None, edits=None):
    """Render every visible retained mask at its measured sampling cadence.

    Returns provenance and writes the same metadata to ``<path>.json``. Empty or
    inconsistent input fails before an output video can be published.
    """
    started = time.perf_counter()
    records = _observations(bundle, analysis, clip, cfg, labels, edits)
    timestamps, fps = _cadence(bundle)
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg and ffprobe are required for verified H264 exports")
    settings = cfg.get("outputs", {})
    alpha = float(settings.get("mask_alpha", .35))
    if not 0 < alpha <= 1:
        raise ValueError("outputs.mask_alpha must be in (0, 1]")
    font = _font(13)
    h, w = bundle["frames"][0].shape[:2]
    width = max(w, 480)
    width += width % 2
    banner = _wrap(f"Clip {clip} | {_viewpoint(clip, analysis)}", font, width-12)
    footers = []
    for record in records:
        lines = [(None, "MOVING blue | STATIONARY red | UNKNOWN yellow"),
                 (None, "Confidence is heuristic; labels do not decide motion or merge.")]
        for item in record["objects"]:
            text = f'#{item["track_id"]} {item["class"]} | {item["lane"]} | {item["label"]} [{item["label_source"]}]'
            lines.extend((item["class"], line) for line in _wrap(text, font, width-12))
            marker = item.get("proposed_edit")
            if marker is not None:
                text = f'PROPOSED EDIT {marker["edit_id"]} | emitted frame {marker["reference_frame"]}'
                lines.extend(("PROPOSED_EDIT", line) for line in _wrap(text, font, width-12))
        footers.append(lines)
    height = h + (len(banner)+1)*18 + max(map(len, footers))*18 + 6
    height += height % 2
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="overlay-", dir=path.parent) as directory:
        temporary = Path(directory) / "video.mp4"
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                   "-pixel_format", "rgb24", "-video_size", f"{width}x{height}",
                   "-framerate", str(fps), "-i", "pipe:0", "-an", "-c:v", "libx264",
                   "-preset", str(settings.get("preset", "medium")),
                   "-crf", str(settings.get("crf", 18)), "-pix_fmt", "yuv420p",
                   "-movflags", "+faststart", str(temporary)]
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=errors)
            try:
                for index, record in enumerate(records):
                    rendered = _render_frame(bundle["frames"][index], bundle["masks"][index],
                                             record, font, width, height, banner, footers[index], alpha)
                    process.stdin.write(rendered.tobytes())
                process.stdin.close()
                returncode = process.wait()
            except BaseException:
                process.stdin.close()
                process.kill()
                process.wait()
                raise
            if returncode:
                errors.seek(0)
                raise RuntimeError(f"ffmpeg failed ({returncode}): {errors.read().decode(errors='replace')[-2000:]}")
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-show_streams", "-of", "json", str(temporary)],
                               check=True, capture_output=True, text=True)
        streams = json.loads(probe.stdout)["streams"]
        if len(streams) != 1:
            raise RuntimeError("Overlay must have exactly one video stream")
        stream = streams[0]
        if (stream["codec_name"] != "h264" or stream["pix_fmt"] != "yuv420p"
                or int(stream["nb_frames"]) != len(records)
                or Fraction(stream["avg_frame_rate"]) != fps):
            raise RuntimeError("Overlay verification failed: codec, pixel format, cadence, or count differs")
        temporary.replace(path)
    metadata = {"version": 1, "clip": str(clip), "viewpoint_note": _viewpoint(clip, analysis),
                "output_sha256": _sha(path), "output_bytes": path.stat().st_size,
                "config_sha256": _hash_json(cfg), "analysis_sha256": _hash_json(analysis),
                "outputs_code_sha256": _sha(__file__), **_provenance(bundle),
                "frame_count": len(records), "frames_per_second": str(fps),
                "frame_spacing_s": float(1/fps), "first_timestamp_s": float(timestamps[0]),
                "last_timestamp_s": float(timestamps[-1]), "duration_s": float(len(records)/fps),
                "source_dimensions": [w, h], "canvas_dimensions": [width, height],
                "codec": stream["codec_name"], "pixel_format": stream["pix_fmt"],
                "mask_draw_count": sum(len(row["objects"]) for row in records),
                "proposed_edit_badge_draw_count": sum("proposed_edit" in item for row in records for item in row["objects"]),
                "proposed_edit_reference_point_draw_count": sum(item.get("proposed_edit", {}).get("draw_reference_position", False)
                                                                 for row in records for item in row["objects"]),
                "proposed_edit_marker_rgb": list(PROPOSED_EDIT_COLOUR),
                "proposed_edit_marker_policy": "actual Proposed records only; badge from emission frame, recorded position on emission frame only",
                "confidence_kind": "heuristic", "labels_used_for_motion": False,
                "legend_rgb": {kind: list(colour) for kind, colour in COLOURS.items()},
                "mask_alpha": alpha, "frames": records,
                "elapsed_s": time.perf_counter()-started}
    _sidecar(path, metadata)
    return metadata


def write_tracks_csv(analyses, path, labels=None, edits=None, bundles=None):
    """Export existing aggregate scores verbatim, including retained invisible IDs."""
    started = time.perf_counter()
    analyses = list(analyses.values()) if isinstance(analyses, dict) else list(analyses)
    indexed_edits = _edit_index(edits)
    rows, keys = [], set()
    for analysis in sorted(analyses, key=lambda item: str(item["clip"])):
        clip = str(analysis["clip"])
        bundle = (bundles or {}).get(clip, {})
        summaries = {int(row["track_id"]): row for row in analysis.get("tracks", [])}
        if len(summaries) != len(analysis.get("tracks", [])):
            raise ValueError("Duplicate aggregate track summary")
        ids = set(summaries) | {int(ident) for ident in bundle.get("tracks", {})}
        for ident in sorted(ids):
            summary = summaries.get(ident)
            if summary is None:
                visible = any(np.asarray(frame.get(ident, frame.get(str(ident), []))).any()
                              for frame in bundle.get("masks", []))
                if visible:
                    raise ValueError(f"Visible track {clip}/{ident} lacks an aggregate score")
                track = bundle["tracks"].get(str(ident), bundle["tracks"].get(ident, {}))
                summary = {"role": track.get("role", "unknown"), "class": "UNKNOWN", "lane": "unknown",
                           "observations": 0, "stationary_frames": 0, "moving_frames": 0, "unknown_frames": 0,
                           "longest_stationary_run": 0, "longest_moving_run": 0, "edit_emitted": False,
                           "label": "not visible"}
            key = clip, ident
            if key in keys:
                raise ValueError(f"Duplicate aggregate track {key}")
            keys.add(key)
            label, label_source = _label(clip, ident, summary, labels, indexed_edits)
            row = {field: summary.get(field) for field in CSV_FIELDS}
            start, end = summary.get("source_start_s"), summary.get("source_end_s")
            row.update({"clip": clip, "viewpoint_note": _viewpoint(clip, analysis), "track_id": ident,
                        "label": label, "label_source": label_source, "confidence_kind": "heuristic",
                        "observed_span_s": float(end)-float(start) if start is not None and end is not None else None,
                        "visibility_note": "measured" if ident in summaries else "retained track with zero visible masks",
                        **{key: value for key, value in _provenance(bundle).items() if key in CSV_FIELDS}})
            rows.append(row)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    metadata = {"version": 1, "rows": len(rows), "output_sha256": _sha(path),
                "analyses_sha256": _hash_json(analyses), "outputs_code_sha256": _sha(__file__),
                "scores_recomputed": False, "confidence_kind": "heuristic",
                "elapsed_s": time.perf_counter()-started}
    _sidecar(path, metadata)
    return metadata


def write_edits_jsonl(edits, path):
    """Persist actual adapter edits only; no placeholder edits for missing clips."""
    started = time.perf_counter()
    indexed = _edit_index(edits)
    rows = []
    for key, original in sorted(indexed.items()):
        row = dict(original)
        if key[0] == "B":
            if row.get("viewpoint_note", VIEWPOINT_B) != VIEWPOINT_B:
                raise ValueError("Clip B edit must say same source, different viewpoint")
            row["viewpoint_note"] = VIEWPOINT_B
        rows.append(row)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(_json(row) + "\n" for row in rows))
    metadata = {"version": 1, "rows": len(rows), "output_sha256": _sha(path),
                "adapter_edits_sha256": _hash_json(_edit_rows(edits)),
                "outputs_code_sha256": _sha(__file__), "elapsed_s": time.perf_counter()-started,
                "merge_reviews_applied": 0, "vehicle_motion_actions": 0}
    _sidecar(path, metadata)
    return metadata
