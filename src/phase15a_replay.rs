//! Replay of the scored Phase 15a seed 1 run. Not a new experiment.
//!
//! The score row is the same calculation as `examples/phase15_gate.rs` for
//! seed 1, arm RECORD, sensor range 300 m. Replies come from the committed
//! file. This module does not call Baseten or Muse.

use crate::board::{BoardFrame, BoardStrip, DinnerBoard, DinnerRoad};
use crate::incident::LaneIncident;
use crate::network::{NetFrame, Network};
use crate::record::{self, Arm, Evidence, Proposal, RecordConfig, Replies, Status};
use crate::replay::ReplayArchive;
use crate::road_map::RoadMap;
use crate::rush_hour::{self, Fcfs, Run, Truth};
use crate::world::{CAR_LENGTH_M, CAR_WIDTH_M, LANE_WIDTH_M};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::time::Instant;

pub const LABEL: &str = "replay of scored run, seed 1";
pub const GATE_FILE: &str = "docs/gates/phase-15a-scores.jsonl";
pub const REPLY_FILE: &str = "docs/gates/phase-15-model-replies.json";
pub const OUT_PATH: &str = "recordings/phase15a-seed1.json";

const SEED: u64 = 1;
const RANGE_M: f64 = 300.0;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Phase15aBeat {
    pub kind: String,
    pub at_s: f64,
    pub car: Option<u32>,
    pub text: String,
}

/// What the board draws for this one scored run.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Phase15aView {
    pub label: String,
    pub note: String,
    pub seed: u64,
    pub arm: String,
    pub sensor_range_m: f64,
    pub gate_file: String,
    pub reply_file: String,
    pub live_model_calls: u32,
    pub link: usize,
    pub incident_visible_s: f64,
    pub focus_m: f64,
    pub beats: Vec<Phase15aBeat>,
    /// Gate score row for seed 1, RECORD, 300 m.
    pub scored: Value,
}

/// The retained seed-1 RECORD row at 300 m from the Phase 15a gate file.
pub fn gate_seed1_record_row() -> Result<Value, String> {
    let line = gate_seed1_record_line()?;
    serde_json::from_str(&line).map_err(|e| format!("{GATE_FILE}: {e}"))
}

pub fn scored_row_matches(scored: &Value) -> Result<(), String> {
    let expected = gate_seed1_record_line()?;
    let ours = serde_json::to_string(scored).map_err(|e| e.to_string())?;
    if ours == expected {
        return Ok(());
    }
    let gate: Value = serde_json::from_str(&expected).map_err(|e| e.to_string())?;
    Err(format_mismatch(&gate, scored))
}

fn gate_seed1_record_line() -> Result<String, String> {
    let text = std::fs::read_to_string(GATE_FILE).map_err(|e| format!("{GATE_FILE}: {e}"))?;
    for line in text.lines() {
        if line.is_empty() {
            continue;
        }
        let row: Value = serde_json::from_str(line).map_err(|e| format!("{GATE_FILE}: {e}"))?;
        if row["kind"] == "score"
            && row["part"] == "tree"
            && row["seed"] == json!(SEED)
            && row["arm"] == "RECORD"
            && row["sensor_range_m"] == json!(RANGE_M)
        {
            return Ok(line.to_string());
        }
    }
    Err(format!(
        "no seed {SEED} RECORD {RANGE_M} m row in {GATE_FILE}"
    ))
}

/// Re-run seed 1 from the Phase 15a host and build a board recording.
///
/// Returns an error, and no recording, when the score row does not match
/// `GATE_FILE`.
pub fn record_seed1() -> Result<ReplayArchive, String> {
    let started = Instant::now();
    eprintln!(
        "replaying phase 15a seed {SEED} RECORD {RANGE_M} m from recorded replies ({REPLY_FILE}); live model calls=0"
    );
    let replies = Replies::read(REPLY_FILE)?;
    if replies.tree.source != "model" {
        return Err(format!(
            "{REPLY_FILE} tree source is {}, not the scored model reply",
            replies.tree.source
        ));
    }
    let sam = record::sam_summary()?;
    let (plain, incident, link) = world()?;
    let mut trips = rush_hour::population_on(SEED, &plain);
    for trip in &mut trips {
        trip.truth = Truth::Ordinary;
        trip.reason = "I'm driving through the corridor".into();
        trip.destination = "other".into();
    }
    let mut solo = trips[0].clone();
    solo.depart_s = 0.0;
    solo.request_s = 0.0;
    eprintln!("seed {SEED}: solo reference");
    let (free_run, _) = rush_hour::simulate_trips_recorded(
        SEED,
        &Fcfs,
        vec![solo.clone()],
        &plain,
        config(Arm::SensorOnly, RANGE_M, None, &replies),
    )?;
    let free = free_run.home[&solo.car];
    let mut blocked = plain.clone();
    blocked.add_incident(incident.clone())?;
    let proposal = proposal(&incident, link, &sam, false);
    eprintln!("seed {SEED}: SENSOR_ONLY baseline at {RANGE_M} m");
    let (baseline, baseline_record) = rush_hour::simulate_trips_recorded(
        SEED,
        &Fcfs,
        trips.clone(),
        &blocked,
        config(Arm::SensorOnly, RANGE_M, Some(proposal.clone()), &replies),
    )?;
    eprintln!("seed {SEED}: RECORD at {RANGE_M} m");
    let (run, record) = rush_hour::simulate_trips_recorded(
        SEED,
        &Fcfs,
        trips,
        &blocked,
        config(Arm::Record, RANGE_M, Some(proposal), &replies),
    )?;
    let scored = row(
        SEED,
        RANGE_M,
        "RECORD",
        &run,
        &record,
        &baseline,
        &baseline_record,
        link,
        incident.start_s,
        free,
        &replies.tree.source,
        false,
    );
    if let Err(mismatch) = scored_row_matches(&scored) {
        return Err(mismatch);
    }
    let archive = archive_from_run(run, scored)?;
    archive.validate()?;
    eprintln!(
        "phase 15a seed {SEED} replay matches {GATE_FILE} in {:.1}s",
        started.elapsed().as_secs_f64()
    );
    Ok(archive)
}

fn archive_from_run(run: Run, scored: Value) -> Result<ReplayArchive, String> {
    let edit = scored["record"]["edits"]
        .get(0)
        .cloned()
        .ok_or("scored row has no road edit")?;
    let link = edit["link"].as_u64().ok_or("edit link is not an integer")? as usize;
    let mut town = run.town;
    if !town.incidents.iter().any(|incident| incident.link == link) {
        return Err(format!("recorded town has no incident on edit link {link}"));
    }
    if town.frames.is_empty() {
        town.frames.push(NetFrame {
            make_way: Vec::new(),
            t: 0,
            cars: Vec::new(),
        });
    }
    let incident_visible_s = scored["merge_at_s"]
        .as_f64()
        .or_else(|| edit["since_s"].as_f64())
        .ok_or("edit has no time")?;
    let beats = beats(&scored, &edit)?;
    let outcome = beats
        .iter()
        .find(|beat| beat.kind == "outcome")
        .map(|beat| beat.text.clone())
        .unwrap_or_else(|| LABEL.to_string());
    let note = format!(
        "{LABEL}. Recorded replies from {REPLY_FILE}. Live model calls: 0. Compared with {GATE_FILE}."
    );
    let view = Phase15aView {
        label: LABEL.to_string(),
        note: note.clone(),
        seed: SEED,
        arm: "RECORD".into(),
        sensor_range_m: RANGE_M,
        gate_file: GATE_FILE.into(),
        reply_file: REPLY_FILE.into(),
        live_model_calls: 0,
        link,
        incident_visible_s,
        focus_m: 220.0,
        beats,
        scored,
    };
    let board = DinnerBoard {
        client: LABEL.into(),
        cars: 0,
        jam: "phase15a".into(),
        prefs: LABEL.into(),
        gate_s_m: 1.0,
        home_s_m: 2.0,
        taper_m: 1.0,
        lane_width_m: LANE_WIDTH_M,
        car_length_m: CAR_LENGTH_M,
        car_width_m: CAR_WIDTH_M,
        strips: vec![BoardStrip {
            name: LABEL.into(),
            story: LABEL.into(),
            verdict: "RECORDED".into(),
            score: outcome,
            caption: note,
            scoreboard: false,
            frames: vec![BoardFrame {
                tick: 0,
                gate_blocked: false,
                collisions: 0,
                home: 0,
                cars: 0,
                vehicles: Vec::new(),
                talks: Vec::new(),
            }],
        }],
        dinner_road: DinnerRoad {
            main: vec![[0.0, 0.0], [1.0, 0.0]],
            ramp: vec![[0.0, 1.0], [1.0, 1.0]],
            main_s0: 0.0,
            home: [1.0, 0.0],
        },
        town,
        demo: None,
        reason: None,
        rush: None,
        phase15a: Some(view),
    };
    Ok(ReplayArchive::new(board))
}

fn beats(scored: &Value, edit: &Value) -> Result<Vec<Phase15aBeat>, String> {
    let author = edit["author_car"].as_u64().ok_or("edit author_car")? as u32;
    let since = edit["since_s"].as_f64().ok_or("edit since_s")?;
    let link = edit["link"].as_u64().ok_or("edit link")?;
    let id = edit["id"].as_str().unwrap_or("");
    let blocks = edit["blocks"].as_str().unwrap_or("");
    let evidence = edit["evidence"]["label"].as_str().unwrap_or("");
    let status = edit["status"].as_str().unwrap_or("");
    let since_txt = edit["since_s"].to_string();
    let mut beats = vec![Phase15aBeat {
        kind: "propose".into(),
        at_s: since,
        car: Some(author),
        text: format!(
            "{LABEL} · car {author} proposes road edit {id} ({evidence}, blocks {blocks}) on link {link} at {since_txt} s"
        ),
    }];
    let confirmations = edit["confirmations"]
        .as_array()
        .ok_or("edit confirmations")?;
    if confirmations.is_empty() {
        beats.push(Phase15aBeat {
            kind: "review".into(),
            at_s: since,
            car: None,
            text: format!("{LABEL} · no second car reviewed the edit · edit {status}"),
        });
    }
    for (index, confirmation) in confirmations.iter().enumerate() {
        let car = confirmation["car"].as_u64().ok_or("confirmation car")? as u32;
        let at = confirmation["at_s"].as_f64().ok_or("confirmation at_s")?;
        let saw = confirmation["saw_blockage"]
            .as_bool()
            .ok_or("confirmation saw_blockage")?;
        let at_txt = confirmation["at_s"].to_string();
        let verdict = if saw {
            "confirms the blockage"
        } else {
            "does not see the blockage"
        };
        let closing = if index + 1 == confirmations.len() {
            format!(" · edit {status}")
        } else {
            String::new()
        };
        beats.push(Phase15aBeat {
            kind: "review".into(),
            at_s: at,
            car: Some(car),
            text: format!(
                "{LABEL} · car {car} reviews at {at_txt} s · saw_blockage {saw} · {verdict}{closing}"
            ),
        });
    }
    let gain = scored["affected"]["median_s"].to_string();
    let gain_n = scored["affected"]["n"].to_string();
    let cost = &scored["unaffected_costs"];
    let bar = match scored["affected_median_bar_at_300m"].as_bool() {
        Some(true) => "300 m affected-median bar met",
        Some(false) => "300 m affected-median bar not met",
        None => "300 m affected-median bar not applicable",
    };
    let cost_bar = match scored["unaffected_bar_at_300m"].as_bool() {
        Some(true) => "unaffected cost bar met",
        Some(false) => "unaffected cost bar not met",
        None => "unaffected cost bar not applicable",
    };
    beats.push(Phase15aBeat {
        kind: "outcome".into(),
        at_s: scored["merge_at_s"].as_f64().unwrap_or(since),
        car: None,
        text: format!(
            "{LABEL} · seed {} {} {} m · affected median gain {gain} s (n={gain_n}) · unaffected mean/p95/max loss {}/{}/{} s (n={}) · merge_at_s {} · collisions {} · overlaps {} · leaks {} · true_edit_merged {} · {bar} · {cost_bar}",
            scored["seed"],
            scored["arm"].as_str().unwrap_or(""),
            scored["sensor_range_m"],
            cost["mean_s"],
            cost["p95_s"],
            cost["max_s"],
            cost["n"],
            scored["merge_at_s"],
            scored["collisions"],
            scored["overlaps"],
            scored["leak_violations"],
            scored["true_edit_merged"],
        ),
    });
    Ok(beats)
}

fn format_mismatch(gate: &Value, ours: &Value) -> String {
    let mut lines = vec![format!(
        "phase 15a seed {SEED} replay does not match {GATE_FILE} (RECORD, {RANGE_M} m). Recording not written."
    )];
    let mut keys = BTreeSet::new();
    if let Some(map) = gate.as_object() {
        keys.extend(map.keys().cloned());
    }
    if let Some(map) = ours.as_object() {
        keys.extend(map.keys().cloned());
    }
    for key in keys {
        if key == "per_trip" || key == "record" {
            continue;
        }
        push_diff(&mut lines, &key, &gate[&key], &ours[&key]);
    }
    push_diff(
        &mut lines,
        "record.edits",
        &gate["record"]["edits"],
        &ours["record"]["edits"],
    );
    if let (Some(gate_record), Some(our_record)) =
        (gate["record"].as_object(), ours["record"].as_object())
    {
        let mut record_keys = BTreeSet::new();
        record_keys.extend(gate_record.keys().cloned());
        record_keys.extend(our_record.keys().cloned());
        for key in record_keys {
            if key == "edits" {
                continue;
            }
            push_diff(
                &mut lines,
                &format!("record.{key}"),
                &gate["record"][&key],
                &ours["record"][&key],
            );
        }
    }
    if serde_json::to_string(&gate["per_trip"]).ok()
        != serde_json::to_string(&ours["per_trip"]).ok()
    {
        lines.push("per_trip differs".into());
        if let (Some(gate_trips), Some(our_trips)) =
            (gate["per_trip"].as_array(), ours["per_trip"].as_array())
        {
            for (index, (gate_trip, our_trip)) in gate_trips.iter().zip(our_trips).enumerate() {
                if serde_json::to_string(gate_trip).ok() != serde_json::to_string(our_trip).ok() {
                    lines.push(format!(
                        "first differing per_trip[{index}] gate: {gate_trip}"
                    ));
                    lines.push(format!(
                        "first differing per_trip[{index}] replay: {our_trip}"
                    ));
                    break;
                }
            }
            if gate_trips.len() != our_trips.len() {
                lines.push(format!(
                    "per_trip length gate {} replay {}",
                    gate_trips.len(),
                    our_trips.len()
                ));
            }
        }
    }
    lines.join("\n")
}

fn push_diff(lines: &mut Vec<String>, key: &str, gate: &Value, ours: &Value) {
    if serde_json::to_string(gate).ok() == serde_json::to_string(ours).ok() {
        return;
    }
    lines.push(format!("gate {key}: {gate}"));
    lines.push(format!("replay {key}: {ours}"));
}

fn successors(net: &Network, l: usize) -> Vec<usize> {
    if let Some((_, out)) = net.links[l].via {
        vec![out]
    } else {
        net.moves_from(l).to_vec()
    }
}
fn detour(
    net: &Network,
    edge: usize,
    from: usize,
    sink: usize,
    incoming: Option<usize>,
) -> Option<Vec<usize>> {
    let mut todo: Vec<_> = if let Some(input) = incoming {
        net.moves_from(input)
            .iter()
            .filter(|c| {
                net.links[**c]
                    .via
                    .is_some_and(|(_, out)| net.links[out].edge != edge)
            })
            .copied()
            .collect()
    } else {
        net.links
            .iter()
            .filter(|l| !l.is_connector() && l.from == from && l.edge != edge)
            .map(|l| l.id)
            .collect()
    };
    let mut prev = BTreeMap::new();
    for l in &todo {
        prev.insert(*l, None);
    }
    let mut seen = BTreeSet::new();
    while let Some(l) = todo.pop() {
        if !seen.insert(l) || (!net.links[l].is_connector() && net.links[l].edge == edge) {
            continue;
        }
        if l == sink {
            let mut path = vec![l];
            let mut at = l;
            while let Some(Some(p)) = prev.get(&at) {
                path.push(*p);
                at = *p;
            }
            path.reverse();
            return Some(path);
        }
        for next in successors(net, l) {
            if !prev.contains_key(&next) {
                prev.insert(next, Some(l));
                todo.push(next);
            }
        }
    }
    None
}
fn world() -> Result<(Network, LaneIncident, usize), String> {
    let net = RoadMap::read("maps/sf-zsfg.json")?.network()?;
    let demand = net
        .demand_profile
        .as_ref()
        .ok_or("missing cited corridor demand")?;
    let sink = net
        .links
        .iter()
        .find(|l| !l.is_connector() && l.edge == demand.sink_edge)
        .ok_or("missing sink")?
        .id;
    let selected = demand
        .expected_road_edges
        .iter()
        .enumerate()
        .find_map(|(i, e)| {
            let incoming = i.checked_sub(1).and_then(|k| {
                net.links
                    .iter()
                    .find(|l| !l.is_connector() && l.edge == demand.expected_road_edges[k])
                    .map(|l| l.id)
            });
            net.links.iter().find(|l| {
                !l.is_connector()
                    && l.edge == *e
                    && detour(&net, *e, l.from, sink, incoming).is_some()
            })
        });
    let selected = selected.ok_or("no structurally eligible tree edge")?;
    let incident = LaneIncident::read("scenarios/sf-potrero-fallen-tree.json")?;
    if selected.edge != incident.edge
        || selected.from != incident.from_node
        || selected.to != incident.to_node
    {
        return Err(format!(
            "scenario edge {} is not first structurally eligible edge {} ({}->{})",
            incident.edge, selected.edge, selected.from, selected.to
        ));
    }
    if incident.position_m + incident.length_m > selected.len {
        return Err(format!(
            "footprint exceeds selected road length {}",
            selected.len
        ));
    }
    let spoof = LaneIncident::read("scenarios/sf-potrero-spoof.json")?;
    if (
        spoof.edge,
        spoof.from_node,
        spoof.to_node,
        spoof.position_m,
        spoof.length_m,
        spoof.start_s,
        spoof.duration_s,
    ) != (
        incident.edge,
        incident.from_node,
        incident.to_node,
        incident.position_m,
        incident.length_m,
        incident.start_s,
        incident.duration_s,
    ) {
        return Err("spoof must use the identical footprint and timing".into());
    }
    let link = selected.id;
    Ok((net, incident, link))
}
fn config(arm: Arm, range: f64, p: Option<Proposal>, replies: &Replies) -> RecordConfig {
    RecordConfig {
        arm,
        sensor_range_m: range,
        proposal: p,
        reply: replies.tree.reply.clone(),
        priority_reach: replies.priority.reply.reach.clone(),
    }
}
fn proposal(i: &LaneIncident, link: usize, sam: &Value, spoof: bool) -> Proposal {
    Proposal {
        link,
        position_m: i.position_m,
        length_m: i.length_m,
        start_s: i.start_s,
        duration_s: i.duration_s,
        spoof,
        evidence: Evidence {
            image_sha256: sam["image_sha256"].as_str().unwrap().into(),
            mask_sha256: sam["mask_sha256"].as_str().unwrap().into(),
            label: "SAM-supported reported tree".into(),
        },
    }
}
fn stats(v: &[f64]) -> Value {
    let mut a = v.to_vec();
    a.sort_by(f64::total_cmp);
    json!({"n":a.len(),"mean_s":if a.is_empty(){None}else{Some(a.iter().sum::<f64>()/a.len() as f64)},"median_s":if a.is_empty(){None}else{Some(rush_hour::median(&a))},"p95_s":if a.is_empty(){None}else{Some(a[((a.len() as f64*0.95).ceil() as usize).saturating_sub(1)])},"min_s":a.first(),"max_s":a.last()})
}
fn row(
    seed: u64,
    range: f64,
    name: &str,
    run: &Run,
    s: &record::Snapshot,
    base: &Run,
    bs: &record::Snapshot,
    link: usize,
    start: f64,
    free: f64,
    source: &str,
    spoof: bool,
) -> Value {
    let mut saved = Vec::new();
    let mut costs = Vec::new();
    let mut per = Vec::new();
    let mut total = Vec::new();
    let mut onmap = Vec::new();
    let mut affected_n = 0;
    let mut unaffected_n = 0;
    for t in &run.trips {
        let affected = !spoof
            && base.town.routes[t.route].contains(&link)
            && bs.entered.get(&t.car).is_some_and(|at| *at > start);
        if affected {
            affected_n += 1;
        } else {
            unaffected_n += 1;
        }
        let home = run.home.get(&t.car).copied();
        let entry = s.entered.get(&t.car).copied();
        let gain = base.home.get(&t.car).zip(home).map(|(a, b)| a - b);
        if let Some(g) = gain {
            if affected {
                saved.push(g);
            } else {
                costs.push(-g);
            }
        }
        let delay = home.map(|h| h - t.depart_s - free);
        let mapdelay = home.zip(entry).map(|(h, e)| h - e - free);
        if let Some(v) = delay {
            total.push(v);
        }
        if let Some(v) = mapdelay {
            onmap.push(v);
        }
        let status = if home.is_some() {
            "completed"
        } else if t.depart_s > s.ended_at_s {
            "never_departed"
        } else if entry.is_none() {
            "never_entered"
        } else {
            "on_network"
        };
        per.push(json!({"car":t.car,"affected":affected,"depart_s":t.depart_s,"entered_s":entry,"home_s":home,"baseline_home_s":base.home.get(&t.car),"arrival_gain_s":gain,
            "total_delay_s":delay,"on_map_delay_s":mapdelay,"off_map_wait_s":entry.map(|e|e-t.depart_s),"unfinished_status":status,"final_link":s.final_links.get(&t.car)}));
    }
    let reroutes: Vec<_> = s
        .events
        .iter()
        .filter(|e| e.action == "hazard_reroute")
        .collect();
    let before_sight = reroutes
        .iter()
        .filter(|e| s.first_sight.get(&e.car).is_none_or(|at| e.at_s < *at))
        .map(|e| e.car)
        .collect::<BTreeSet<_>>()
        .len();
    let by_sight = reroutes
        .iter()
        .filter(|e| s.first_sight.get(&e.car).is_some_and(|at| *at <= e.at_s))
        .map(|e| e.car)
        .collect::<BTreeSet<_>>()
        .len();
    let edit = s.edits.first();
    let merge = edit.and_then(|e| e.merged_at);
    let median = if saved.is_empty() {
        None
    } else {
        Some(rush_hour::median(&saved))
    };
    let cost = stats(&costs);
    let complete = run.home.len() == run.trips.len() && base.home.len() == base.trips.len();
    json!({"kind":"score","part":"tree","seed":seed,"sensor_range_m":range,"range_basis":if range==300.0{"Waymo published up to 300 m; generous unoccluded radius"}else{"hypothetical sensitivity"},
        "arm":name,"case":if spoof{"spoof"}else{"tree"},"reply_source":source,"trips":run.trips.len(),"completed":run.home.len(),"all_trips_finished":complete,
        "collisions":run.town.stats.crossing_conflicts,"overlaps":run.town.stats.overlaps,"true_edit_merged":!spoof && edit.is_some_and(|e|e.status==Status::Merged),
        "spoof_merged":spoof && edit.is_some_and(|e|e.status==Status::Merged),"spoof_caused_reroutes":if spoof{reroutes.len()}else{0},"leak_violations":s.leak_violations(),
        "merge_at_s":merge,"time_to_merge_s":merge.zip(edit).map(|(m,e)|m-e.since_s),"rerouted_before_ever_seeing_tree":before_sight,"rerouted_after_sighting":by_sight,
        "discovered_by_sight":s.first_sight.len(),"affected":stats(&saved),"affected_expected":affected_n,"unaffected_costs":cost,"unaffected_expected":unaffected_n,
        "total_delay":stats(&total),"on_map_delay":stats(&onmap),"affected_median_bar_at_300m":if range==300.0 && !spoof{median.map(|m|m>=30.0 && saved.len()==affected_n && complete)}else{None},
        "unaffected_bar_at_300m":if range==300.0 && !spoof{Some(cost["p95_s"].as_f64().is_some_and(|v|v<=30.0) && cost["max_s"].as_f64().is_some_and(|v|v<60.0) && costs.len()==unaffected_n && complete)}else{None},
        "per_trip":per,"record":s})
}
