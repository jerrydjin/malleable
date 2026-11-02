use malleable::{
    network::Network,
    record::{self, Arm, RecordConfig, Replies, Snapshot},
    rush_hour::{self, LabourApproachTrace, Mock, Run, Trip},
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::BTreeSet;
#[allow(dead_code)]
#[path = "phase15_birth.rs"]
pub mod retained;
const BASE: &str = "e4ba2a6e9555f99baec8dfaf1ea9c5a6a7766b50";
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Candidate {
    pub incoming: usize,
    pub edge: usize,
    pub from: usize,
    pub junction: usize,
    pub name: String,
    pub connector: usize,
    pub route: Vec<usize>,
}
pub fn candidates(w: &retained::World) -> Result<Vec<Candidate>, String> {
    let mut result = Vec::new();
    for f in &w.flows {
        let at = w
            .corridor
            .iter()
            .position(|l| *l == f[2])
            .ok_or("crossing flow does not join corridor")?;
        let mut route = vec![f[0], f[1]];
        route.extend_from_slice(&w.corridor[at..]);
        let l = &w.net.links[f[0]];
        if w.net.links[*route.last().unwrap()].to != 4 {
            return Err("candidate does not reach hospital node 4".into());
        }
        if !w.net.moves_from(f[0]).contains(&f[1]) || w.net.links[f[1]].via != Some((f[0], f[2])) {
            return Err("illegal joining connector".into());
        }
        result.push(Candidate {
            incoming: f[0],
            edge: l.edge,
            from: l.from,
            junction: l.to,
            name: format!("edge {}: node {} to node {}", l.edge, l.from, l.to),
            connector: f[1],
            route,
        });
    }
    result.sort_by_key(|c| c.incoming);
    result.dedup_by_key(|c| c.incoming);
    Ok(result)
}
fn config(arm: Arm, range: f64, r: &Replies) -> RecordConfig {
    RecordConfig {
        arm,
        sensor_range_m: range,
        proposal: None,
        reply: r.tree.reply.clone(),
        priority_reach: r.priority.reply.reach.clone(),
    }
}
pub fn population(
    seed: u64,
    w: &retained::World,
    c: &Candidate,
    labour: bool,
) -> Result<(Network, Vec<Trip>, u32), String> {
    // Generate all old route IDs first: adding an explicit source/sink could reorder them.
    let (mut trips, probe) = retained::population(seed, w, labour);
    let old = w.net.routes();
    let mut n = w.net.clone();
    n.register_experiment_route(c.route.clone())?;
    let routes = n.routes();
    for t in &mut trips {
        let p = if t.car == probe {
            &c.route
        } else {
            &old[t.route].2.links
        };
        t.route = routes
            .iter()
            .position(|(_, _, r)| r.links == *p)
            .ok_or("route lost during registration")?;
        if t.car == probe {
            t.destination = "hospital".into();
        }
    }
    Ok((n, trips, probe))
}
fn run(
    seed: u64,
    w: &retained::World,
    c: &Candidate,
    labour: bool,
    arm: Arm,
    range: f64,
    r: &Replies,
    solo: bool,
) -> Result<(Run, Snapshot, LabourApproachTrace, u32), String> {
    let (n, mut t, p) = population(seed, w, c, labour)?;
    if solo {
        t.retain(|t| t.car == p);
    }
    let (run, s, a) = rush_hour::simulate_trips_phase15c(
        seed,
        &Mock,
        t,
        &n,
        config(arm, range, r),
        p,
        c.incoming,
    )?;
    Ok((run, s, a, p))
}
fn stats(v: &[f64]) -> Value {
    let mut v = v.to_vec();
    v.sort_by(f64::total_cmp);
    json!({"n":v.len(),"mean_s":if v.is_empty(){None}else{Some(v.iter().sum::<f64>()/v.len() as f64)},"median_s":if v.is_empty(){None}else{Some(rush_hour::median(&v))},"total_s":v.iter().sum::<f64>(),"min_s":v.first(),"max_s":v.last(),"p95_s":if v.is_empty(){None}else{Some(v[((v.len() as f64*0.95).ceil() as usize).saturating_sub(1)])}})
}
fn source_hash() -> Result<String, String> {
    record::sha256(&format!(
        "{}/phase15c-generated-code.sha256",
        env!("CARGO_MANIFEST_DIR")
    ))
}
fn diagnostic(seed: u64, w: &retained::World, c: &Candidate, r: &Replies) -> Result<Value, String> {
    let (base, s, a, p) = run(seed, w, c, true, Arm::SensorOnly, 300., r, false)?;
    let (solo, ss, sa, _) = run(seed, w, c, true, Arm::SensorOnly, 300., r, true)?;
    let trip = base.trips.iter().find(|t| t.car == p).unwrap();
    let off = s.entered.get(&p).map(|e| e - trip.depart_s);
    let map = base.home.get(&p).zip(s.entered.get(&p)).map(|(h, e)| h - e);
    let free = solo
        .home
        .get(&p)
        .zip(ss.entered.get(&p))
        .map(|(h, e)| h - e);
    let excess = map.zip(free).map(|(m, f)| m - f);
    let approach = a.dwell_s().zip(sa.dwell_s()).map(|(d, f)| d - f);
    let majority = off.zip(excess).and_then(|(o, m)| {
        if o + m.max(0.) > 0. {
            Some(o / (o + m.max(0.)))
        } else {
            None
        }
    });
    Ok(
        json!({"seed":seed,"probe_car":p,"depart_s":trip.depart_s,"request_s":trip.request_s,"sensor_range_m":300,"arm":"SENSOR_ONLY","granted":base.decisions.iter().find(|d|d.car==p).map(|d|d.granted),"approach_trace":a,"solo_approach_trace":sa,"approach_excess_s":approach,"on_map_trip_s":map,"solo_on_map_trip_s":free,"on_map_excess_s":excess,"off_map_wait_s":off,"off_map_delay_fraction":majority,"approach_at_least_30s":approach.is_some_and(|d|d>=30.),"completed":base.home.len(),"trips":base.trips.len(),"all_trips_finished":base.home.len()==base.trips.len(),"collisions":base.town.stats.crossing_conflicts,"overlaps":base.town.stats.overlaps,"priority_edits":s.edits.len(),"priority_deliveries":s.deliveries.len(),"accepted_local_actions":s.events.len()}),
    )
}
fn diagnostics(w: &retained::World, c: &Candidate, r: &Replies) -> Result<Value, String> {
    let mut rows = Vec::new();
    for seed in 1..=10 {
        rows.push(diagnostic(seed, w, c, r)?);
    }
    let approaches: Vec<_> = rows
        .iter()
        .filter_map(|x| x["approach_excess_s"].as_f64())
        .collect();
    let on: Vec<_> = rows
        .iter()
        .filter_map(|x| x["on_map_excess_s"].as_f64())
        .collect();
    let off: Vec<_> = rows
        .iter()
        .filter_map(|x| x["off_map_wait_s"].as_f64())
        .collect();
    let successes = rows
        .iter()
        .filter(|x| x["approach_at_least_30s"] == true)
        .count();
    let sum_on = on.iter().map(|x| x.max(0.)).sum::<f64>();
    let sum_off = off.iter().sum::<f64>();
    let most_off = sum_off > sum_on;
    let complete = rows.iter().all(|r| r["all_trips_finished"] == true)
        && approaches.len() == 10
        && on.len() == 10
        && off.len() == 10;
    Ok(
        json!({"candidate":c,"seeds":rows,"approach_excess":stats(&approaches),"on_map_excess":stats(&on),"off_map_wait":stats(&off),"seeds_approach_at_least_30s":successes,"most_delay_off_map":most_off,"pooled_off_map_delay_fraction":if sum_on+sum_off>0. {Some(sum_off/(sum_on+sum_off))}else{None},"complete":complete,"valid":complete && successes>=8 && !most_off}),
    )
}
fn committed_code() -> Result<(), String> {
    let path = "experiments/phase15c/gate.rs";
    let ok = std::process::Command::new("git")
        .args([
            "diff",
            "--quiet",
            "HEAD",
            "--",
            "experiments/phase15c",
            "scripts/phase15c.sh",
        ])
        .status()
        .map_err(|e| e.to_string())?;
    let tracked = std::process::Command::new("git")
        .args(["cat-file", "-e", &format!("HEAD:{path}")])
        .status()
        .map_err(|e| e.to_string())?;
    if !ok.success() || !tracked.success() {
        return Err("commit the 15c code and origin rule before diagnostics".into());
    }
    Ok(())
}
fn origins() -> Result<Value, String> {
    committed_code()?;
    let w = retained::build()?;
    let replies = Replies::read("docs/gates/phase-15-model-replies.json")?;
    let mut evaluated = Vec::new();
    for c in candidates(&w)? {
        let v = diagnostics(&w, &c, &replies)?;
        eprintln!(
            "15c candidate {} complete: SENSOR_ONLY diagnostics, all ten seeds",
            c.incoming
        );
        evaluated.push(v);
    }
    let selected = evaluated
        .iter()
        .filter(|v| {
            v["complete"] == true
                && v["approach_excess"]["median_s"]
                    .as_f64()
                    .is_some_and(|m| m > 0.)
        })
        .max_by(|a, b| {
            a["approach_excess"]["median_s"]
                .as_f64()
                .unwrap()
                .total_cmp(&b["approach_excess"]["median_s"].as_f64().unwrap())
                .then(
                    b["candidate"]["incoming"]
                        .as_u64()
                        .cmp(&a["candidate"]["incoming"].as_u64()),
                )
        });
    Ok(
        json!({"kind":"origin_selection_baseline_diagnostics_only","base_commit":BASE,"generated_code_sha256":source_hash()?,"origin_rule":"experiments/phase15c/README.md","candidates":evaluated,"selected":selected.map(|v|&v["candidate"]),"selected_valid":selected.map(|v|&v["valid"])}),
    )
}
fn selected() -> Result<Candidate, String> {
    let v: Value = serde_json::from_slice(
        &std::fs::read("assets/phase15c/origin-manifest.json").map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    if v["generated_code_sha256"] != source_hash()? {
        return Err("origin manifest code differs".into());
    }
    serde_json::from_value(v["selected"].clone())
        .map_err(|e| format!("no eligible on-map approach: {e}"))
}
fn validity() -> Result<Value, String> {
    committed_code()?;
    let manifest: Value = serde_json::from_slice(
        &std::fs::read("assets/phase15c/origin-manifest.json").map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    if manifest["selected"].is_null() {
        return Ok(
            json!({"kind":"harness_validity_only","valid":false,"decision":"STOP",
            "reason":"No candidate has a complete positive median on-map approach excess",
            "generated_code_sha256":source_hash()?}),
        );
    }
    let w = retained::build()?;
    let c = selected()?;
    let r = Replies::read("docs/gates/phase-15-model-replies.json")?;
    let mut v = diagnostics(&w, &c, &r)?;
    v["kind"] = json!("harness_validity_only");
    v["generated_code_sha256"] = json!(source_hash()?);
    v["decision"] = json!(if v["valid"] == true {
        "CONTINUE_TO_PREREGISTRATION"
    } else {
        "STOP"
    });
    Ok(v)
}
fn freeze() -> Result<(), String> {
    let path = "docs/gates/phase-15c-code-freeze.sha256";
    let doc = "docs/phase-15c-preregistration.md";
    for f in [path, doc, "assets/phase15c/validity.json"] {
        if !std::process::Command::new("git")
            .args(["cat-file", "-e", &format!("HEAD:{f}")])
            .status()
            .map_err(|e| e.to_string())?
            .success()
        {
            return Err(
                "committed passing validity and preregistration required before scoring".into(),
            );
        }
        if !std::process::Command::new("git")
            .args(["diff", "--quiet", "HEAD", "--", f])
            .status()
            .map_err(|e| e.to_string())?
            .success()
        {
            return Err("registration/validity changed".into());
        }
    }
    let v: Value = serde_json::from_slice(
        &std::fs::read("assets/phase15c/validity.json").map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    if v["valid"] != true || v["generated_code_sha256"] != source_hash()? {
        return Err("validity STOP or code changed: scoring forbidden".into());
    }
    for line in std::fs::read_to_string(path)
        .map_err(|e| e.to_string())?
        .lines()
        .filter(|l| !l.is_empty() && !l.starts_with('#'))
    {
        let (hash, f) = line.split_once("  ").ok_or("bad freeze")?;
        if record::sha256(f)? != hash {
            return Err(format!("frozen file changed: {f}"));
        }
    }
    for line in std::fs::read_to_string("assets/phase15c/generated-code.sha256")
        .map_err(|e| e.to_string())?
        .lines()
    {
        let (hash, f) = line.split_once("  ").ok_or("bad generated freeze")?;
        if record::sha256(&format!("{}/{f}", env!("CARGO_MANIFEST_DIR")))? != hash {
            return Err(format!("generated code changed: {f}"));
        }
    }
    Ok(())
}
fn row(
    seed: u64,
    range: f64,
    case: &str,
    name: &str,
    r: &Run,
    s: &Snapshot,
    a: &LabourApproachTrace,
    b: &Run,
    bs: &Snapshot,
    p: u32,
    solo: f64,
) -> Value {
    let holders: BTreeSet<_> = s
        .events
        .iter()
        .filter(|e| e.action == "hold" && e.beneficiary == Some(p))
        .map(|e| e.car)
        .collect();
    let mut held = Vec::new();
    let mut others = Vec::new();
    let mut nonholding = Vec::new();
    let mut trips = Vec::new();
    for t in &r.trips {
        let home = r.home.get(&t.car).copied();
        let entry = s.entered.get(&t.car).copied();
        let loss = home.zip(b.home.get(&t.car)).map(|(h, b)| h - b);
        if t.car != p {
            if let Some(loss) = loss {
                others.push(loss);
                if holders.contains(&t.car) {
                    held.push(loss);
                } else {
                    nonholding.push(loss);
                }
            }
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
        trips.push(json!({"car":t.car,"depart_s":t.depart_s,"entry_s":entry,"home_s":home,"baseline_entry_s":bs.entered.get(&t.car),"baseline_home_s":b.home.get(&t.car),"extra_delay_s":loss,"off_map_wait_s":entry.map(|e|e-t.depart_s),"on_map_trip_s":home.zip(entry).map(|(h,e)|h-e),"unfinished_status":status,"final_link":s.final_links.get(&t.car),"held_for_claimant":holders.contains(&t.car)}));
    }
    let gain = b.home.get(&p).zip(r.home.get(&p)).map(|(b, r)| b - r);
    let granted = r.decisions.iter().find(|d| d.car == p).map(|d| d.granted);
    let claimant = r.trips.iter().find(|t| t.car == p).unwrap();
    let off = s.entered.get(&p).map(|e| e - claimant.depart_s);
    let map = r.home.get(&p).zip(s.entered.get(&p)).map(|(h, e)| h - e);
    let complete = r.home.len() == r.trips.len() && b.home.len() == b.trips.len();
    let causal = s.events.iter().all(|e| {
        e.beneficiary.is_none_or(|beneficiary| {
            s.deliveries.iter().any(|d| {
                d.car == e.car && d.edit_id == format!("priority:{beneficiary}") && d.at_s <= e.at_s
            })
        })
    });
    let gym = case == "gym"
        && granted == Some(false)
        && gain == Some(0.)
        && others.iter().all(|x| *x == 0.)
        && complete
        && s.edits.is_empty()
        && s.deliveries.is_empty()
        && s.events.is_empty();
    json!({"kind":"score","part":"phase15c","seed":seed,"sensor_range_m":range,"arm":name,"case":case,"probe_car":p,"granted":granted,"grant_source":"mock","reach_source":"model recording","arrival_gain_s":gain,"claimant_on_map_trip_s":map,"claimant_on_map_excess_s":map.map(|m|m-solo),"claimant_off_map_wait_s":off,"claimant_approach":a,"holding_cars":holders,"holding_car_count":holders.len(),"holders_extra_delay":stats(&held),"others_extra_delay":stats(&others),"nonholding_extra_delay":stats(&nonholding),"others_expected":r.trips.len()-1,"all_trips_finished":complete,"trips":r.trips.len(),"completed":r.home.len(),"collisions":r.town.stats.crossing_conflicts,"overlaps":r.town.stats.overlaps,"priority_edits":s.edits.len(),"priority_deliveries":s.deliveries.len(),"accepted_actions":s.events.len(),"actions_have_due_delivery":if name=="RECORD"{Some(causal)}else{None},"gym_zero":if case=="gym"{Some(gym)}else{None},"per_trip":trips,"record":s})
}
fn score() -> Result<(), String> {
    freeze()?;
    let w = retained::build()?;
    let c = selected()?;
    let replies = Replies::read("docs/gates/phase-15-model-replies.json")?;
    let mut rows = Vec::new();
    for seed in 1..=10 {
        for labour in [true, false] {
            for range in [60., 150., 300.] {
                let (solo, ss, _, p) =
                    run(seed, &w, &c, labour, Arm::SensorOnly, range, &replies, true)?;
                let free = solo
                    .home
                    .get(&p)
                    .zip(ss.entered.get(&p))
                    .map(|(h, e)| h - e)
                    .ok_or("solo incomplete")?;
                let (b, bs, ba, _) = run(
                    seed,
                    &w,
                    &c,
                    labour,
                    Arm::SensorOnly,
                    range,
                    &replies,
                    false,
                )?;
                let (r, s, a, _) = run(seed, &w, &c, labour, Arm::Record, range, &replies, false)?;
                let case = if labour { "labour" } else { "gym" };
                rows.push(row(
                    seed,
                    range,
                    case,
                    "SENSOR_ONLY",
                    &b,
                    &bs,
                    &ba,
                    &b,
                    &bs,
                    p,
                    free,
                ));
                rows.push(row(
                    seed, range, case, "RECORD", &r, &s, &a, &b, &bs, p, free,
                ));
            }
        }
        eprintln!("15c score seed {seed} complete: both twins/all ranges");
    }
    let claim: Vec<_> = rows
        .iter()
        .filter(|x| x["arm"] == "RECORD" && x["case"] == "labour" && x["sensor_range_m"] == 300.)
        .collect();
    let wins = claim
        .iter()
        .filter(|x| x["arrival_gain_s"].as_f64().is_some_and(|g| g >= 15.))
        .count();
    let held = claim.iter().all(|x| {
        x["holders_extra_delay"]["median_s"]
            .as_f64()
            .is_some_and(|m| m <= 10.)
            && x["holders_extra_delay"]["n"] == x["holding_car_count"]
    });
    let others = claim.iter().all(|x| {
        x["others_extra_delay"]["p95_s"]
            .as_f64()
            .is_some_and(|m| m <= 30.)
            && x["others_extra_delay"]["max_s"]
                .as_f64()
                .is_some_and(|m| m < 60.)
            && x["others_extra_delay"]["n"] == x["others_expected"]
    });
    let safe = rows
        .iter()
        .all(|x| x["collisions"] == 0 && x["overlaps"] == 0);
    let complete = rows.iter().all(|x| x["all_trips_finished"] == true);
    let gym = rows
        .iter()
        .filter(|x| x["case"] == "gym")
        .all(|x| x["gym_zero"] == true);
    let causal = rows
        .iter()
        .filter(|x| x["arm"] == "RECORD")
        .all(|x| x["actions_have_due_delivery"] == true);
    for row in rows {
        println!("{row}");
    }
    println!(
        "{}",
        json!({"kind":"gate","part":"phase15c","winning_seeds_300m":wins,"holders_cost_bar_300m":held,"others_cost_bar_300m":others,"safety":safe,"all_trips_finished":complete,"gym_zero":gym,"actions_have_due_delivery":causal,"pass":wins>=7 && held && others && safe && complete && gym && causal})
    );
    Ok(())
}
fn main() -> Result<(), String> {
    let part = std::env::args()
        .skip(1)
        .find_map(|a| a.strip_prefix("part=").map(str::to_string))
        .unwrap_or("validity".into());
    match part.as_str() {
        "origins" => println!("{}", origins()?),
        "validity" => println!("{}", validity()?),
        "score" => score()?,
        _ => return Err("part=origins, validity or score".into()),
    }
    Ok(())
}
