#!/usr/bin/env python3
"""Acquire the one authorized bbox, tiled only for OSM's node-count limit."""
import concurrent.futures
import copy
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "experiments/phase16/map-change"
BOX = (-122.425, 37.738, -122.385, 37.762)
LONGITUDES = (-122.425, -122.420, -122.415, -122.410, -122.405,
              -122.400, -122.395, -122.390, -122.385)
LATITUDES = (37.738, 37.750, 37.762)
TILES = [(LONGITUDES[i], LATITUDES[j], LONGITUDES[i+1], LATITUDES[j+1])
         for i in range(8) for j in range(2)]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def compress(path, data):
    with gzip.GzipFile(filename=str(path), mode="wb", mtime=0) as destination:
        destination.write(data)


def fetch(pair):
    index, box = pair
    url = "https://api.openstreetmap.org/api/0.6/map?bbox=" + ",".join(map(str, box))
    start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    request = urllib.request.Request(url, headers={
        "User-Agent": "Malleable-Phase16/1.0 (https://github.com/jerrydjin/malleable)"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
        record = {"request_url": url, "bbox_west_south_east_north": box,
                  "http_status": response.status, "started_at_utc": start,
                  "completed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  "response_headers": {key: response.headers.get(key) for key in ("date", "etag", "content-type")},
                  "raw_bytes": len(data), "raw_sha256": sha(data)}
    tree = ET.fromstring(data)
    path = OUT / f"source-tiles/grid-{index}.osm.gz"
    compress(path, data)
    record.update({"compressed_path": str(path.relative_to(ROOT)), "compressed_sha256": sha(path.read_bytes()),
                   "nodes": len(tree.findall("node")), "ways": len(tree.findall("way")),
                   "relations": len(tree.findall("relation"))})
    print(json.dumps(record), flush=True)
    return record, tree


def main():
    plan = json.loads((OUT / "plan.json").read_text())
    assert tuple(plan["new_bbox_west_south_east_north"]) == BOX
    assert plan["allowed_bbox_expansions"] == 1 and not plan["further_expansion_allowed"]
    destination = OUT / "us101-expanded.osm.gz"
    assert not destination.exists(), "refusing to overwrite the acquired snapshot"
    OUT.joinpath("source-tiles").mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        acquired = list(pool.map(fetch, enumerate(TILES)))
    entities = {}
    duplicate_version_conflicts = []
    for record, tree in acquired:
        for item in tree:
            if item.tag not in ("node", "way", "relation"):
                continue
            key = (item.tag, int(item.get("id")))
            if key in entities and entities[key].get("version") != item.get("version"):
                duplicate_version_conflicts.append({"type": key[0], "id": key[1]})
            if key not in entities or int(item.get("version", "0")) > int(entities[key].get("version", "0")):
                entities[key] = item
    assert not duplicate_version_conflicts, "source changed during tiled acquisition; retain the tiles and stop"
    original_path = ROOT / "maps/us101.osm"
    original = ET.parse(original_path).getroot()
    overlaps = {kind: 0 for kind in ("node", "way", "relation")}
    changed_versions = []
    for item in original:
        if item.tag not in overlaps:
            continue
        key = (item.tag, int(item.get("id")))
        if key in entities:
            overlaps[item.tag] += 1
            if item.get("version") != entities[key].get("version"):
                changed_versions.append({"type": key[0], "id": key[1], "retained_version": item.get("version"),
                                         "fetched_version": entities[key].get("version")})
        # Preserve the complete frozen snapshot's entities, including all node
        # references; new geographic coverage supplies only additional entities.
        entities[key] = item
    result = ET.Element("osm", {**original.attrib, "generator": "phase16 retained-core plus authorized EW tiles"})
    ET.SubElement(result, "bounds", dict(zip(("minlon", "minlat", "maxlon", "maxlat"), map(str, BOX))))
    for kind in ("node", "way", "relation"):
        result.extend(copy.deepcopy(entities[key]) for key in sorted(entities) if key[0] == kind)
    data = ET.tostring(result, encoding="utf-8", xml_declaration=True)
    compress(destination, data)
    acquisition = {
        "bbox_west_south_east_north": BOX, "tiles": [a[0] for a in acquired],
        "full_area_request": {"url": "https://api.openstreetmap.org/api/0.6/map?bbox=-122.425,37.738,-122.385,37.762",
                              "http_status": 400, "body": "You requested too many nodes (limit is 50000). Either request a smaller area, or use planet.osm"},
        "retained_source_path": "maps/us101.osm", "retained_source_sha256": sha(original_path.read_bytes()),
        "merge_policy": "Frozen original entities take precedence by type/id; new tiles add coverage. Exact geometric clipping to the one authorized bbox occurs before netconvert.",
        "overlap_entities_retained": overlaps, "overlap_version_differences": changed_versions,
        "tile_duplicate_version_conflicts": duplicate_version_conflicts,
        "merged_path": str(destination.relative_to(ROOT)), "merged_raw_bytes": len(data),
        "merged_raw_sha256": sha(data), "merged_compressed_sha256": sha(destination.read_bytes()),
        "osm_nodes": len(result.findall("node")), "osm_ways": len(result.findall("way")),
        "osm_relations": len(result.findall("relation")), "traffic_runs": 0}
    (OUT / "acquisition.json").write_text(json.dumps(acquisition, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in acquisition.items() if k != "tiles"}), flush=True)


if __name__ == "__main__":
    main()
