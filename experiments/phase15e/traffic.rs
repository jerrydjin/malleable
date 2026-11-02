use malleable::{
    incident::LaneIncident,
    network::{Network, ScheduledCar, TownSim, NET_DT_S, QUEUED_MPS},
    record::{self, Arm, Evidence, Proposal, RecordConfig, Replies, Snapshot},
    road_map::RoadMap,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Input {
    pub car: u32,
    pub route: usize,
    pub depart_s: f64,
    pub mainline: bool,
    pub affected: bool,
    pub source: usize,
}
pub struct World {
    pub net: Network,
    pub routes: Vec<Vec<usize>>,
    pub through: Vec<Vec<usize>>,
    pub local: Vec<usize>,
    pub blocked_edge: usize,
    pub blocked_link: usize,
    pub incident: LaneIncident,
    pub replies: Replies,
}
fn read_json(p: &str) -> Result<Value, String> {
    serde_json::from_slice(&std::fs::read(p).map_err(|e| e.to_string())?).map_err(|e| e.to_string())
}
fn gcd(mut a: usize, mut b: usize) -> usize {
    while b > 0 {
        let r = a % b;
        a = b;
        b = r;
    }
    a
}
pub fn build() -> Result<World, String> {
    let map = RoadMap::read("maps/us101.json")?;
    let p = read_json("assets/phase15e/placement.json")?;
    if p["valid"] != true {
        return Err("STOP: placement must pass".into());
    }
    let mut n = Network::from_road_map_full_lanes(&map)?;
    let blocked_edge = p["tree"]["edge"].as_u64().unwrap() as usize;
    let blocked_link = n
        .links
        .iter()
        .find(|l| !l.is_connector() && l.edge == blocked_edge)
        .ok_or("missing blocked road")?
        .id;
    let incident = LaneIncident {
        version: 1,
        id: "us101-tree".into(),
        kind: "blocked_road".into(),
        map: "maps/us101.json".into(),
        edge: blocked_edge,
        from_node: map.edges[blocked_edge].from,
        to_node: map.edges[blocked_edge].to,
        lane: 0,
        position_m: (n.links[blocked_link].len - 8.) / 2.,
        length_m: 8.,
        start_s: 240.,
        duration_s: 900.,
        rationale: "Fixed longest exit gap; retained 15a duration".into(),
    };
    if incident.position_m < 0. {
        return Err("STOP: fixed tree footprint does not fit host road".into());
    }
    let mut through_paths = Vec::new();
    let mut all_paths = BTreeSet::new();
    for chain in p["chains"].as_array().unwrap() {
        if chain["boundary_entry"] != true || chain["boundary_exit"] != true {
            return Err("STOP: mainline chain lacks boundary endpoints".into());
        }
        let edges: Vec<_> = chain["edges"]
            .as_array()
            .unwrap()
            .iter()
            .map(|x| x.as_u64().unwrap() as usize)
            .collect();
        let denominator = edges
            .iter()
            .map(|e| map.edges[*e].lanes as usize)
            .fold(1, |a, b| a / gcd(a, b) * b);
        let mut variants = Vec::new();
        for q in 0..denominator {
            let mut path = Vec::new();
            for edge in &edges {
                let lanes: Vec<_> = n
                    .links
                    .iter()
                    .filter(|l| !l.is_connector() && l.edge == *edge)
                    .map(|l| l.id)
                    .collect();
                let lane = lanes[q * lanes.len() / denominator];
                if let Some(&previous) = path.last() {
                    let connector = *n
                        .moves_from(previous)
                        .iter()
                        .find(|c| n.links[**c].via == Some((previous, lane)))
                        .ok_or("missing legal lane connector")?;
                    path.push(connector);
                }
                path.push(lane);
            }
            all_paths.insert(path.clone());
            variants.push(path);
        }
        through_paths.push(variants);
    }
    // Same straightest-conflicting-flow construction/rates as 15b, at ramp/local junctions.
    let ramp_nodes: BTreeSet<_> = n
        .links
        .iter()
        .filter(|l| !l.is_connector() && l.class == malleable::network::RoadClass::Ramp)
        .flat_map(|l| [l.from, l.to])
        .collect();
    let mut local_paths = BTreeSet::new();
    let mut seen = BTreeSet::new();
    for l in n.links.iter().filter(|l| {
        !l.is_connector()
            && !matches!(
                l.class,
                malleable::network::RoadClass::Motorway | malleable::network::RoadClass::Ramp
            )
            && ramp_nodes.contains(&l.to)
    }) {
        if !seen.insert((l.edge, l.from, l.to)) {
            continue;
        }
        let direction = |id: usize| {
            let road = &n.links[id];
            let a = road.pts.first().unwrap();
            let b = road.pts.last().unwrap();
            let norm = (b[0] - a[0]).hypot(b[1] - a[1]).max(1e-9);
            [(b[0] - a[0]) / norm, (b[1] - a[1]) / norm]
        };
        let a = direction(l.id);
        let mut choices: Vec<_> = n
            .moves_from(l.id)
            .iter()
            .map(|c| {
                let (_, out) = n.links[*c].via.unwrap();
                let b = direction(out);
                (a[0] * b[0] + a[1] * b[1], *c, out)
            })
            .collect();
        choices.sort_by(|a, b| b.0.total_cmp(&a.0).then(a.1.cmp(&b.1)));
        if let Some((_, c, out)) = choices.first() {
            let conflicts = n.conflicts_of(*c).iter().any(|other| {
                n.links[*other].via.is_some_and(|(i, o)| {
                    n.links[i].class == malleable::network::RoadClass::Ramp
                        || n.links[o].class == malleable::network::RoadClass::Ramp
                })
            });
            if conflicts {
                local_paths.insert(vec![l.id, *c, *out]);
            }
        }
    }
    all_paths.extend(local_paths.iter().cloned());
    for path in &all_paths {
        n.register_experiment_route(path.clone())?;
    }
    let route_objects = n.routes();
    let routes: Vec<_> = route_objects
        .iter()
        .map(|(_, _, r)| r.links.clone())
        .collect();
    let ids: BTreeMap<_, _> = routes
        .iter()
        .cloned()
        .enumerate()
        .map(|(id, p)| (p, id))
        .collect();
    let through = through_paths
        .iter()
        .map(|v| v.iter().map(|p| ids[p]).collect())
        .collect();
    let local = local_paths.iter().map(|p| ids[p]).collect();
    Ok(World {
        net: n,
        routes,
        through,
        local,
        blocked_edge,
        blocked_link,
        incident,
        replies: Replies::read("docs/gates/phase-15-model-replies.json")?,
    })
}
pub fn population(seed: u64, w: &World) -> Vec<Input> {
    let mut result = Vec::new();
    let main_vph = read_json("assets/phase15e/volume.json").unwrap()["mainline_vph_each_direction"]
        .as_f64()
        .unwrap();
    for (flow, variants) in w.through.iter().enumerate() {
        let headway = 3600. / main_vph;
        let phase = (seed
            .wrapping_mul(6364136223846793005)
            .wrapping_add(flow as u64)
            % 1_000_000) as f64
            / 1_000_000.
            * headway;
        let mut index = 0;
        let mut at = phase;
        while at < 900. {
            let route = variants[(index + seed as usize) % variants.len()];
            result.push(Input {
                car: 1 + flow as u32 * 10000 + index as u32,
                route,
                depart_s: at,
                mainline: true,
                affected: w.routes[route]
                    .iter()
                    .any(|l| w.net.links[*l].edge == w.blocked_edge)
                    && at >= 240.
                    && at < 1140.,
                source: w.routes[route][0],
            });
            at += headway;
            index += 1;
        }
    }
    for (flow, &route) in w.local.iter().enumerate() {
        let source = w.routes[route][0];
        let headway = 3600. / malleable::network::demand_vph(w.net.links[source].class);
        let phase = (seed
            .wrapping_mul(6364136223846793005)
            .wrapping_add(flow as u64)
            % 1_000_000) as f64
            / 1_000_000.
            * headway;
        let mut index = 0;
        let mut at = phase;
        while at < 900. {
            result.push(Input {
                car: 100000 + flow as u32 * 1000 + index as u32,
                route,
                depart_s: at,
                mainline: false,
                affected: false,
                source,
            });
            at += headway;
            index += 1;
        }
    }
    result.sort_by(|a, b| a.depart_s.total_cmp(&b.depart_s).then(a.car.cmp(&b.car)));
    result
}
fn config(w: &World, arm: Arm, tree: bool) -> Result<RecordConfig, String> {
    let sam = record::sam_summary()?;
    Ok(RecordConfig {
        arm,
        sensor_range_m: 300.,
        proposal: if tree {
            Some(Proposal {
                link: w.blocked_link,
                position_m: w.incident.position_m,
                length_m: 8.,
                start_s: 240.,
                duration_s: 900.,
                spoof: false,
                evidence: Evidence {
                    image_sha256: sam["image_sha256"].as_str().unwrap().into(),
                    mask_sha256: sam["mask_sha256"].as_str().unwrap().into(),
                    label: "blocked".into(),
                },
            })
        } else {
            None
        },
        reply: w.replies.tree.reply.clone(),
        priority_reach: w.replies.priority.reply.reach.clone(),
    })
}
#[derive(Default, Serialize)]
pub struct Spill {
    pub first_at_s: Option<f64>,
    pub seconds: f64,
    pub peak_pending: usize,
    pub examples: Vec<Value>,
}
pub struct Outcome {
    pub home: BTreeMap<u32, f64>,
    pub snapshot: Snapshot,
    pub collisions: u64,
    pub overlaps: u64,
    pub spill: Spill,
    pub ended_at_s: f64,
}
pub fn simulate(seed: u64, w: &World, inputs: &[Input], tree: bool) -> Result<Outcome, String> {
    let mut n = w.net.clone();
    if tree {
        n.add_incident(w.incident.clone())?;
    }
    let schedule: Vec<_> = inputs
        .iter()
        .map(|t| ScheduledCar {
            id: t.car,
            route: t.route,
            depart_s: t.depart_s,
        })
        .collect();
    let mut sim = TownSim::with_schedule_on(seed, &schedule, n)?;
    sim.enable_record(config(w, Arm::SensorOnly, tree)?)?;
    let source_set: BTreeSet<_> = inputs
        .iter()
        .filter(|t| {
            t.mainline
                && w.routes[t.route]
                    .iter()
                    .any(|l| w.net.links[*l].edge == w.blocked_edge)
        })
        .map(|t| t.source)
        .collect();
    let mut due: BTreeMap<usize, Vec<(f64, u32)>> = BTreeMap::new();
    for t in inputs {
        if source_set.contains(&t.source) {
            due.entry(t.source).or_default().push((t.depart_s, t.car));
        }
    }
    for v in due.values_mut() {
        v.sort_by(|a, b| a.0.total_cmp(&b.0));
    }
    let mut entered = BTreeSet::new();
    let mut collisions = 0u64;
    let mut overlaps = 0u64;
    let mut spill = Spill::default();
    for step in 0..=10000 {
        collisions += sim.crossing_conflicts() as u64;
        overlaps += sim.overlaps() as u64;
        if sim.time() >= 240. && sim.time() < 1140. && !source_set.is_empty() {
            let bodies = sim.bodies();
            for (id, link, _, _) in &bodies {
                if source_set.contains(link) {
                    entered.insert(*id);
                }
            }
            let mut blocked = Vec::new();
            let mut pending_total = 0;
            for source in &source_set {
                let pending = due[source]
                    .iter()
                    .filter(|(at, id)| *at < sim.time() - NET_DT_S && !entered.contains(id))
                    .count();
                if pending == 0 {
                    continue;
                }
                let stationary = bodies.iter().any(|(id, link, rear, _)| {
                    link == source
                        && *rear < malleable::world::CAR_LENGTH_M + malleable::world::MIN_GAP_M + 1.
                        && sim.speed_of(*id).is_some_and(|v| v < QUEUED_MPS)
                });
                if stationary {
                    blocked.push(*source);
                    pending_total += pending;
                }
            }
            if !blocked.is_empty() {
                spill.first_at_s.get_or_insert(sim.time());
                spill.seconds += NET_DT_S;
                spill.peak_pending = spill.peak_pending.max(pending_total);
                if spill.examples.len() < 3 {
                    spill
                        .examples
                        .push(json!({"at_s":sim.time(),"sources":blocked,"pending":pending_total}));
                }
            }
        } else if sim.time() < 240. && !source_set.is_empty() {
            for (id, link, _, _) in sim.bodies() {
                if source_set.contains(&link) {
                    entered.insert(id);
                }
            }
        }
        if sim.completed_trips().len() == inputs.len() && step % 4 == 0 {
            break;
        }
        sim.step();
    }
    let ended_at_s = sim.time();
    Ok(Outcome {
        home: sim.completed_trips(),
        snapshot: sim.record_snapshot(),
        collisions,
        overlaps,
        spill,
        ended_at_s,
    })
}
fn stats(v: &[f64]) -> Value {
    let mut v = v.to_vec();
    v.sort_by(f64::total_cmp);
    json!({"n":v.len(),"median_s":if v.is_empty(){None}else{Some(malleable::rush_hour::median(&v))},"mean_s":if v.is_empty(){None}else{Some(v.iter().sum::<f64>()/v.len() as f64)},"min_s":v.first(),"max_s":v.last(),"p95_s":if v.is_empty(){None}else{Some(v[((v.len() as f64*0.95).ceil() as usize).saturating_sub(1)])}})
}
fn describe(w: &World) -> Value {
    json!({"kind":"traffic_input_declaration_before_validity","map_sha256":record::sha256("maps/us101.json").unwrap(),"placement_sha256":record::sha256("assets/phase15e/placement.json").unwrap(),"volume_sha256":record::sha256("assets/phase15e/volume.json").unwrap(),"through_weighted_route_variants":w.through,"local_routes":w.local,"local_paths":w.local.iter().map(|i|&w.routes[*i]).collect::<Vec<_>>(),"blocked_edge":w.blocked_edge,"blocked_link":w.blocked_link,"incident":w.incident,"population":([1,2,3,4,5,6,7,8,9,10].iter().map(|s|{let p=population(*s,w);json!({"seed":s,"trips":p.len(),"mainline":p.iter().filter(|t|t.mainline).count(),"affected_expected":p.iter().filter(|t|t.affected).count()})}).collect::<Vec<_>>())})
}
fn validity(w: &World) -> Result<Value, String> {
    for path in [
        "experiments/phase15e/traffic.rs",
        "experiments/phase15e/see-only-validity-plan.md",
        "assets/phase15e/traffic-inputs.json",
        "assets/phase15e/placement.json",
        "assets/phase15e/volume.json",
        "assets/phase15e/generated-code.sha256",
    ] {
        let tracked = std::process::Command::new("git")
            .args(["cat-file", "-e", &format!("HEAD:{path}")])
            .status()
            .map_err(|e| e.to_string())?;
        let clean = std::process::Command::new("git")
            .args(["diff", "--quiet", "HEAD", "--", path])
            .status()
            .map_err(|e| e.to_string())?;
        if !tracked.success() || !clean.success() {
            return Err(format!(
                "Commit validity code and declaration first: {path}"
            ));
        }
    }
    for line in std::fs::read_to_string("assets/phase15e/generated-code.sha256")
        .map_err(|e| e.to_string())?
        .lines()
    {
        let (h, f) = line
            .split_once("  ")
            .ok_or("bad generated source manifest")?;
        if record::sha256(&format!("{}/{f}", env!("CARGO_MANIFEST_DIR")))? != h {
            return Err(format!("generated source changed: {f}"));
        }
    }

    // All references are SOLO see_only; no RECORD arm or benefit comparison runs here.
    let unique: BTreeSet<_> = w.through.iter().flatten().copied().collect();
    let mut free = BTreeMap::new();
    for (index, route) in unique.iter().enumerate() {
        let t = Input {
            car: 9999999,
            route: *route,
            depart_s: 0.,
            mainline: true,
            affected: false,
            source: w.routes[*route][0],
        };
        let r = simulate(1, w, &[t], false)?;
        let on = r
            .home
            .get(&9999999)
            .zip(r.snapshot.entered.get(&9999999))
            .map(|(h, e)| h - e)
            .ok_or("solo trip unfinished")?;
        free.insert(*route, on);
        eprintln!("solo mainline reference {}/{}", index + 1, unique.len());
    }
    let mut rows = Vec::new();
    for seed in 1..=10 {
        let trips = population(seed, w);
        let r = simulate(seed, w, &trips, true)?;
        let mut delays = Vec::new();
        let mut waits = Vec::new();
        let mut per = Vec::new();
        let expected = trips.iter().filter(|t| t.affected).count();
        for t in &trips {
            let home = r.home.get(&t.car).copied();
            let entry = r.snapshot.entered.get(&t.car).copied();
            let on = home.zip(entry).map(|(h, e)| h - e);
            let excess = on.zip(free.get(&t.route)).map(|(on, f)| on - f);
            let off = entry.map(|e| e - t.depart_s);
            if t.affected {
                if let Some(d) = excess {
                    delays.push(d);
                }
                if let Some(d) = off {
                    waits.push(d);
                }
            }
            let status = if home.is_some() {
                "completed"
            } else if t.depart_s > r.ended_at_s {
                "never_departed"
            } else if entry.is_none() {
                "never_entered"
            } else {
                "on_network"
            };
            per.push(json!({"car":t.car,"route":t.route,"mainline":t.mainline,"affected":t.affected,"depart_s":t.depart_s,"entry_s":entry,"home_s":home,"on_map_trip_s":on,"solo_on_map_trip_s":free.get(&t.route),"on_map_excess_s":excess,"off_map_wait_s":off,"unfinished_status":status,"final_link":r.snapshot.final_links.get(&t.car)}));
        }
        let distribution = stats(&delays);
        let delay_pass =
            delays.len() == expected && distribution["median_s"].as_f64().is_some_and(|m| m >= 30.);
        rows.push(json!({"seed":seed,"arm":"see_only","sensor_range_m":300,"trips":trips.len(),"completed":r.home.len(),"affected_expected":expected,"affected_on_map_excess":distribution,"affected_off_map_wait":stats(&waits),"delay_at_least_30s":delay_pass,"boundary_spillback":r.spill,"queue_on_map":r.spill.seconds==0.,"collisions":r.collisions,"overlaps":r.overlaps,"all_trips_finished":r.home.len()==trips.len(),"leak_violations":r.snapshot.leak_violations(),"per_trip":per,"record":r.snapshot}));
        eprintln!("15e see-only validity seed {seed} complete; every trip retained");
    }
    let wins = rows
        .iter()
        .filter(|r| r["delay_at_least_30s"] == true)
        .count();
    let queue = rows.iter().all(|r| r["queue_on_map"] == true);
    let complete = rows.iter().all(|r| r["all_trips_finished"] == true);
    let safe = rows
        .iter()
        .all(|r| r["collisions"] == 0 && r["overlaps"] == 0 && r["leak_violations"] == 0);
    Ok(
        json!({"kind":"see_only_validity_before_record_scoring","generated_code_sha256":record::sha256("assets/phase15e/generated-code.sha256")?,"traffic_inputs_sha256":record::sha256("assets/phase15e/traffic-inputs.json")?,"volume_sha256":record::sha256("assets/phase15e/volume.json")?,"seeds":rows,"delay_qualifying_seeds":wins,"queue_on_map":queue,"all_trips_finished":complete,"safety":safe,"valid":wins>=8 && queue,"decision":if wins>=8 && queue{"CONTINUE_TO_PREREGISTRATION"}else{"STOP"},"free_flow_on_map_s":free}),
    )
}
fn main() -> Result<(), String> {
    let part = std::env::args()
        .skip(1)
        .find_map(|a| a.strip_prefix("part=").map(str::to_string))
        .unwrap_or("describe".into());
    let w = build()?;
    match part.as_str() {
        "describe" => println!("{}", describe(&w)),
        "validity" => println!("{}", validity(&w)?),
        _ => return Err("Only describe or validity before preregistration".into()),
    }
    Ok(())
}
