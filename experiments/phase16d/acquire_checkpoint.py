#!/usr/bin/env python3
"""Acquire official native SAM 2.1 weights through the inherited TLS proxy."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.error
import urllib.request

EXPERIMENT = Path(__file__).resolve().parent
URL = "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt"


class OfficialRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if newurl != URL:
            raise RuntimeError("Unexpected checkpoint redirect; no alternate destination was requested")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def acquire(config, record_path):
    if config["sam"]["official_checkpoint_url"] != URL:
        raise ValueError("Acquisition requires the pinned official tiny checkpoint URL")
    destination = Path(config["sam"]["checkpoint"]).expanduser()
    record = {"requested_url": URL, "model_id": config["sam"]["model_id"],
              "checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "checkpoint_path": str(destination), "state": "started",
              "bytes_downloaded": 0, "tls_verification": True, "proxy": "inherited"}
    temporary = None
    try:
        if destination.exists():
            raise FileExistsError("Refusing to overwrite an existing checkpoint")
        destination.parent.mkdir(parents=True, exist_ok=True)
        opener = urllib.request.build_opener(OfficialRedirects())
        with opener.open(URL, timeout=60) as response:
            record["http_status"] = response.status
            record["final_url"] = response.geturl()
            record["declared_content_length"] = response.headers.get("Content-Length")
            if response.status != 200 or response.geturl() != URL:
                raise RuntimeError("Checkpoint response was not a direct HTTP 200 from the pinned URL")
            digest = hashlib.sha256()
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".sam2.1-", suffix=".part", delete=False) as stream:
                temporary = Path(stream.name)
                for chunk in iter(lambda: response.read(1 << 20), b""):
                    digest.update(chunk)
                    record["bytes_downloaded"] += len(chunk)
                    stream.write(chunk)
        if record["declared_content_length"] is not None:
            if record["bytes_downloaded"] != int(record["declared_content_length"]):
                raise RuntimeError("Downloaded bytes differ from HTTP Content-Length")
        import torch
        state = torch.load(temporary, map_location="cpu", weights_only=True)
        model = state.get("model") if isinstance(state, dict) else None
        if not isinstance(model, dict) or not model or not all(isinstance(v, torch.Tensor) for v in model.values()):
            raise RuntimeError("Downloaded file is not an official native SAM model state dictionary")
        if not any(key.startswith("image_encoder.") for key in model):
            raise RuntimeError("Native checkpoint lacks the SAM image encoder")
        record.update({"sha256": digest.hexdigest(), "native_tensor_count": len(model),
                       "native_parameter_elements": sum(v.numel() for v in model.values()),
                       "validation": "torch.load(weights_only=True), native model tensor dictionary; strict architecture load occurs in tracker"})
        # Same-filesystem link is atomic and exclusive: no partially written
        # checkpoint is ever visible, and concurrent acquisition cannot overwrite.
        os.link(temporary, destination)
        record["state"] = "verified"
    except Exception as error:
        record.update({"state": "blocked" if isinstance(error, urllib.error.HTTPError) and error.code == 403 else "failed",
                       "failure_type": type(error).__name__, "reason": str(error)})
        if isinstance(error, urllib.error.HTTPError):
            record["http_status"] = error.code
        raise
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        Path(record_path).parent.mkdir(parents=True, exist_ok=True)
        Path(record_path).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, default=EXPERIMENT / "runtime" / "checkpoint-acquisition.json")
    arguments = parser.parse_args()
    result = acquire(json.loads((EXPERIMENT / "config.json").read_text()), arguments.record)
    print(json.dumps({key: result[key] for key in ("state", "bytes_downloaded", "sha256")}))
