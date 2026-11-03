#!/usr/bin/env python3
"""Write the Phase 16b summary from committed artifacts. No numbers are typed by hand."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "experiments" / "phase16b" / "output"
GATE = ROOT / "docs" / "gates" / "phase-16b-summary.md"
STATUS = ROOT / "experiments" / "phase16b" / "status.json"

PRIOR_STOP = (
    "STOP — Phase 16b Step 1: no complete licensed footage set was acquired and "
    "visually verified in this environment. Wikimedia runtime requests were denied "
    "by the proxy (CONNECT 403), and automatic approval review rejected a subsequent "
    "access retry. Candidate licence descriptions were found, but A/B/C frames, "
    "timestamps, lane obstruction and second viewpoint remain unverified. No SAM "
    "inference, model call or merge experiment was run."
)
SPEC_KEYS = [
    "id", "kind", "link", "route", "author_car", "blocks", "since_s",
    "expires_at", "status", "confirmations", "merged_at",
]


def load(path):
    return json.loads(Path(path).read_text())


def num(value):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value, 3)
    return value


def main():
    prereg = load(ROOT / "experiments/phase16b/prereg.json")
    versions = load(OUT / "versions.json")
    label = load(OUT / "label.json")
    merge = load(OUT / "merge-check.json")
    edit = load(OUT / "edit.json")
    manifest = load(ROOT / "experiments/phase16b/footage/MANIFEST.json")
    frames = {clip: load(OUT / f"frames-{clip}.json") for clip in ("A", "B", "C")}
    summary = {row["id"]: row for row in load(OUT / "detection-summary.json")["clips"]}
    rows = []
    for clip, doc in frames.items():
        infer = [frame["infer_s"] for frame in doc["frames"]]
        rows.append({
            "clip": clip,
            "role": doc["role"],
            "sampled_frames": doc["decision"]["sampled_frames"],
            "positive_frames": doc["decision"]["positive_frames"],
            "longest_consecutive_positive": doc["decision"]["longest_consecutive_positive"],
            "max_lane_pixels": doc["decision"]["max_lane_pixels"],
            "median_lane_pixels": doc["decision"]["median_lane_pixels"],
            "detected": doc["decision"]["detected"],
            "since_s": doc["decision"]["since_s"],
            "confirm_at_s": doc["decision"]["confirm_at_s"],
            "infer_s_sum": sum(infer),
            "infer_s_mean": sum(infer) / len(infer) if infer else None,
            "infer_s_max": max(infer) if infer else None,
        })
    by = {row["clip"]: row for row in rows}
    a_ok = by["A"]["detected"] is True
    b_ok = by["B"]["detected"] is True
    c_ok = by["C"]["detected"] is False
    d_ok = (
        merge["spoof_merged"] is False
        and merge["c_only_merged"] is False
        and merge["b_merged"] is True
        and a_ok
        and b_ok
        and c_ok
    )
    e_ok = (
        merge.get("b_merged") is True
        and edit.get("status") == "Merged"
        and edit.get("kind") == "hazard"
        and all(key in edit for key in SPEC_KEYS)
        and isinstance(edit.get("confirmations"), list)
        and any(item.get("saw_blockage") is True for item in edit["confirmations"])
    )
    raw = label.get("raw_reply")
    f_ok = (
        label.get("source") == "model"
        and label.get("provider") == "baseten"
        and isinstance(label.get("model_id"), str)
        and label.get("model_id")
        and isinstance(label.get("latency_ms"), (int, float))
        and isinstance(raw, str)
        and raw.strip() != ""
    )
    bars = [
        ("a", "A detects by the preregistered rule", a_ok, (
            f"positive {by['A']['positive_frames']}/{by['A']['sampled_frames']}, "
            f"longest run {by['A']['longest_consecutive_positive']} "
            f"(need {prereg['consecutive_required']}), "
            f"max lane pixels {by['A']['max_lane_pixels']} "
            f"(threshold {prereg['threshold_lane_pixels']})"
        )),
        ("b", "B confirms by the same rule. B is the SAME SOURCE, DIFFERENT VIEWPOINT", b_ok, (
            f"positive {by['B']['positive_frames']}/{by['B']['sampled_frames']}, "
            f"longest run {by['B']['longest_consecutive_positive']}, "
            f"max lane pixels {by['B']['max_lane_pixels']}"
        )),
        ("c", "C produces no detection", c_ok, (
            f"positive {by['C']['positive_frames']}/{by['C']['sampled_frames']}, "
            f"longest run {by['C']['longest_consecutive_positive']}, "
            f"max lane pixels {by['C']['max_lane_pixels']}"
        )),
        ("d", "Merge only with B. A spoof and C do not merge", d_ok, (
            f"spoof merged {merge['spoof_merged']}, "
            f"C merged {merge['c_only_merged']}, "
            f"B merged {merge['b_merged']}"
        )),
        ("e", "Merged edit has the SPEC hazard keys", e_ok, (
            f"status {edit.get('status')}, kind {edit.get('kind')}, "
            f"confirmations {len(edit.get('confirmations') or [])}"
        )),
        ("f", "Label and reach come from a live model reply", f_ok, (
            f"source {label.get('source')}, "
            f"fallback_reason {label.get('fallback_reason')}, "
            f"provider {label.get('provider')}, "
            f"model_id {label.get('model_id')}, "
            f"latency_ms {label.get('latency_ms')}"
        )),
    ]
    def word(ok):
        return "PASS" if ok else "FAIL"
    lines = [
        "# Phase 16b",
        "",
        "B is the SAME SOURCE, DIFFERENT VIEWPOINT. It is not a second vehicle and not an independent camera.",
        "",
        "The previous run stopped before this footage was attached. That stop, verbatim:",
        "",
        PRIOR_STOP,
        "",
        "This run used the attached file. It did not download from Wikimedia. The original sha256 is "
        f"`{manifest['original']['sha256']}`.",
        "",
        "## Bars",
        "",
        "| Bar | Result | Numbers |",
        "| --- | --- | --- |",
    ]
    for bar, text, ok, detail in bars:
        lines.append(f"| {bar}. {text} | {word(ok)} | {detail} |")
    lines += [
        "",
        "## Detection",
        "",
        f"Threshold {prereg['threshold_lane_pixels']} lane pixels, "
        f"{prereg['consecutive_required']} consecutive sampled frames, "
        f"stride {prereg['frame_stride']} at {prereg['source_fps']} fps. "
        f"Lane polygon area {prereg['lane_polygon_area_px']} px.",
        "",
        "| Clip | Role | Sampled | Positive | Longest run | Max lane px | Median lane px | Infer sum s | Infer mean s |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['clip']} | {row['role']} | {row['sampled_frames']} | {row['positive_frames']} | "
            f"{row['longest_consecutive_positive']} | {row['max_lane_pixels']} | {num(row['median_lane_pixels'])} | "
            f"{num(row['infer_s_sum'])} | {num(row['infer_s_mean'])} |"
        )
    lines += [
        "",
        "## Models",
        "",
        f"SAM runtime model id `{versions['model_id']}`, Hugging Face revision `{versions['hf_revision']}`, "
        f"torch `{versions['torch_version']}`, transformers `{versions['transformers_version']}`, "
        f"device `{versions['device']}`.",
        "",
        "Label client: existing `src/muse.rs` Baseten path, requested model "
        "`meta-models/muse-spark-open-1026`. "
        f"Recorded source `{label.get('source')}`, fallback_reason `{label.get('fallback_reason')}`, "
        f"provider `{label.get('provider')}`, model_id `{label.get('model_id')}`, "
        f"latency_ms `{label.get('latency_ms')}`.",
        "",
        "The stored reply label is what that source produced. On `fallback` / `no_key` the body is "
        "`Reply::mock()` from `src/record.rs` (`fallen tree`). That text is not a classification of these frames. "
        "The edit's `blocks` value is the preregistered `road`, not the reply's `blocks`. "
        "Merge is `RoadEdit::review`. The reply does not set status and does not move a vehicle.",
        "",
        "A machine with `BASETEN_API_KEY` reruns only the label step, rewrites the edit metadata, "
        "reruns the merge check and refreshes this summary:",
        "",
        "```sh",
        "experiments/phase16b/run_live_label.sh",
        "```",
        "",
        "The script reads the key from the environment and does not print it.",
        "",
        "## Sources",
        "",
        f"[{manifest['original']['source_url']}]({manifest['original']['source_url']}). "
        "Author as listed: Dash. Licence as listed: Commons public-domain statement for an automated recording. "
        "That statement was not independently adjudicated.",
        "",
        "Per-frame lane pixels and infer times: `experiments/phase16b/output/frames-A.json`, "
        "`frames-B.json`, `frames-C.json`. Masks: `experiments/phase16b/masks/`. "
        "Overlays: `experiments/phase16b/overlays/`. "
        "Edit: `experiments/phase16b/output/edit.json`. "
        "Merge check: `experiments/phase16b/output/merge-check.json`.",
        "",
    ]
    text = "\n".join(lines)
    GATE.write_text(text)
    status = {
        "phase": "16b",
        "prior_stop": PRIOR_STOP,
        "sam_model_id": versions["model_id"],
        "hf_revision": versions["hf_revision"],
        "torch_version": versions["torch_version"],
        "transformers_version": versions["transformers_version"],
        "llm_requested": "meta-models/muse-spark-open-1026",
        "llm_source": label.get("source"),
        "llm_fallback_reason": label.get("fallback_reason"),
        "llm_provider": label.get("provider"),
        "llm_model_id": label.get("model_id"),
        "llm_latency_ms": label.get("latency_ms"),
        "clips": rows,
        "merge": merge,
        "bars": [{"bar": bar, "result": word(ok), "detail": detail} for bar, _, ok, detail in bars],
    }
    STATUS.write_text(json.dumps(status, indent=2) + "\n")
    print(text)


if __name__ == "__main__":
    main()
