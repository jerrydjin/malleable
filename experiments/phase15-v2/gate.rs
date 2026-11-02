use malleable::{
    incident::LaneIncident,
    network::Network,
    record::{self, Arm, Evidence, Proposal, RecordConfig, Replies, Snapshot, Status},
    road_map::RoadMap,
    rush_hour::{self, Fcfs, Mock, Trip, Truth, V2Audit, V2Watch},
};
use serde_json::{json, Value};
use std::collections::BTreeMap;
#[allow(dead_code)]
#[path = "phase15_birth.rs"]
mod retained_birth_population;
fn config(arm: Arm, range: f64, p: Option<Proposal>, r: &Replies) -> RecordConfig {
    RecordConfig {
        arm,
        sensor_range_m: range,
        proposal: p,
        reply: r.tree.reply.clone(),
        priority_reach: r.priority.reply.reach.clone(),
    }
}
fn site() -> Result<(Network, LaneIncident, usize), String> {
    let n = RoadMap::read("maps/sf-zsfg.json")?.network()?;
    let i = LaneIncident::read("scenarios/sf-potrero-near-tree-v2.json")?;
    let link = n
        .links
        .iter()
        .find(|l| {
            !l.is_connector() && l.edge == i.edge && l.from == i.from_node && l.to == i.to_node
        })
        .ok_or("missing NEAR tree road")?
        .id;
    let m: Value = serde_json::from_slice(
        &std::fs::read("assets/phase15/v2-near-manifest.json").map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    if i.edge != 15
        || m["near"]["last_turnoff"]["node"] != 55
        || m["near"]["last_turnoff"]["D_m"]
            .as_f64()
            .is_none_or(|d| d > 300.0)
    {
        return Err("NEAR declaration changed".into());
    }
    Ok((n, i, link))
}
fn proposal(i: &LaneIncident, link: usize, spoof: bool) -> Result<Proposal, String> {
    let sam = record::sam_summary()?;
    Ok(Proposal {
        link,
        position_m: i.position_m,
        length_m: i.length_m,
        start_s: i.start_s,
        duration_s: i.duration_s,
        spoof,
        evidence: Evidence {
            image_sha256: sam["image_sha256"].as_str().unwrap().into(),
            mask_sha256: sam["mask_sha256"].as_str().unwrap().into(),
            label: "blocked".into(),
        },
    })
}
fn ordinary(seed: u64, n: &Network) -> Vec<Trip> {
    let mut t = rush_hour::population_on(seed, n);
    for t in &mut t {
        t.truth = Truth::Ordinary;
        t.reason = "I'm driving through the corridor".into();
        t.destination = "other".into();
    }
    t
}
fn watch(i: &LaneIncident, link: usize) -> V2Watch {
    V2Watch {
        hazard: link,
        turnoff_node: 55,
        start_s: i.start_s,
        end_s: i.start_s + i.duration_s,
    }
}
pub fn validity() -> Result<Value, String> {
    let (mut n, i, l) = site()?;
    let t = ordinary(1, &n);
    n.add_incident(i.clone())?;
    let r = Replies::read("docs/gates/phase-15-model-replies.json")?;
    let (near_run, s, a) = rush_hour::simulate_trips_recorded_v2(
        1,
        &Fcfs,
        t,
        &n,
        config(Arm::Record, 300.0, Some(proposal(&i, l, false)?), &r),
        Some(watch(&i, l)),
    )?;
    let w = retained_birth_population::build()?;
    let (t, car) = retained_birth_population::population(1, &w, true);
    let (birth, bs, _) = rush_hour::simulate_trips_recorded_v2(
        1,
        &Mock,
        t,
        &w.net,
        config(Arm::Record, 300.0, None, &r),
        None,
    )?;
    let edits = bs
        .edits
        .iter()
        .filter(|e| e.kind == "priority" && e.author_car == car)
        .count();
    let deliveries = bs
        .deliveries
        .iter()
        .filter(|d| d.edit_id == format!("priority:{car}"))
        .count();
    let reroutes = s
        .events
        .iter()
        .filter(|e| e.action == "hazard_reroute")
        .count();
    let merged = s
        .edits
        .iter()
        .any(|e| e.kind == "hazard" && e.status == Status::Merged);
    Ok(
        json!({"kind":"harness_validity_only","generated_code_sha256":record::sha256(&format!("{}/generated-code.sha256",env!("CARGO_MANIFEST_DIR")))?,"seed":1,"sensor_range_m":300,"true_edit_merged":merged,"hazard_reroutes":reroutes,"route_decision_examples":s.route_decisions.iter().take(3).collect::<Vec<_>>(),"before_turnoff_distinct_cars":a.distinct_before_turnoff_during_incident,"before_turnoff_max_simultaneous_cars":a.max_simultaneous_before_turnoff_during_incident,
        "labour_granted":birth.decisions.iter().any(|d|d.car==car && d.granted),"priority_edits":edits,"priority_deliveries":deliveries,"public_delivered_cars":bs.delivered.len(),"priority_actions":bs.events.len(),"leaks":s.leak_violations(),"safety":near_run.town.stats.overlaps+near_run.town.stats.crossing_conflicts+birth.town.stats.overlaps+birth.town.stats.crossing_conflicts,
        "valid":merged && reroutes>=1 && a.distinct_before_turnoff_during_incident>=20 && a.max_simultaneous_before_turnoff_during_incident>=20 && edits>=1 && deliveries>=1 && s.leak_violations()==0 && near_run.town.stats.overlaps+near_run.town.stats.crossing_conflicts+birth.town.stats.overlaps+birth.town.stats.crossing_conflicts==0}),
    )
}
fn main() -> Result<(), String> {
    let a: BTreeMap<String, String> = std::env::args()
        .skip(1)
        .filter_map(|s| s.split_once('=').map(|(k, v)| (k.into(), v.into())))
        .collect();
    let first = a
        .get("seed")
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(1);
    let end = a
        .get("end")
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(10);
    match a.get("part").map(String::as_str).unwrap_or("validity") {
        "validity" => {
            println!("{}", validity()?);
            Ok(())
        }
        "near" => near(first, end),
        "birth" => birth(first, end),
        _ => Err("part must be validity, near or birth".into()),
    }
}

#[allow(dead_code)]
#[path = "phase15_tree_v1_rows.rs"]
mod retained_tree_rows;
fn freeze() -> Result<(), String> {
    let path = "docs/gates/phase-15-v2-code-freeze.sha256";
    let doc = "docs/phase-15-v2-preregistration.md";
    let text = std::fs::read_to_string(path)
        .map_err(|_| "v2 preregistration and freeze required before scores".to_string())?;
    for f in [path, doc] {
        let s = std::process::Command::new("git")
            .args(["cat-file", "-e", &format!("HEAD:{f}")])
            .status()
            .map_err(|e| e.to_string())?;
        if !s.success() {
            return Err("v2 preregistration must be committed".into());
        }
    }
    let clean = std::process::Command::new("git")
        .args(["diff", "--quiet", "HEAD", "--", path, doc])
        .status()
        .map_err(|e| e.to_string())?;
    if !clean.success() {
        return Err("v2 registration changed".into());
    }
    for l in text
        .lines()
        .filter(|l| !l.is_empty() && !l.starts_with('#'))
    {
        let (hash, f) = l.split_once("  ").ok_or("invalid freeze")?;
        if record::sha256(f)? != hash {
            return Err(format!("frozen v2 input changed: {f}"));
        }
    }
    let generated = "assets/phase15/v2-generated-code.sha256";
    let text = std::fs::read_to_string(generated).map_err(|e| e.to_string())?;
    for l in text.lines() {
        let (hash, f) = l.split_once("  ").ok_or("invalid generated freeze")?;
        let actual = format!("{}/{f}", env!("CARGO_MANIFEST_DIR"));
        if record::sha256(&actual)? != hash {
            return Err(format!("generated code differs: {f}"));
        }
    }
    let v: Value = serde_json::from_slice(
        &std::fs::read("assets/phase15/v2-harness-validity.json").map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    if v["valid"] != true || v["generated_code_sha256"] != record::sha256(generated)? {
        return Err("validity tests must pass for this exact code before registration".into());
    }
    Ok(())
}
fn timeline(mut row: Value, s: &Snapshot, a: &V2Audit) -> Value {
    let merged = s
        .edits
        .iter()
        .find(|e| e.kind == "hazard")
        .and_then(|e| e.merged_at);
    let mut before = 0;
    let mut after = 0;
    let mut no_pass = 0;
    let cars:Vec<_>=a.cars.iter().map(|(id,e)| {
        if e.original_route_has_blocked_edge {match (merged,e.passed_last_turnoff_s) {(_,None)=>no_pass+=1,(Some(m),Some(p)) if p<m=>before+=1,(Some(_),Some(_))=>after+=1,_=>()}}
        json!({"car":id,"original_route_has_blocked_edge":e.original_route_has_blocked_edge,"actual_entry_s":e.on_map_entry_s,"first_on_map_with_blocked_edge_s":e.first_on_map_with_blocked_edge_s,
            "first_before_turnoff_during_incident_s":e.first_before_turnoff_during_incident_s,"last_before_turnoff_during_incident_s":e.last_before_turnoff_during_incident_s,
            "passed_last_turnoff_s":e.passed_last_turnoff_s,"edit_merged_at_s":merged,"merge_minus_pass_s":merged.zip(e.passed_last_turnoff_s).map(|(m,p)|m-p)})
    }).collect();
    row["version"] = json!(2);
    row["part"] = json!("near");
    row["case"] = json!(if row["case"] == "spoof" {
        "spoof"
    } else {
        "near"
    });
    row["cars_with_blocked_edge_on_original_route"] = json!(a
        .cars
        .values()
        .filter(|e| e.original_route_has_blocked_edge)
        .count());
    row["cars_observed_on_map_with_blocked_edge_remaining"] = json!(a
        .cars
        .values()
        .filter(|e| e.first_on_map_with_blocked_edge_s.is_some())
        .count());
    row["affected_before_turnoff_distinct_cars"] = json!(a.distinct_before_turnoff_during_incident);
    row["affected_before_turnoff_max_simultaneous_cars"] =
        json!(a.max_simultaneous_before_turnoff_during_incident);
    row["cars_passed_turnoff_before_merge"] = json!(before);
    row["cars_passed_turnoff_at_or_after_merge"] = json!(after);
    row["cars_never_passed_turnoff"] = json!(no_pass);
    row["last_turnoff_node"] = json!(55);
    row["D_m"] = json!(85.1188329873662);
    row["turnoff_timeline"] = json!(cars);
    let range = row["sensor_range_m"].as_f64().unwrap();
    let control = row["affected"]["median_s"].as_f64().map(|g| {
        g.abs() < 10.0
            && row["all_trips_finished"] == true
            && row["affected"]["n"] == row["affected_expected"]
    });
    row.as_object_mut()
        .unwrap()
        .remove("affected_median_bar_at_300m");
    row["near_control_bar_at_300m"] = json!(if range == 300.0 && row["case"] != "spoof" {
        control
    } else {
        None
    });
    row
}
fn near(first: u64, end: u64) -> Result<(), String> {
    freeze()?;
    let (plain, i, l) = site()?;
    let r = Replies::read("docs/gates/phase-15-model-replies.json")?;
    let mut n = plain.clone();
    n.add_incident(i.clone())?;
    let mut rows = Vec::new();
    for seed in first..=end {
        let t = ordinary(seed, &plain);
        let mut solo = t[0].clone();
        solo.depart_s = 0.0;
        solo.request_s = 0.0;
        let (f, _, _) = rush_hour::simulate_trips_recorded_v2(
            seed,
            &Fcfs,
            vec![solo.clone()],
            &plain,
            config(Arm::SensorOnly, 300.0, None, &r),
            None,
        )?;
        let free = f.home[&solo.car];
        for range in [60.0, 150.0, 300.0] {
            let (base, bs, ba) = rush_hour::simulate_trips_recorded_v2(
                seed,
                &Fcfs,
                t.clone(),
                &n,
                config(Arm::SensorOnly, range, Some(proposal(&i, l, false)?), &r),
                Some(watch(&i, l)),
            )?;
            let v = retained_tree_rows::v2_row(
                seed,
                range,
                "SENSOR_ONLY",
                &base,
                &bs,
                &base,
                &bs,
                l,
                i.start_s,
                free,
                &r.tree.source,
                false,
            );
            rows.push(timeline(v, &bs, &ba));
            for (name, arm) in [("RECORD", Arm::Record), ("RECORD_CITY", Arm::RecordCity)] {
                let (run, s, a) = rush_hour::simulate_trips_recorded_v2(
                    seed,
                    &Fcfs,
                    t.clone(),
                    &n,
                    config(arm, range, Some(proposal(&i, l, false)?), &r),
                    Some(watch(&i, l)),
                )?;
                let v = retained_tree_rows::v2_row(
                    seed,
                    range,
                    name,
                    &run,
                    &s,
                    &base,
                    &bs,
                    l,
                    i.start_s,
                    free,
                    &r.tree.source,
                    false,
                );
                rows.push(timeline(v, &s, &a));
            }
            let (pb, ps, _) = rush_hour::simulate_trips_recorded_v2(
                seed,
                &Fcfs,
                t.clone(),
                &plain,
                config(Arm::SensorOnly, range, None, &r),
                None,
            )?;
            let (run, s, a) = rush_hour::simulate_trips_recorded_v2(
                seed,
                &Fcfs,
                t.clone(),
                &plain,
                config(Arm::Record, range, Some(proposal(&i, l, true)?), &r),
                Some(watch(&i, l)),
            )?;
            let v = retained_tree_rows::v2_row(
                seed,
                range,
                "SPOOF",
                &run,
                &s,
                &pb,
                &ps,
                l,
                i.start_s,
                free,
                &r.tree.source,
                true,
            );
            rows.push(timeline(v, &s, &a));
        }
        eprintln!("v2 NEAR seed {seed} complete, all ranges retained");
    }
    let safety = rows
        .iter()
        .all(|r| r["collisions"] == 0 && r["overlaps"] == 0);
    let true_merges = rows
        .iter()
        .filter(|r| r["case"] == "near")
        .all(|r| r["true_edit_merged"] == true);
    let spoof = rows
        .iter()
        .filter(|r| r["case"] == "spoof")
        .all(|r| r["spoof_merged"] == false && r["spoof_caused_reroutes"] == 0);
    let leaks = rows.iter().all(|r| r["leak_violations"] == 0);
    let wins = rows
        .iter()
        .filter(|r| {
            r["arm"] == "RECORD"
                && r["sensor_range_m"] == 300.0
                && r["near_control_bar_at_300m"] == true
        })
        .count();
    let cost = rows
        .iter()
        .filter(|r| r["arm"] == "RECORD" && r["sensor_range_m"] == 300.0)
        .all(|r| r["unaffected_bar_at_300m"] == true);
    let coverage = rows.iter().filter(|r| r["arm"] == "RECORD").all(|r| {
        r["affected_before_turnoff_distinct_cars"]
            .as_u64()
            .is_some_and(|n| n >= 20)
    });
    let complete = rows.iter().all(|r| r["all_trips_finished"] == true);
    for r in rows {
        println!("{r}");
    }
    println!(
        "{}",
        json!({"version":2,"kind":"gate","part":"near","claim_sensor_range_m":300,"seeds":[first,end],"safety":safety,"true_merges":true_merges,"spoof_rejected":spoof,"no_leaks":leaks,"coverage_valid":coverage,"control_holding_seeds_300m":wins,"others_cost_bar_300m":cost,"all_trips_finished":complete,"pass":first==1 && end==10 && safety && true_merges && spoof && leaks && wins>=8 && cost})
    );
    Ok(())
}
fn birth_row(mut v: Value, s: &Snapshot) -> Value {
    v["version"] = json!(2);
    let probe = v["probe_car"].as_u64().unwrap() as u32;
    let edits = s
        .edits
        .iter()
        .filter(|e| e.kind == "priority" && e.author_car == probe)
        .count();
    let deliveries = s
        .deliveries
        .iter()
        .filter(|d| d.edit_id == format!("priority:{probe}"))
        .count();
    let causal = s.events.iter().all(|e| {
        e.beneficiary.is_none_or(|b| {
            s.deliveries
                .iter()
                .any(|d| d.car == e.car && d.edit_id == format!("priority:{b}") && d.at_s <= e.at_s)
        })
    });
    v["priority_edits"] = json!(edits);
    v["priority_deliveries"] = json!(deliveries);
    v["accepted_actions"] = json!(s.events.len());
    v["actions_have_due_delivery"] = json!(if v["arm"] == "RECORD" {
        Some(causal)
    } else {
        None
    });
    v
}
fn birth(first: u64, end: u64) -> Result<(), String> {
    freeze()?;
    let w = retained_birth_population::build()?;
    let r = Replies::read("docs/gates/phase-15-model-replies.json")?;
    let mut rows = Vec::new();
    for seed in first..=end {
        for labour in [true, false] {
            let case = if labour { "labour" } else { "gym" };
            let (t, probe) = retained_birth_population::population(seed, &w, labour);
            for range in [60.0, 150.0, 300.0] {
                let (base, bs, _) = rush_hour::simulate_trips_recorded_v2(
                    seed,
                    &Mock,
                    t.clone(),
                    &w.net,
                    config(Arm::SensorOnly, range, None, &r),
                    None,
                )?;
                rows.push(birth_row(
                    retained_birth_population::v2_row(
                        seed,
                        range,
                        case,
                        "SENSOR_ONLY",
                        probe,
                        &base,
                        &bs,
                        &base,
                        &r,
                    ),
                    &bs,
                ));
                let (run, s, _) = rush_hour::simulate_trips_recorded_v2(
                    seed,
                    &Mock,
                    t.clone(),
                    &w.net,
                    config(Arm::Record, range, None, &r),
                    None,
                )?;
                rows.push(birth_row(
                    retained_birth_population::v2_row(
                        seed, range, case, "RECORD", probe, &run, &s, &base, &r,
                    ),
                    &s,
                ));
            }
        }
        eprintln!("v2 birth seed {seed} complete, both twins/all ranges retained");
    }
    let safety = rows
        .iter()
        .all(|r| r["collisions"] == 0 && r["overlaps"] == 0);
    let granted = rows
        .iter()
        .filter(|r| r["case"] == "labour")
        .all(|r| r["granted"] == true);
    let gym = rows.iter().filter(|r| r["case"] == "gym").all(|r| {
        r["granted"] == false
            && r["gym_zero_gain_and_costs"] == true
            && r["priority_edits"] == 0
            && r["priority_deliveries"] == 0
    });
    let wins = rows
        .iter()
        .filter(|r| {
            r["arm"] == "RECORD"
                && r["case"] == "labour"
                && r["sensor_range_m"] == 300.0
                && r["arrival_gain_s"].as_f64().is_some_and(|v| v > 0.0)
        })
        .count();
    let cost = rows
        .iter()
        .filter(|r| r["arm"] == "RECORD" && r["sensor_range_m"] == 300.0)
        .all(|r| r["others_bar_at_300m"] == true);
    let validity = rows
        .iter()
        .filter(|r| r["case"] == "labour" && r["arm"] == "RECORD")
        .all(|r| {
            r["priority_edits"].as_u64().is_some_and(|n| n >= 1)
                && r["priority_deliveries"].as_u64().is_some_and(|n| n >= 1)
                && r["actions_have_due_delivery"] == true
        });
    let complete = rows.iter().all(|r| r["all_trips_finished"] == true);
    for r in rows {
        println!("{r}");
    }
    println!(
        "{}",
        json!({"version":2,"kind":"gate","part":"birth","claim_sensor_range_m":300,"seeds":[first,end],"safety":safety,"labour_granted":granted,"gym_denied_zero_gain_cost":gym,"priority_wiring_valid":validity,"winning_seeds_300m":wins,"others_cost_bar_300m":cost,"all_trips_finished":complete,"pass":first==1 && end==10 && safety && granted && gym && wins>=8 && cost})
    );
    Ok(())
}
