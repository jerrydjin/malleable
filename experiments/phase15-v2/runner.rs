/// V2-only observer. This file is included in the generated crate, never v1.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct V2Watch {
    pub hazard: usize,
    pub turnoff_node: usize,
    pub start_s: f64,
    pub end_s: f64,
}
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct V2Exposure {
    pub original_route_has_blocked_edge: bool,
    pub on_map_entry_s: Option<f64>,
    pub first_on_map_with_blocked_edge_s: Option<f64>,
    pub first_before_turnoff_during_incident_s: Option<f64>,
    pub last_before_turnoff_during_incident_s: Option<f64>,
    pub passed_last_turnoff_s: Option<f64>,
}
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct V2Audit {
    pub cars: BTreeMap<u32, V2Exposure>,
    pub distinct_before_turnoff_during_incident: usize,
    pub max_simultaneous_before_turnoff_during_incident: usize,
}
pub fn simulate_trips_recorded_v2(
    seed: u64,
    policy: &dyn Policy,
    mut trips: Vec<Trip>,
    net: &Network,
    config: crate::record::RecordConfig,
    watch: Option<V2Watch>,
) -> Result<(Run, crate::record::Snapshot, V2Audit), String> {
    trips.sort_by(|a, b| a.request_s.total_cmp(&b.request_s).then(a.car.cmp(&b.car)));
    let schedule: Vec<_> = trips
        .iter()
        .map(|t| ScheduledCar {
            id: t.car,
            route: t.route,
            depart_s: t.depart_s,
        })
        .collect();
    let mut sim = TownSim::with_schedule_on(seed, &schedule, net.clone())?;
    sim.enable_record(config)?;
    let mut audit = V2Audit::default();
    if let Some(w) = &watch {
        let original = net.routes();
        for t in &trips {
            audit.cars.insert(
                t.car,
                V2Exposure {
                    original_route_has_blocked_edge: original[t.route].2.links.contains(&w.hazard),
                    ..Default::default()
                },
            );
        }
    }
    let requests: Vec<_> = trips
        .iter()
        .map(|t| PolicyRequest {
            car: t.car,
            rider: t.rider,
            reason: t.reason.clone(),
            at_s: t.request_s,
            history: Vec::new(),
        })
        .collect();
    policy.prepare(&requests);
    let mut cursor = 0;
    let mut decisions = Vec::new();
    let mut stats = NetStats::default();
    for step in 0..=10_000 {
        let first = cursor;
        while cursor < trips.len() && trips[cursor].request_s <= sim.time() {
            cursor += 1;
        }
        if cursor > first {
            let batch = policy.decide_batch(&requests[first..cursor]);
            if batch.len() != cursor - first
                || batch
                    .iter()
                    .zip(&requests[first..cursor])
                    .any(|(d, r)| d.car != r.car)
            {
                return Err("v2 policy identities mismatch".into());
            }
            for d in batch {
                sim.set_precedence(d.car, d.granted);
                decisions.push(d);
            }
        }
        if let Some(w) = &watch {
            let mut simultaneous = 0;
            for (car, on_route, before, passed) in
                sim.record_node_observations(w.hazard, w.turnoff_node)
            {
                let e = audit.cars.get_mut(&car).unwrap();
                e.on_map_entry_s
                    .get_or_insert((sim.time() - crate::network::NET_DT_S).max(0.0));
                if on_route {
                    e.first_on_map_with_blocked_edge_s.get_or_insert(sim.time());
                }
                if on_route
                    && before
                    && e.on_map_entry_s.is_some_and(|at| at > w.start_s)
                    && w.start_s <= sim.time()
                    && sim.time() < w.end_s
                {
                    e.first_before_turnoff_during_incident_s
                        .get_or_insert(sim.time());
                    e.last_before_turnoff_during_incident_s = Some(sim.time());
                    simultaneous += 1;
                }
                if passed {
                    e.passed_last_turnoff_s.get_or_insert(sim.time());
                }
            }
            audit.max_simultaneous_before_turnoff_during_incident = audit
                .max_simultaneous_before_turnoff_during_incident
                .max(simultaneous);
        }
        stats.overlaps += sim.overlaps();
        stats.crossing_conflicts += sim.crossing_conflicts();
        let home = sim.completed_trips();
        stats.exited = home.len() as u32;
        stats.spawned = stats.exited + sim.car_count() as u32;
        stats.peak_cars = stats.peak_cars.max(sim.car_count() as u32);
        if sim.queued() > stats.peak_queued {
            stats.peak_queued = sim.queued();
            stats.peak_at = sim.time() as u32;
        }
        if home.len() == trips.len() && cursor == trips.len() && step % 4 == 0 {
            break;
        }
        sim.step();
    }
    audit.distinct_before_turnoff_during_incident = audit
        .cars
        .values()
        .filter(|e| e.first_before_turnoff_during_incident_s.is_some())
        .count();
    let snapshot = sim.record_snapshot();
    let run = Run {
        junction: sim.junction_snapshot(),
        trips,
        decisions,
        home: sim.completed_trips(),
        town: sim.experiment_recording(Vec::new(), stats),
        history: BTreeMap::new(),
        messages: sim.messages(),
        message_log: sim.message_log(),
        history_enabled: true,
        slot_log: sim.slot_log(),
    };
    Ok((run, snapshot, audit))
}
