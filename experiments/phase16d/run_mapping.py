#!/usr/bin/env python3
"""Run development mapping on A/B/C, with auditable attempts and real SAM only.

The development targets are evaluation inputs, never prompts or motion inputs.
No held-out path is read by the development command. A failed preflight is a
runtime failure, not a zero-detection score.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import cv2

from mapping import analyze
from tracker import CheckpointUnavailable, load_tracking, track_clip

EXPERIMENT = Path(__file__).resolve().parent
ROOT = EXPERIMENT.parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for part in iter(lambda: stream.read(1 << 20), b""):
            digest.update(part)
    return digest.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def code_manifest():
    # Shared with the freeze protocol; imports here avoid any held-out access.
    from protocol import code_manifest as frozen_code_manifest
    return frozen_code_manifest(ROOT)


def preservation():
    from protocol import verify_base_preservation
    return verify_base_preservation(ROOT)


def _git(*arguments):
    result = subprocess.run(["git", *arguments], cwd=ROOT, check=True,
                            capture_output=True, text=True)
    return result.stdout.strip()


def call_labels(candidates_path, output_path, log_path, defer_labels, cargo):
    command = [cargo, "run", "--offline", "--example", "phase16d_record", "--",
               f"--input={candidates_path}", f"--output={output_path}"]
    if defer_labels:
        command.append("--defer-labels")
    # Preserve injected credentials and transport settings; never inspect or log
    # their values. The child client uses the same existing Muse/Baseten adapter.
    with Path(log_path).open("w") as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"Road-record adapter failed with exit {result.returncode}; see {log_path}")
    record = json.loads(Path(output_path).read_text())
    if record["merge_reviews_applied"] != 0 or record["vehicle_motion_actions"] != 0:
        raise RuntimeError("Record adapter reported an unexpected merge or motion action")
    return record


def _artifact_manifest(directory):
    return [{"path": str(path.relative_to(directory)), "bytes": path.stat().st_size,
             "sha256": sha256(path)} for path in sorted(directory.rglob("*"))
            if path.is_file() and path.name != "run.json"]


def run_development(arguments):
    from evaluate import evaluate_development
    from outputs import render_overlay, write_edits_jsonl, write_tracks_csv

    if (EXPERIMENT / "FROZEN.md").exists():
        raise RuntimeError("Development is frozen; this command cannot tune or rerun it")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", arguments.run_id):
        raise ValueError("run-id must contain only letters, digits, underscores and hyphens")
    config = json.loads((EXPERIMENT / "config.json").read_text())
    before = code_manifest()
    preserved = preservation()
    run_dir = EXPERIMENT / "runs" / arguments.run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    record = {"version": 1, "phase": "development", "run_id": arguments.run_id,
              "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "git_commit": _git("rev-parse", "HEAD"), "state": "started",
              "selected_clips": arguments.clips, "code_manifest": before,
              "labels_deferred": bool(arguments.defer_labels), "base_preservation": preserved,
              "completed_tracking_clips": 0, "clips": {},
              "heldout_opened": False, "vehicle_motion_actions": 0, "merge_reviews_applied": 0}
    write_json(run_dir / "run.json", record)
    write_json(run_dir / "config.json", config)
    started = time.perf_counter()
    stage = "checkpoint_preflight"
    try:
        checkpoint = Path(config["sam"]["checkpoint"]).expanduser()
        if not checkpoint.is_file():
            raise CheckpointUnavailable(f"Native SAM 2.1 checkpoint is unavailable: {checkpoint}")
        record["checkpoint_sha256"] = sha256(checkpoint)
        # No tracking cache, decoding or model call occurs before preflight.
        cv2.setNumThreads(1)
        analyses, bundles, candidates = {}, {}, []
        for clip in arguments.clips:
            stage = f"tracking_{clip}"
            item = config["clips"][clip]
            cache_dir = arguments.cache_root.resolve() / clip
            metadata = track_clip(ROOT / item["path"], config, cache_dir,
                                  force=arguments.force_tracking)
            bundle = load_tracking(cache_dir)
            bundles[clip] = bundle
            write_json(run_dir / clip / "tracking.json", metadata)
            write_json(run_dir / clip / "track-identities.json", bundle["tracks"])
            stage = f"motion_and_emission_{clip}"
            analysis = analyze(bundle, config, clip, float(item["source_start_s"]),
                               run_dir / clip / "evidence")
            analyses[clip] = analysis
            write_json(run_dir / clip / "analysis.json", analysis)
            write_json(run_dir / clip / "candidates.json", analysis["candidates"])
            candidates.extend(analysis["candidates"])
            record["completed_tracking_clips"] += 1
            record["clips"][clip] = {"cache_directory": str(cache_dir),
                                     "input_sha256": metadata["identity"]["source_sha256"],
                                     "result_fingerprint": metadata["result_fingerprint"],
                                     "sampled_frames": len(bundle["frames"]),
                                     "track_count": metadata["track_count"],
                                     "eligible_candidates": len(analysis["candidates"])}
            write_json(run_dir / "run.json", record)
        stage = "label_and_reach"
        write_json(run_dir / "candidates.json", candidates)
        edits = call_labels(run_dir / "candidates.json", run_dir / "records.json",
                            run_dir / "label-adapter.log", arguments.defer_labels, arguments.cargo)
        stage = "exports"
        for clip in arguments.clips:
            render_overlay(bundles[clip], analyses[clip], run_dir / "overlays" / f"{clip}.mp4",
                           clip, config, edits=edits)
        write_tracks_csv(analyses, run_dir / "tracks.csv", edits=edits, bundles=bundles)
        write_edits_jsonl(edits, run_dir / "edits.jsonl")
        if set(arguments.clips) == {"A", "B", "C"}:
            stage = "development_evaluation"
            plan = json.loads((EXPERIMENT / "dev-targets.json").read_text())
            result = evaluate_development(analyses, bundles, edits, plan)
            write_json(run_dir / "dev-results.json", result)
            record["development_all_pass"] = bool(result["all_pass"])
        if before != code_manifest():
            raise RuntimeError("Code/config changed during the run; this attempt cannot be frozen")
        preservation()
        record.update({"state": "complete", "elapsed_s": time.perf_counter() - started,
                       "model_calls": edits["model_calls"], "edit_count": len(edits["edits"]),
                       "artifact_manifest": _artifact_manifest(run_dir)})
        write_json(run_dir / "run.json", record)
        # Publish only complete A/B/C snapshots. Partial and failed development
        # attempts retain their own evidence without replacing previous outputs.
        if set(arguments.clips) == {"A", "B", "C"}:
            destination = EXPERIMENT / "overlays"
            destination.mkdir(exist_ok=True)
            for path in sorted((run_dir / "overlays").iterdir()):
                shutil.copy2(path, destination / path.name)
            for name in ("tracks.csv", "tracks.csv.json", "edits.jsonl", "edits.jsonl.json"):
                shutil.copy2(run_dir / name, EXPERIMENT / name)
            write_json(EXPERIMENT / "latest-development.json",
                       {"run_dir": str(run_dir.relative_to(ROOT)), "run_sha256": sha256(run_dir / "run.json")})
        print(json.dumps({"state": record["state"], "run_dir": str(run_dir.relative_to(ROOT)),
                          "edit_count": record["edit_count"], "model_calls": record["model_calls"],
                          "development_all_pass": record.get("development_all_pass")}))
        return 0
    except Exception as error:
        record.update({"state": "blocked" if isinstance(error, CheckpointUnavailable) else "failed",
                       "failure_stage": stage, "failure_type": type(error).__name__,
                       "failure_reason": str(error), "elapsed_s": time.perf_counter() - started,
                       "development_all_pass": None,
                       "artifact_manifest": _artifact_manifest(run_dir)})
        write_json(run_dir / "run.json", record)
        print(json.dumps({"state": record["state"], "run_dir": str(run_dir.relative_to(ROOT)),
                          "failure_stage": stage, "reason": str(error)}), file=sys.stderr)
        return 2


def run_heldout(arguments):
    """Use the frozen algorithm once; the supplied prereg determines scoring.

    This command does not invent a generic PASS rule. Its numerical artifacts
    can be assessed against prereg.md without changing the frozen code.
    """
    from protocol import prepare_heldout, reserve_heldout, verify_freeze
    from outputs import render_overlay, write_edits_jsonl, write_tracks_csv

    frozen = verify_freeze(ROOT)
    inputs = prepare_heldout(ROOT)
    if inputs["state"] == "MISSING":
        print(json.dumps(inputs))
        return 3
    if inputs["prereg_sha256"] != arguments.prereg_sha256:
        raise RuntimeError("Read the frozen held-out preflight and use its exact prereg SHA-256")
    config = json.loads((EXPERIMENT / "config.json").read_text())
    checkpoint = Path(config["sam"]["checkpoint"]).expanduser()
    if not checkpoint.is_file():
        raise CheckpointUnavailable("Held-out checkpoint is missing; no attempt was reserved")
    cache_dir = arguments.cache_root.resolve() / "heldout"
    if cache_dir.exists():
        raise RuntimeError("Held-out tracking cache already exists; no reuse or replacement is permitted")
    run_dir = EXPERIMENT / "runs" / "heldout"
    if run_dir.exists():
        raise RuntimeError("Held-out run directory already exists; rerunning is forbidden")
    receipt = reserve_heldout(ROOT, inputs, checkpoint)
    run_dir.mkdir(parents=True, exist_ok=False)
    record = {"version": 1, "phase": "heldout", "state": "attempt_reserved",
              "attempt": 1, "freeze_code_commit": frozen["code_commit"],
              "code_manifest": frozen["code_manifest"], "receipt": receipt,
              "preregistered_score": "PENDING_PREREG_EVALUATION",
              "merge_reviews_applied": 0, "vehicle_motion_actions": 0}
    write_json(run_dir / "run.json", record)
    stage = "tracking"
    try:
        metadata = track_clip(ROOT / inputs["clip_path"], config, cache_dir)
        bundle = load_tracking(cache_dir)
        write_json(run_dir / "heldout" / "tracking.json", metadata)
        write_json(run_dir / "heldout" / "track-identities.json", bundle["tracks"])
        stage = "motion_and_emission"
        analysis = analyze(bundle, config, "heldout", 0., run_dir / "heldout" / "evidence")
        write_json(run_dir / "heldout" / "analysis.json", analysis)
        write_json(run_dir / "candidates.json", analysis["candidates"])
        stage = "label_and_reach"
        edits = call_labels(run_dir / "candidates.json", run_dir / "records.json",
                            run_dir / "label-adapter.log", False, arguments.cargo)
        stage = "exports"
        render_overlay(bundle, analysis, run_dir / "overlays" / "heldout.mp4",
                       "heldout", config, edits=edits)
        write_tracks_csv({"heldout": analysis}, run_dir / "tracks.csv", edits=edits,
                         bundles={"heldout": bundle})
        write_edits_jsonl(edits, run_dir / "edits.jsonl")
        verify_freeze(ROOT)
        record.update({"state": "complete", "sampled_frames": len(bundle["frames"]),
                       "track_count": metadata["track_count"], "edit_count": len(edits["edits"]),
                       "model_calls": edits["model_calls"],
                       "artifact_manifest": _artifact_manifest(run_dir)})
        write_json(run_dir / "run.json", record)
        destination = EXPERIMENT / "overlays"
        for path in (run_dir / "overlays").iterdir():
            shutil.copy2(path, destination / path.name)
        dev_dir = ROOT / frozen["development_run"]
        dev_edits = json.loads((dev_dir / "records.json").read_text())["edits"]
        all_edits = dev_edits + edits["edits"]
        all_analyses = {clip: json.loads((dev_dir / clip / "analysis.json").read_text())
                        for clip in ("A", "B", "C")}
        all_analyses["heldout"] = analysis
        all_bundles = {clip: {"metadata": json.loads((dev_dir / clip / "tracking.json").read_text()),
                              "tracks": json.loads((dev_dir / clip / "track-identities.json").read_text())}
                       for clip in ("A", "B", "C")}
        all_bundles["heldout"] = bundle
        write_tracks_csv(all_analyses, EXPERIMENT / "tracks.csv", edits=all_edits, bundles=all_bundles)
        write_edits_jsonl(all_edits, EXPERIMENT / "edits.jsonl")
        print(json.dumps({"state": "complete", "attempt": 1, "edit_count": len(edits["edits"]),
                          "preregistered_score": "PENDING_PREREG_EVALUATION"}))
        return 0
    except Exception as error:
        record.update({"state": "failed", "failure_stage": stage,
                       "failure_type": type(error).__name__, "failure_reason": str(error),
                       "artifact_manifest": _artifact_manifest(run_dir)})
        write_json(run_dir / "run.json", record)
        print(json.dumps({"state": "failed", "attempt": 1, "reason": str(error)}), file=sys.stderr)
        return 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    dev = commands.add_parser("dev", help="run actual A/B/C development mapping")
    dev.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("dev-%Y%m%dT%H%M%SZ"))
    dev.add_argument("--clips", nargs="+", choices=["A", "B", "C"], default=["A", "B", "C"])
    dev.add_argument("--cache-root", type=Path, default=Path("/workspace/.cache/phase16d/tracking"))
    dev.add_argument("--force-tracking", action="store_true", help="explicitly replace a mismatching owned dev cache")
    dev.add_argument("--defer-labels", action="store_true", help="explicit development fallback; cannot freeze")
    dev.add_argument("--cargo", default="cargo", help="Cargo executable; credentials stay in the environment")
    freeze_command = commands.add_parser("freeze", help="write freeze after passing dev evidence and code are committed")
    freeze_command.add_argument("--run-dir", type=Path, required=True)
    freeze_command.add_argument("--validation", type=Path, default=EXPERIMENT / "runtime" / "validation.json")
    commands.add_parser("heldout-preflight", help="read supplied preregistration only after a committed freeze")
    heldout = commands.add_parser("heldout", help="one frozen inference attempt after preregistration review")
    heldout.add_argument("--prereg-sha256", required=True)
    heldout.add_argument("--cache-root", type=Path, default=Path("/workspace/.cache/phase16d/tracking"))
    heldout.add_argument("--cargo", default="cargo")
    arguments = parser.parse_args()
    if arguments.command == "dev":
        if len(set(arguments.clips)) != len(arguments.clips):
            parser.error("clips must not contain duplicates")
        return run_development(arguments)
    if arguments.command == "heldout":
        return run_heldout(arguments)
    if arguments.command == "freeze":
        from protocol import freeze
        result = freeze(ROOT, arguments.run_dir, arguments.validation)
        print(json.dumps({"code_commit": result["code_commit"], "state": "freeze_written_commit_required"}))
        return 0
    from protocol import prepare_heldout
    print(json.dumps(prepare_heldout(ROOT), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
