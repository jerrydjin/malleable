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
import urllib.parse
import urllib.request

EXPERIMENT = Path(__file__).resolve().parent
URL = "https://huggingface.co/facebook/sam2.1-hiera-large/resolve/main/sam2.1_hiera_large.pt"
FALLBACK_URL = "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt"


def official_destination(url):
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").lower()
    return (parsed.scheme == "https" and not parsed.username and not parsed.password
            and parsed.port in (None, 443)
            and (host in {"huggingface.co", "dl.fbaipublicfiles.com"}
                 or host.endswith(".hf.co")))


def public_destination(url):
    # HF redirect queries contain temporary credentials; never persist them.
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


class OfficialRedirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, redirects):
        super().__init__()
        self.redirects = redirects

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if not official_destination(newurl):
            raise RuntimeError("Unexpected checkpoint redirect host: "
                               + str(urllib.parse.urlsplit(newurl).hostname))
        self.redirects.append({"http_status": code, "destination": public_destination(newurl)})
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def acquire(config, record_path):
    if config["sam"]["official_checkpoint_url"] != URL:
        raise ValueError("Acquisition requires the pinned official Hiera Large checkpoint URL")
    destination = Path(config["sam"]["checkpoint"]).expanduser()
    if not destination.is_absolute():
        destination = EXPERIMENT.parents[1] / destination
    record = {"requested_url": URL, "model_id": config["sam"]["model_id"],
              "checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "checkpoint_path": str(destination), "state": "started",
              "bytes_downloaded": 0, "tls_verification": True, "proxy": "inherited",
              "attempts": []}
    temporary = None
    try:
        if destination.exists():
            raise FileExistsError("Refusing to overwrite an existing checkpoint")
        destination.parent.mkdir(parents=True, exist_ok=True)
        for url in (URL, FALLBACK_URL):
            attempt = {"requested_url": url, "redirects": []}
            record["attempts"].append(attempt)
            opener = urllib.request.build_opener(OfficialRedirects(attempt["redirects"]))
            try:
                response = opener.open(url, timeout=60)
                break
            except urllib.error.HTTPError as error:
                attempt.update({"http_status": error.code,
                                "failed_host": urllib.parse.urlsplit(error.url).hostname})
                if url == FALLBACK_URL:
                    raise RuntimeError("Checkpoint download failed: " + "; ".join(
                        f"{item['failed_host']} HTTP {item['http_status']}" for item in record["attempts"])) from None
        with response:
            record["http_status"] = response.status
            record["final_url"] = public_destination(response.geturl())
            record["declared_content_length"] = response.headers.get("Content-Length")
            attempt.update({"http_status": response.status, "final_url": record["final_url"]})
            if response.status != 200 or not official_destination(response.geturl()):
                raise RuntimeError("Checkpoint response was not an official HTTPS HTTP 200")
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
