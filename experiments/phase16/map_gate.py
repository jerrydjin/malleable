#!/usr/bin/env python3
"""Build the fixed OSM box in SUMO and audit topology, without running traffic."""
import argparse
import collections
import copy
import gzip
import hashlib
import heapq
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "experiments/phase16/rerun"
BOX = (-122.410, 37.738, -122.400, 37.762)
SOURCE = ROOT / "maps/us101.osm"
EXPANDED = False
STOP_COMMIT = "cafad04f4635a8d8113874555425d525768a8e0d"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def clip_osm():
    """Clip source segments geometrically; keep OSM attributes and valid restrictions.

    netconvert's keep-edges.in-geo-boundary selects whole intersecting ways.
    Clipping first prevents routes from leaving the explicitly fixed box.
    This uses the retained 15e line/rectangle clipping function unchanged.
    """
    spec = importlib.util.spec_from_file_location(
        "retained_boundary", ROOT / "experiments/phase15e/import_boundary.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with (gzip.open(SOURCE, "rb") if SOURCE.suffix == ".gz" else SOURCE.open("rb")) as stream:
        source = ET.parse(stream).getroot()
    nodes = {int(n.get("id")): n for n in source.findall("node")}
    points = {key: (float(n.get("lon")), float(n.get("lat"))) for key, n in nodes.items()}
    next_node = max(nodes) + 1
    next_way = max(int(w.get("id")) for w in source.findall("way")) + 1
    synthetic = {}
    new_nodes = {}
    ways = []
    source_ways = {}
    original_way_parts = {}

    def boundary_node(a, b, fraction, original):
        nonlocal next_node
        if original is not None:
            return original
        xy = (round(a[0] + fraction * (b[0] - a[0]), 11),
              round(a[1] + fraction * (b[1] - a[1]), 11))
        if xy not in synthetic:
            synthetic[xy] = next_node
            new_nodes[next_node] = ET.Element("node", {
                "id": str(next_node), "lon": str(xy[0]), "lat": str(xy[1]),
                "version": "1", "visible": "true"})
            next_node += 1
        return synthetic[xy]

    for way in source.findall("way"):
        tags = {t.get("k"): t.get("v") for t in way.findall("tag")}
        if tags.get("highway") not in module.DRIVABLE or tags.get("area") == "yes":
            continue
        if any(tags.get(k) in ("private", "no") for k in ("access", "vehicle", "motor_vehicle")):
            continue
        refs = [int(n.get("ref")) for n in way.findall("nd")]
        pieces, active = [], []
        for left, right in zip(refs, refs[1:]):
            a, b = points[left], points[right]
            interval = module.clip(a, b, BOX)
            if interval is None:
                if len(active) >= 2:
                    pieces.append(active)
                active = []
                continue
            lo, hi = interval
            start = boundary_node(a, b, lo, left if lo < 1e-12 else None)
            end = boundary_node(a, b, hi, right if hi > 1 - 1e-12 else None)
            if active and active[-1] != start:
                pieces.append(active)
                active = []
            if not active:
                active = [start]
            active.append(end)
            if hi < 1 - 1e-12:
                pieces.append(active)
                active = []
        if len(active) >= 2:
            pieces.append(active)
        for index, refs in enumerate(pieces):
            ident = int(way.get("id")) if index == 0 else next_way
            if index:
                next_way += 1
            item = ET.Element("way", {**way.attrib, "id": str(ident)})
            for ref in refs:
                ET.SubElement(item, "nd", {"ref": str(ref)})
            item.extend(copy.deepcopy(way.findall("tag")))
            ET.SubElement(item, "tag", {"k": "malleable:source_way", "v": way.get("id")})
            ways.append(item)
            source_ways[str(ident)] = {"source_way": int(way.get("id")), "tags": tags}
            original_way_parts.setdefault(int(way.get("id")), []).append(ident)

    used = {int(n.get("ref")) for w in ways for n in w.findall("nd")}
    result = ET.Element("osm", {"version": "0.6", "generator": "phase16 exact-box clip"})
    ET.SubElement(result, "bounds", dict(zip(("minlon", "minlat", "maxlon", "maxlat"), map(str, BOX))))
    for key in sorted(used):
        result.append(copy.deepcopy(nodes[key] if key in nodes else new_nodes[key]))
    result.extend(ways)
    kept_relations = 0
    for relation in source.findall("relation"):
        tags = {t.get("k"): t.get("v") for t in relation.findall("tag")}
        if tags.get("type") != "restriction":
            continue
        members = relation.findall("member")
        valid = all(
            (m.get("type") == "node" and int(m.get("ref")) in used)
            or (m.get("type") == "way" and len(original_way_parts.get(int(m.get("ref")), [])) == 1)
            for m in members)
        if valid:
            result.append(copy.deepcopy(relation))
            kept_relations += 1
    for node in result.findall("node"):
        lon, lat = float(node.get("lon")), float(node.get("lat"))
        assert BOX[0] - 1e-10 <= lon <= BOX[2] + 1e-10
        assert BOX[1] - 1e-10 <= lat <= BOX[3] + 1e-10
    path = OUT / "network/clipped.osm.xml.gz"
    with gzip.GzipFile(filename=str(path), mode="wb", mtime=0) as destination:
        destination.write(ET.tostring(result, encoding="utf-8", xml_declaration=True))
    write_json(OUT / "network/clipping.json", {
        "source": str(SOURCE.relative_to(ROOT)), "source_sha256": sha(SOURCE),
        "bbox_west_south_east_north": BOX, "nodes": len(used), "ways": len(ways),
        "synthetic_boundary_nodes": len(new_nodes), "preserved_restrictions": kept_relations,
        "source_ways": source_ways, "clipped_sha256": sha(path)})
    return path


def build():
    OUT.joinpath("network").mkdir(parents=True, exist_ok=True)
    clipped = clip_osm()
    command = [shutil.which("netconvert") or "netconvert", "--osm-files", str(clipped),
               "--keep-edges.by-vclass", "passenger", "--output.original-names", "true",
               "--osm.all-attributes", "true", "--output-file", str(OUT / "network/us101.net.xml.gz")]
    write_json(OUT / "netconvert-command.json", command)
    with (OUT / "netconvert.log").open("w") as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)


def audit():
    import sumolib
    from sumolib import geomhelper
    net_path = OUT / "network/us101.net.xml.gz"
    net = sumolib.net.readNet(str(net_path), withInternal=EXPANDED)
    clipping = json.loads((OUT / "network/clipping.json").read_text())
    placement = json.loads((ROOT / "assets/phase15e/placement.json").read_text())
    manifest = json.loads((ROOT / "assets/phase15e/import-manifest.json").read_text())
    by_host = {e["edge"]: e for e in manifest["edges"]}

    def original(edge):
        key = edge.getID().lstrip("-").split("#")[0]
        return clipping["source_ways"].get(key, {}).get("source_way")

    def outgoing(edge):
        for nxt, connections in edge.getOutgoing().items():
            if nxt.allows("passenger") and any(c.getFromLane().allows("passenger")
                                               and c.getToLane().allows("passenger") for c in connections):
                yield nxt

    def walk(starts, blocked=(), allowed=None):
        previous = {e.getID(): None for e in starts}
        queue = collections.deque(starts)
        while queue:
            edge = queue.popleft()
            for nxt in sorted(outgoing(edge), key=lambda e: e.getID()):
                ident = nxt.getID()
                if ident in previous or ident in blocked or (allowed is not None and ident not in allowed):
                    continue
                previous[ident] = edge.getID()
                queue.append(nxt)
        return previous

    def path(previous, target):
        if target not in previous:
            return None
        result = []
        while target is not None:
            result.append(target)
            target = previous[target]
        return result[::-1]

    def fastest_route(starts, target, closed):
        """Static passenger Dijkstra, including SUMO internal connector costs.

        Length and time belong to the fastest free-flow path, including the
        complete first and last edges. No traffic or signal waiting is modeled.
        """
        best, previous, queue = {}, {}, []
        for edge in starts:
            if edge.getID() in closed or not edge.allows("passenger"):
                continue
            cost = edge.getLength() / edge.getSpeed()
            best[edge.getID()] = (cost, edge.getLength())
            previous[edge.getID()] = None
            heapq.heappush(queue, (cost, edge.getID()))
        while queue:
            cost, ident = heapq.heappop(queue)
            if cost != best[ident][0]:
                continue
            if ident == target:
                return {"exists": True, "edges": path(previous, target),
                        "length_m": best[ident][1], "free_flow_time_s": cost}
            edge = net.getEdge(ident)
            for nxt in sorted(outgoing(edge), key=lambda e: e.getID()):
                if nxt.getID() in closed:
                    continue
                options = []
                for connection in edge.getOutgoing()[nxt]:
                    if not (connection.getFromLane().allows("passenger")
                            and connection.getToLane().allows("passenger")):
                        continue
                    via, seconds, length = connection.getViaLaneID(), 0., 0.
                    while via:
                        lane = net.getLane(via)
                        length += lane.getLength()
                        seconds += lane.getLength() / lane.getSpeed()
                        links = lane.getOutgoing()
                        via = links[0].getViaLaneID() if links else ""
                    options.append((seconds, length))
                seconds, length = min(options)
                candidate = cost + seconds + nxt.getLength() / nxt.getSpeed()
                if nxt.getID() not in best or candidate < best[nxt.getID()][0]:
                    best[nxt.getID()] = (candidate, best[ident][1] + length + nxt.getLength())
                    previous[nxt.getID()] = ident
                    heapq.heappush(queue, (candidate, nxt.getID()))
        return {"exists": False, "edges": None, "length_m": None, "free_flow_time_s": None}

    chains = []
    for chain in placement["chains"]:
        ways = {by_host[e]["osm_way"] for e in chain["edges"]}
        edges = [e for e in net.getEdges() if original(e) in ways and e.allows("passenger")]
        starts = [e for e in edges if original(e) == by_host[chain["edges"][0]]["osm_way"]]
        ends = [e for e in edges if original(e) == by_host[chain["edges"][-1]]["osm_way"]]
        previous = walk(starts, allowed={e.getID() for e in edges})
        candidates = [path(previous, e.getID()) for e in ends]
        candidates = [p for p in candidates if p]
        direction = "southbound" if chain["nodes"][0] == 47 else "northbound"
        chains.append({"direction": direction, "continuous": bool(candidates),
                       "source_edges": [e.getID() for e in starts], "destination_edges": [e.getID() for e in ends],
                       "path": min(candidates, key=lambda p: (len(p), p)) if candidates else None})
    sb = next(c for c in chains if c["direction"] == "southbound")
    upstream = str(placement["chosen_gap"]["upstream_osm_key"][1])
    ramps = [e for e in net.getNode(upstream).getOutgoing()
             if "motorway_link" in e.getType() and e.allows("passenger")]
    tree_edges = [e for e in net.getEdges() if original(e) == placement["tree"]["osm_way"]]
    assert len(tree_edges) == 1, "the fixed tree way must map unambiguously"
    tree_edge = tree_edges[0]
    # Source geographic midpoint, not the host's junction-trimmed footprint station.
    host_map = json.loads((ROOT / "maps/us101.json").read_text())
    road = host_map["edges"][placement["tree"]["edge"]]
    start, end = host_map["nodes"][road["from"]], host_map["nodes"][road["to"]]
    shape = [(start["lon"], start["lat"])] + [(p["lon"], p["lat"]) for p in road["shape"]] + [(end["lon"], end["lat"])]
    import math
    scale = 111320 * math.cos(math.radians(37.75))
    lengths = [math.hypot((b[0]-a[0])*scale, (b[1]-a[1])*111320) for a, b in zip(shape, shape[1:])]
    offset = sum(lengths) / 2
    for a, b, length in zip(shape, shape[1:], lengths):
        if offset <= length:
            lon, lat = (a[i] + (b[i]-a[i])*offset/length for i in (0, 1))
            break
        offset -= length
    xy = net.convertLonLat2XY(lon, lat)
    tree_station, tree_distance = geomhelper.polygonOffsetAndDistanceToPoint(xy, tree_edge.getShape())
    unblocked = walk(ramps)
    blocked = walk(ramps, blocked={e.getID() for e in tree_edges})
    surface = [e.getID() for e in net.getEdges() if e.getID() in blocked
               and "motorway" not in e.getType()]
    destinations = []
    for target in sb["destination_edges"]:
        destinations.append({"edge": target, "path_via_ramp_before_closure": path(unblocked, target),
                             "path_avoiding_tree": path(blocked, target),
                             "valid_alternative": target in blocked})
        if EXPANDED:
            destinations[-1]["bypass_route"] = fastest_route(ramps, target, {e.getID() for e in tree_edges})
            destinations[-1]["open_tree_control_route"] = fastest_route(ramps, target, set())
            assert destinations[-1]["bypass_route"]["exists"] == (target in blocked)
    post_tree = [e.getID() for e in net.getEdges() if original(e) in {
        by_host[i]["osm_way"] for i in (1583, 443, 442)}]
    map_passed = all(c["continuous"] for c in chains) and bool(surface) and bool(ramps) and (
        "motorway" in tree_edge.getType() and tree_distance < 20 and tree_edge.getLaneNumber() == 5)
    alternative_passed = bool(destinations) and all(d["valid_alternative"] for d in destinations)
    # Independent upper-bound check on the retained 15e graph. Ignoring turn
    # restrictions cannot manufacture a false no-path result from a legal path.
    adjacent = collections.defaultdict(set)
    for item in host_map["edges"]:
        if item["id"] != road["id"]:
            adjacent[item["from"]].add(item["to"])
    reached = {placement["chosen_gap"]["upstream_exit_node"]}
    pending = collections.deque(reached)
    while pending:
        for node in adjacent[pending.popleft()]:
            if node not in reached:
                reached.add(node)
                pending.append(node)
    sb_chain = next(c for c in placement["chains"] if c["nodes"][0] == 47)
    relaxed = {"method": "All retained directed road-node transitions, ignoring turn and lane restrictions",
               "blocked_host_edge": road["id"], "source_host_node": placement["chosen_gap"]["upstream_exit_node"],
               "destination_host_node": sb_chain["nodes"][-1],
               "destination_reachable": sb_chain["nodes"][-1] in reached,
               "reachable_nodes": len(reached),
               "post_tree_road_origins_reachable": {str(i): host_map["edges"][i]["from"] in reached
                                                    for i in (1583, 443, 442)}}
    stop = None if map_passed and alternative_passed else (
        "STOP: the fixed SUMO map has no passenger-vehicle route from the last southbound exit "
        "to the retained destination beyond the tree while avoiding the blocked section. "
        "The required affected-trip alternative is absent; no traffic, validity, record or spoof run was started.")
    unchanged = {}
    for name in ("maps/us101.osm", "maps/us101.json", "assets/phase15e/placement.json",
                 "assets/phase15e/volume.json", "assets/phase15e/traffic-inputs.json", "experiments/phase15e/traffic.rs"):
        data = (ROOT / name).read_bytes()
        retained = subprocess.check_output(["git", "show", STOP_COMMIT + ":" + name], cwd=ROOT)
        assert data == retained, f"retained input changed: {name}"
        unchanged[name] = hashlib.sha256(data).hexdigest()
    assert not subprocess.check_output(["git", "diff", STOP_COMMIT, "--", "src/"], cwd=ROOT)
    result = {
        "phase": "16 citation-fix rerun", "decision": "CONTINUE" if stop is None else "STOP", "stop": stop,
        "map_gate_passed": map_passed, "affected_destination_alternative_gate_passed": alternative_passed,
        "sumo_version": subprocess.check_output(["sumo", "--version"], text=True).splitlines()[0],
        "bbox_west_south_east_north": BOX, "source_osm_sha256": sha(SOURCE),
        "clipped_osm_sha256": sha(OUT / "network/clipped.osm.xml.gz"), "sumo_net_sha256": sha(net_path),
        "network_edges": len(net.getEdges()), "network_nodes": len(net.getNodes()), "mainline_chains": chains,
        "last_exit_osm_node": upstream, "exit_ramp_edges": [e.getID() for e in ramps],
        "reachable_surface_edges": sorted(surface), "reachable_avoiding_tree_count": len(blocked),
        "reachable_post_tree_mainline": sorted(set(post_tree) & blocked.keys()),
        "post_tree_mainline_edges": sorted(post_tree), "destinations": destinations,
        "independent_retained_graph_confirmation": relaxed,
        "tree": {"source_way": placement["tree"]["osm_way"], "host_edge": road["id"],
                 "distance_from_exit_retained_m": placement["tree"]["D_m"],
                 "source_center_lon_lat": [lon, lat], "sumo_edge": tree_edge.getID(),
                 "sumo_edge_lanes": tree_edge.getLaneNumber(), "sumo_edge_length_m": tree_edge.getLength(),
                 "projected_center_station_m": tree_station, "projection_distance_m": tree_distance,
                 "footprint_length_m": placement["footprint_length_m"], "start_s": placement["start_s"],
                 "duration_s": placement["duration_s"]},
        "retained_input_sha256": unchanged, "src_unchanged": True,
        "sumo_traffic_runs": 0, "validity_runs": 0, "record_runs": 0, "spoof_runs": 0, "scored_rows": 0,
        "method": "Exhaustive directed passenger-edge connectivity; no closure vehicle physics or scores. "
                  "The blocked-way removal is only a topological test: an 8 m all-lane cut on that way has the same reachability effect. "
                  "Edge-level reachability permits lane changes, making a no-path finding conservative.",
        "caveat": "No SUMO time-step was run. Traffic validity and efficacy remain unmeasured."}
    if EXPANDED:
        post_ids = set(post_tree) | {tree_edge.getID()}
        incoming = []
        for ident in sorted(post_tree):
            edge = net.getEdge(ident)
            node = edge.getFromNode()
            sources = [e for e in node.getIncoming() if not e.isSpecial() and e.allows("passenger")]
            incoming.append({"downstream_edge": ident, "join_node": node.getID(),
                             "incoming_edges": sorted(e.getID() for e in sources),
                             "non_mainline_incoming_edges": sorted(e.getID() for e in sources if e.getID() not in post_ids),
                             "outgoing_ramps": sorted(e.getID() for e in node.getOutgoing()
                                                      if "motorway_link" in e.getType())})
        if not map_passed:
            stop = ("STOP: the single authorized east-west expansion failed an original structural map check. "
                    "No further widening or traffic, validity, record or spoof run was performed.")
        elif not alternative_passed:
            missing_reentry = not any(item["non_mainline_incoming_edges"] for item in incoming)
            outbound = any("1164067021" in item["outgoing_ramps"] for item in incoming)
            stop = ("STOP: the single authorized east-west expansion still has no drivable bypass from exit ramp "
                    "8915060 to affected destination 28326941 while avoiding tree edge 1343758309. ")
            if missing_reentry:
                stop += "No southbound on-ramp joins the post-tree mainline inside latitude 37.738 to 37.762; "
            if outbound:
                stop += "ramp 1164067021 leaves US-101 for I-280 South and is not a re-entry. "
            stop += "No further widening or traffic, validity, record or spoof run was performed."
        result.update({"phase": "16 single pre-traffic map expansion",
                       "stop": stop, "decision": "CONTINUE" if stop is None else "STOP",
                       "network_edges": len(net.getEdges(withInternal=False)),
                       "network_internal_edges": len(net.getEdges(withInternal=True)) - len(net.getEdges(withInternal=False)),
                       "network_loaded_edges": len(net.getEdges(withInternal=True)),
                       "source_osm_path": str(SOURCE.relative_to(ROOT)),
                       "old_bbox_west_south_east_north": (-122.410, 37.738, -122.400, 37.762),
                       "bbox_expansions_used": 1, "further_expansion_allowed": False,
                       "closed_edges": sorted(e.getID() for e in tree_edges),
                       "post_tree_incoming_connections": incoming,
                       "affected_destinations_definition": "Unchanged southbound through destination from retained 15e mainline chain; all affected through trips share this destination.",
                       "route_cost_definition": "Fastest free-flow passenger route from start of last exit ramp through end of affected destination; includes internal connector lengths/times, excludes signal/traffic waiting.",
                       "independent_retained_graph_confirmation": {
                           **relaxed, "scope": "Historical narrow bbox only; not evidence of expanded-map reachability"}})
    write_json(OUT / "map-gate.json", result)
    print(json.dumps({k: result[k] for k in ("decision", "map_gate_passed", "affected_destination_alternative_gate_passed", "stop")}))
    return 0 if stop is None else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--expanded", action="store_true", help="Use only the one authorized west/east expansion")
    args = parser.parse_args()
    if args.expanded:
        EXPANDED = True
        BOX = (-122.425, 37.738, -122.385, 37.762)
        OUT = ROOT / "experiments/phase16/map-change"
        SOURCE = OUT / "us101-expanded.osm.gz"
        plan = json.loads((OUT / "plan.json").read_text())
        acquisition = json.loads((OUT / "acquisition.json").read_text())
        assert tuple(plan["new_bbox_west_south_east_north"]) == BOX
        assert plan["allowed_bbox_expansions"] == 1 and not plan["further_expansion_allowed"]
        assert sha(SOURCE) == acquisition["merged_compressed_sha256"], "acquired source hash mismatch"
    if args.build:
        build()
    sys.exit(audit())
