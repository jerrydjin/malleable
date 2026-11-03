"""Preregistered Phase 16b detection rule. Constants come from prereg.json."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PREREG = Path(__file__).resolve().parent / "prereg.json"


def load_prereg(path=PREREG):
    return json.loads(Path(path).read_text())


def polygon_area(polygon):
    total = 0
    for i, (x, y) in enumerate(polygon):
        x2, y2 = polygon[(i + 1) % len(polygon)]
        total += x * y2 - x2 * y
    return abs(total) / 2


def point_in_polygon(x, y, polygon):
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i
    return inside


def median(values):
    ys = sorted(values)
    n = len(ys)
    if n == 0:
        return None
    if n % 2 == 1:
        return ys[n // 2]
    return (ys[n // 2 - 1] + ys[n // 2]) / 2


def evaluate(frames, threshold, need):
    """frames are dicts with lane_pixels and source_s, in time order.

    A frame is positive when lane_pixels >= threshold. detected is true when
    some consecutive run is at least `need` frames. since_s is the source time
    of the first frame of the earliest such run. confirm_at_s is the source
    time of the frame on which that run first reaches `need`.
    """
    run = 0
    best = 0
    positive = 0
    since = None
    confirm = None
    run_start = None
    areas = []
    for frame in frames:
        area = frame["lane_pixels"]
        areas.append(area)
        if area >= threshold:
            positive += 1
            if run == 0:
                run_start = frame["source_s"]
            run += 1
            if run > best:
                best = run
            if run == need and confirm is None:
                confirm = frame["source_s"]
                since = run_start
        else:
            run = 0
            run_start = None
    return {
        "positive_frames": positive,
        "longest_consecutive_positive": best,
        "detected": best >= need,
        "since_s": since,
        "confirm_at_s": confirm,
        "max_lane_pixels": max(areas) if areas else 0,
        "median_lane_pixels": median(areas),
        "sampled_frames": len(frames),
    }
