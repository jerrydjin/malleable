"""Commit-before-freeze checks and one-shot held-out attempt receipts.

Development helpers never enumerate or read the held-out directory. Held-out
inputs are opened only by prepare_heldout(), after a committed freeze passes
verification. This module supplies no held-out scoring rule.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess


EXPERIMENT = Path("experiments/phase16d")
DETERMINISM_TEST = "test_tracker.ActualTrackingDeterminism.test_fixed_development_clip_first_three_sampled_frames_repeat"
_EXCLUDED_DIRS = {"heldout", "overlays", "runs", "evidence", "cache", ".cache", "__pycache__"}
_SUFFIXES = {".py", ".rs", ".json", ".sh", ".toml", ".txt", ".yaml", ".yml", ".md"}
_REQUIRED = {
    "tracker.py", "motion.py", "mapping.py", "outputs.py", "evaluate.py",
    "run_mapping.py", "protocol.py", "record_adapter.rs", "config.json",
    "dev-targets.json", "runtime/requirements.lock.txt", "runtime/sam2-source.json",
    "base-preservation.json", "tests/test_protocol.py",
}


class ProtocolError(RuntimeError):
    """An explicit freeze or one-shot prerequisite is not satisfied."""


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _local(root, relative):
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ProtocolError("Artifact path must be relative to the repository")
    path = root / relative
    if not path.resolve().is_relative_to(root) or path.is_symlink():
        raise ProtocolError(f"Artifact path is not a normal repository file: {relative}")
    return path


def _git(root, *arguments, check=True):
    process = subprocess.run(["git", *arguments], cwd=root, check=False,
                             capture_output=True)
    if check and process.returncode:
        raise ProtocolError("Git prerequisite failed: " + " ".join(arguments[:2]))
    return process


def _read(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise ProtocolError(f"Missing or invalid JSON artifact: {path}") from error


def _at_head(root, path):
    relative = str(path.relative_to(root))
    recorded = _git(root, "show", f"HEAD:{relative}", check=False)
    if recorded.returncode or not path.is_file() or recorded.stdout != path.read_bytes():
        raise ProtocolError(f"Commit this artifact before proceeding: {relative}")


def verify_base_preservation(root):
    """Verify every retained parent file, including prior STOP evidence."""
    root = Path(root).resolve()
    record = _read(root / EXPERIMENT / "base-preservation.json")
    entries = record.get("files", [])
    if not entries or len({entry["path"] for entry in entries}) != len(entries):
        raise ProtocolError("Base preservation manifest is empty or contains duplicate paths")
    inherited = set(_git(root, "ls-tree", "-r", "--name-only", record["base_commit"]).stdout.decode().splitlines())
    if {entry["path"] for entry in entries} != inherited:
        raise ProtocolError("Base preservation manifest does not cover every retained parent file")
    for entry in entries:
        path = _local(root, entry["path"])
        if not path.is_file() or sha256(path) != entry["sha256"]:
            raise ProtocolError(f"Retained parent evidence changed: {entry['path']}")
    return {"base_commit": record["base_commit"], "checked_files": len(entries),
            "changed_files": 0, "manifest_sha256": sha256(root / EXPERIMENT / "base-preservation.json")}


def frozen_paths(root):
    """All executable/configuration inputs, without opening held-out paths."""
    root = Path(root).resolve()
    directory = root / EXPERIMENT
    result = []
    # os.walk prunes excluded directories before traversal; a recursive glob
    # would enumerate held-out names before filtering them.
    for parent, directories, names in os.walk(directory, followlinks=False):
        for name in directories:
            if name not in _EXCLUDED_DIRS and (Path(parent) / name).is_symlink():
                raise ProtocolError(f"Frozen input directory may not be a symbolic link: {name}")
        directories[:] = sorted(name for name in directories if name not in _EXCLUDED_DIRS)
        for name in sorted(names):
            path = Path(parent) / name
            relative = path.relative_to(directory)
            if (path.suffix in _SUFFIXES and name not in {"FROZEN.md", "freeze.json", "latest-development.json"}
                    and relative not in {Path("tracks.csv.json"), Path("edits.jsonl.json"),
                                         Path("runtime/validation.json"),
                                         Path("runtime/checkpoint-access.json"),
                                         Path("runtime/checkpoint-acquisition.json")}):
                if path.is_symlink():
                    raise ProtocolError(f"Frozen input may not be a symbolic link: {relative}")
                result.append(path)
    for relative in ("examples/phase16d_record.rs", "tests/phase16d.rs"):
        path = root / relative
        if path.is_file():
            result.append(path)
    return sorted(result, key=lambda path: str(path.relative_to(root)))


def code_manifest(root):
    root = Path(root).resolve()
    files = [{"path": str(path.relative_to(root)), "sha256": sha256(path)}
             for path in frozen_paths(root)]
    return {"files": files, "sha256": _digest(files)}


def _validation(root, validation_path, current):
    validation = _read(validation_path)
    if validation.get("code_manifest_sha256") != current["sha256"]:
        raise ProtocolError("Validation does not cover the current code/config manifest")
    if validation.get("python", {}).get("status") != "PASS" or validation.get("python", {}).get("failed") != 0:
        raise ProtocolError("The complete Python suite must pass before freezing")
    for key in ("cargo", "sam_determinism"):
        item = validation.get(key, {})
        if item.get("status") != "PASS" or item.get("failed", 0) != 0:
            raise ProtocolError(f"Required validation is not passing: {key}")
        relative = Path(item.get("log", ""))
        log = _local(root, relative if relative.parts[:2] == ("experiments", "phase16d")
                     else EXPERIMENT / relative)
        if not log.is_file() or (item.get("log_sha256") is not None
                                and sha256(log) != item["log_sha256"]):
            raise ProtocolError(f"Validation log is unavailable or changed: {key}")
        _at_head(root, log)
    repeat = validation["sam_determinism"]
    if repeat.get("skipped") != 0 or repeat.get("test") != DETERMINISM_TEST:
        raise ProtocolError("Actual fixed-clip SAM repeat must pass without being skipped")
    if validation.get("python", {}).get("outcomes", {}).get(DETERMINISM_TEST, {}).get("status") != "PASS":
        raise ProtocolError("Python outcomes do not record the actual SAM repeat passing")
    return validation


def freeze(root, run_dir, validation_path):
    """Create freeze artifacts after code and successful evidence are committed."""
    root = Path(root).resolve()
    directory = root / EXPERIMENT
    run_dir = (root / Path(run_dir)).resolve()
    validation_path = (root / Path(validation_path)).resolve()
    if not run_dir.is_relative_to(directory / "runs") or not validation_path.is_relative_to(root):
        raise ProtocolError("Freeze evidence must be inside this experiment/repository")
    if (directory / "FROZEN.md").exists() or (directory / "freeze.json").exists():
        raise ProtocolError("A freeze already exists; refusing to replace it")
    verify_base_preservation(root)
    for relative in sorted(_REQUIRED):
        if not (directory / relative).is_file():
            raise ProtocolError(f"Required freeze input is missing: {relative}")
    current = code_manifest(root)
    for entry in current["files"]:
        _at_head(root, _local(root, entry["path"]))
    # An altered retained file outside the manifest must not sneak into a freeze.
    if _git(root, "diff", "HEAD", "--name-only").stdout.strip():
        raise ProtocolError("Commit tracked changes before freezing")
    run_path = run_dir / "run.json"
    run = _read(run_path)
    if (run.get("state") != "complete" or run.get("phase") != "development"
            or run.get("selected_clips") != ["A", "B", "C"]
            or run.get("code_manifest") != current
            or run.get("completed_tracking_clips") != 3
            or run.get("labels_deferred") is not False
            or run.get("heldout_opened") is not False):
        raise ProtocolError("Freeze requires a complete unchanged A/B/C run with live label attempts")
    checkpoint_sha = run.get("checkpoint_sha256", "")
    if not isinstance(checkpoint_sha, str) or len(checkpoint_sha) != 64:
        raise ProtocolError("Development checkpoint provenance is missing")
    results_path, records_path = run_dir / "dev-results.json", run_dir / "records.json"
    results, records = _read(results_path), _read(records_path)
    config, plan = _read(directory / "config.json"), _read(directory / "dev-targets.json")
    required = config.get("emission", {}).get("consecutive_frames")
    if (type(required) is not int or required <= 0 or plan.get("required_consecutive_frames") != required
            or results.get("required_consecutive_frames") != required
            or results.get("evaluation_plan_sha256") != _digest(plan)):
        raise ProtocolError("Development evaluation must use the current plan and configured N")
    rows = results.get("rows", [])
    target_ids = {"A_red_stationary", "A_white_moving", "B_red_stationary", "B_white_moving", "C_clear_road"}
    if (results.get("all_pass") is not True or len(rows) != 5
            or {row.get("id") for row in rows} != target_ids
            or any(row.get("pass") is not True for row in rows)
            or results.get("input_errors") != []
            or results.get("safety_checks", {}).get("pass") is not True
            or set(results.get("clip_checks", {})) != {"A", "B", "C"}
            or any(item.get("pass") is not True for item in results["clip_checks"].values())):
        raise ProtocolError("Every one of the five actual development target rows must pass")
    if (records.get("labels_deferred") is not False or results.get("labels_deferred") is not False
            or records.get("merge_reviews_applied") != 0
            or records.get("vehicle_motion_actions") != 0):
        raise ProtocolError("Records must use final labels and perform no merge or motion actions")
    evidence = [run_path, results_path, records_path, validation_path]
    for clip in ("A", "B", "C"):
        tracking_path = run_dir / clip / "tracking.json"
        tracking = _read(tracking_path)
        if (tracking.get("state") != "complete"
                or tracking.get("identity", {}).get("checkpoint_sha256") != checkpoint_sha
                or tracking.get("decoded", {}).get("sampled_frames", 0) <= 0
                or tracking.get("calls", {}).get("automatic_mask_generation", 0) <= 0):
            raise ProtocolError(f"Actual SAM development evidence is incomplete: {clip}")
        if clip != "C" and (tracking.get("track_count", 0) <= 0
                            or tracking.get("calls", {}).get("propagated_frame_outputs", 0) <= 0):
            raise ProtocolError(f"Development target requires genuinely propagated tracks: {clip}")
        evidence.append(tracking_path)
    for entry in run.get("artifact_manifest", []):
        path = _local(run_dir, entry["path"])
        if not path.is_file() or sha256(path) != entry["sha256"]:
            raise ProtocolError("Development run artifact changed after completion")
        evidence.append(path)
    validation = _validation(root, validation_path, current)
    for key in ("cargo", "sam_determinism"):
        relative = Path(validation[key]["log"])
        evidence.append(_local(root, relative if relative.parts[:2] == ("experiments", "phase16d")
                               else EXPERIMENT / relative))
    for path in set(evidence):
        _at_head(root, path)
    commit = _git(root, "rev-parse", "HEAD").stdout.decode().strip()
    manifest = {"version": 1, "code_commit": commit,
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "code_manifest": current, "checkpoint_sha256": checkpoint_sha,
                "development_run": str(run_dir.relative_to(root)),
                "evidence": [{"path": str(path.relative_to(root)), "sha256": sha256(path)}
                             for path in sorted(set(evidence))],
                "heldout_inference_attempts_at_freeze": 0}
    encoded = json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with (directory / "freeze.json").open("x") as stream:
        stream.write(encoded)
    try:
        with (directory / "FROZEN.md").open("x") as stream:
            stream.write(f"# Phase 16d freeze\n\nCode/config commit: `{commit}`.\n\n"
                         f"Code manifest SHA-256: `{current['sha256']}`.\n\n"
                         f"Development run: `{manifest['development_run']}`. All five development "
                         "targets passed; actual SAM repeat and Cargo validation passed. "
                         "See `freeze.json` for committed evidence hashes.\n\n"
                         "Commit this freeze before opening the held-out clip. The code/config "
                         "must remain unchanged for its single attempt. No held-out result "
                         "is asserted by this file.\n")
    except BaseException:
        (directory / "freeze.json").unlink()
        raise
    return manifest


def verify_freeze(root, require_committed=True):
    root = Path(root).resolve()
    directory = root / EXPERIMENT
    manifest = _read(directory / "freeze.json")
    marker = directory / "FROZEN.md"
    if not marker.is_file() or manifest.get("code_commit", "") not in marker.read_text():
        raise ProtocolError("Freeze marker is missing or inconsistent")
    if manifest.get("code_manifest") != code_manifest(root):
        raise ProtocolError("Frozen code/config changed; held-out processing is forbidden")
    verify_base_preservation(root)
    if _git(root, "merge-base", "--is-ancestor", manifest["code_commit"], "HEAD", check=False).returncode:
        raise ProtocolError("Frozen code commit is not an ancestor of this checkout")
    for entry in manifest.get("evidence", []):
        path = _local(root, entry["path"])
        if not path.is_file() or sha256(path) != entry["sha256"]:
            raise ProtocolError(f"Frozen evidence changed: {entry['path']}")
    if require_committed:
        _at_head(root, marker)
        _at_head(root, directory / "freeze.json")
    return manifest


def prepare_heldout(root):
    """Read supplied preregistration only after a committed, unchanged freeze.

    Missing inputs are returned without inventing a scored failure. The caller
    must use an already-frozen scorer or assess outputs manually against the
    supplied preregistration. Code changes after freeze are forbidden; no
    generic success criteria are inferred here.
    """
    root = Path(root).resolve()
    manifest = verify_freeze(root)
    directory = root / EXPERIMENT / "heldout"
    if not directory.is_dir():
        return {"state": "MISSING", "reason": "Michael has not supplied the held-out directory"}
    if directory.is_symlink() or not directory.resolve().is_relative_to(root):
        raise ProtocolError("The held-out directory must be a normal local directory")
    prereg = directory / "prereg.md"
    videos = sorted(path for path in directory.iterdir()
                    if path.suffix.lower() in {".mp4", ".mov", ".mkv", ".avi", ".webm"})
    if not prereg.is_file() or len(videos) != 1:
        raise ProtocolError("Held-out input requires prereg.md and exactly one supported video")
    clip = videos[0]
    if prereg.is_symlink() or clip.is_symlink() or not clip.is_file():
        raise ProtocolError("Held-out inputs must be normal local files")
    return {"state": "READY_FOR_PREREG_REVIEW", "code_commit": manifest["code_commit"],
            "clip_path": str(clip.relative_to(root)), "clip_sha256": sha256(clip),
            "prereg_path": str(prereg.relative_to(root)), "prereg_sha256": sha256(prereg),
            "prereg_text": prereg.read_text()}


def reserve_heldout(root, inputs, checkpoint_path):
    """Persist an exclusive attempt receipt immediately before inference.

    An interrupted or failed reserved attempt cannot be silently retried. This
    function neither decodes the clip nor evaluates the preregistration.
    """
    root = Path(root).resolve()
    manifest = verify_freeze(root)
    if inputs.get("state") != "READY_FOR_PREREG_REVIEW" or inputs.get("code_commit") != manifest["code_commit"]:
        raise ProtocolError("Held-out inputs have not passed the frozen preflight")
    for name in ("clip", "prereg"):
        path = _local(root, inputs[f"{name}_path"])
        if not path.is_relative_to(root / EXPERIMENT / "heldout") or sha256(path) != inputs[f"{name}_sha256"]:
            raise ProtocolError("Held-out inputs changed after preregistration review")
    checkpoint = Path(checkpoint_path).expanduser().resolve()
    if not checkpoint.is_file() or sha256(checkpoint) != manifest["checkpoint_sha256"]:
        raise ProtocolError("Held-out checkpoint must match the frozen development checkpoint")
    receipt = {key: value for key, value in inputs.items() if key != "prereg_text"}
    receipt.update({"state": "ATTEMPT_RESERVED", "attempt": 1,
                    "reserved_at_utc": datetime.now(timezone.utc).isoformat(),
                    "checkpoint_sha256": manifest["checkpoint_sha256"],
                    "code_manifest_sha256": manifest["code_manifest"]["sha256"]})
    path = root / EXPERIMENT / "heldout" / "ATTEMPTED.json"
    try:
        with path.open("x") as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as error:
        raise ProtocolError("The held-out attempt is already reserved; rerunning is forbidden") from error
    return receipt
