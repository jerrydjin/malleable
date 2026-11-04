#!/usr/bin/env python3
"""Launch the existing experiment commands with durable logs and a job receipt."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys

EXPERIMENT = Path(__file__).resolve().parent
ROOT = EXPERIMENT.parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("command", choices=("dev", "heldout", "validate"))
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", args.job_id):
        parser.error("job-id must contain only letters, digits, underscores and hyphens")
    jobs = EXPERIMENT / "runs" / "_jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    receipt = jobs / f"{args.job_id}.json"
    log_path = EXPERIMENT / "runtime" / f"{args.job_id}-console.log"
    if args.command == "validate":
        command = [sys.executable, str(EXPERIMENT / "validate.py"), *args.arguments]
    else:
        command = [sys.executable, str(EXPERIMENT / "run_mapping.py"), args.command, *args.arguments]
    record = {"job_id": args.job_id, "state": "launch_reserved", "command": command,
              "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "log_path": str(log_path.relative_to(ROOT)),
              "note": "Final status is recorded by the existing runner or validation command."}
    # Reserve the job name before starting any child. Reopening a chat cannot
    # silently launch the same job a second time. Held-out also has its own
    # exclusive attempt receipt in the original runner.
    with receipt.open("x") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    child_env = os.environ.copy()
    rust = "/workspace/.toolchains/rust"
    child_env["PATH"] = f"{rust}/rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin:" + child_env.get("PATH", "")
    child_env["CARGO_HOME"] = f"{rust}/cargo"
    child_env["CARGO_TARGET_DIR"] = "/workspace/.cache/phase16d-cargo"
    child_env["PYTHONUNBUFFERED"] = "1"
    try:
        with log_path.open("xb") as log:
            child = subprocess.Popen(command, cwd=ROOT, env=child_env,
                                     stdin=subprocess.DEVNULL, stdout=log,
                                     stderr=subprocess.STDOUT, close_fds=True,
                                     start_new_session=True)
        record.update({"state": "launched", "pid": child.pid})
    except Exception as error:
        record.update({"state": "launch_failed", "failure_type": type(error).__name__,
                       "reason": str(error)})
        raise
    finally:
        receipt.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: record[key] for key in ("job_id", "state", "pid", "log_path")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
