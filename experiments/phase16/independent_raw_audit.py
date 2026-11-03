#!/usr/bin/env python3
"""Audit the authorized expanded raw OSM without importing SUMO or running traffic."""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def audit(source):
    source = source.resolve()
    compressed = source.read_bytes()
    data = gzip.decompress(compressed)
    root = ET.fromstring(data)
    box = (-122.425, 37.738, -122.385, 37.762)
    nodes = {
        int(node.get("id")): (float(node.get("lon")), float(node.get("lat")))
        for node in root.findall("node")
    }
    ways = {
        int(way.get("id")): {
            "nodes": [int(node.get("ref")) for node in way.findall("nd")],
            "tags": {tag.get("k"): tag.get("v") for tag in way.findall("tag")},
        }
        for way in root.findall("way")
    }

    def inside(node):
        lon, lat = nodes[node]
        return box[0] <= lon <= box[2] and box[1] <= lat <= box[3]

    post_ways = (1164076368, 28326944, 28326941)
    blocked_way = 1343758309
    source_node = 729040229
    post_nodes = sorted(
        {node for way in post_ways for node in ways[way]["nodes"] if inside(node)},
        key=lambda node: -nodes[node][1],
    )
    # Relaxed upper bound: every highway class and access value is allowed;
    # turns, lane transitions and implicit one-way rules impose no restriction.
    # Explicit oneway=yes/1/true/-1 is respected. Interior-node adjacency
    # suffices: clipping creates dead-end boundary ports, which cannot reconnect
    # to another interior node through geometry outside the authorized box.
    adjacency = collections.defaultdict(set)
    incoming = collections.defaultdict(list)
    outgoing = collections.defaultdict(list)
    for ident, way in ways.items():
        tags = way["tags"]
        if not tags.get("highway"):
            continue
        forward = tags.get("oneway") != "-1"
        reverse = tags.get("oneway") not in ("yes", "1", "true")
        for left, right in zip(way["nodes"], way["nodes"][1:]):
            if not (inside(left) and inside(right)):
                continue
            for start, end, allowed in ((left, right, forward), (right, left, reverse)):
                if not allowed:
                    continue
                incoming[end].append((ident, start))
                outgoing[start].append((ident, end))
                if ident != blocked_way:
                    adjacency[start].add(end)

    reached = {source_node}
    queue = collections.deque([source_node])
    while queue:
        for node in adjacency[queue.popleft()]:
            if node not in reached:
                reached.add(node)
                queue.append(node)
    mainline = set(post_ways) | {blocked_way}

    def describe(ident, neighbor):
        tags = ways[ident]["tags"]
        return {
            "way": ident,
            "neighbor_node": neighbor,
            "neighbor_lon_lat": nodes[neighbor],
            "highway": tags.get("highway"),
            "oneway": tags.get("oneway"),
            "ref": tags.get("ref"),
            "destination": tags.get("destination"),
            "destination_ref": tags.get("destination:ref"),
        }

    inventory = [
        {
            "node": node,
            "lon_lat": nodes[node],
            "reachable_avoiding_tree": node in reached,
            "incoming_non_mainline": [
                describe(ident, neighbor)
                for ident, neighbor in incoming[node] if ident not in mainline
            ],
            "outgoing_non_mainline": [
                describe(ident, neighbor)
                for ident, neighbor in outgoing[node] if ident not in mainline
            ],
        }
        for node in post_nodes
    ]
    return {
        "source": str(source),
        "source_compressed_sha256": hashlib.sha256(compressed).hexdigest(),
        "source_raw_sha256": hashlib.sha256(data).hexdigest(),
        "bbox_west_south_east_north": box,
        "blocked_source_way": blocked_way,
        "last_exit_source_node": source_node,
        "last_exit_lon_lat": nodes[source_node],
        "method": "Independent raw OSM node adjacency restricted to exact authorized bbox; all highway classes, private/access-restricted ways, and all turn/lane transitions permitted as a conservative upper bound; explicit oneway tags respected. Boundary cuts cannot connect routes through outside geometry.",
        "source_nodes": len(nodes),
        "source_ways": len(ways),
        "reached_nodes_avoiding_tree": len(reached),
        "post_tree_source_ways": post_ways,
        "post_tree_node_inventory": inventory,
        "any_post_tree_node_reachable": any(node in reached for node in post_nodes),
        "incoming_non_mainline_way_ids": sorted({
            entry["way"] for item in inventory for entry in item["incoming_non_mainline"]
        }),
        "traffic_runs": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(audit(args.source), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(result)
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
