/// Read-only claimant observer; motion and policy application match the retained runner.
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct LabourApproachTrace {
    pub approach_enter_s: Option<f64>,
    pub approach_exit_s: Option<f64>,
    pub approach_queued_s: f64,
}
impl LabourApproachTrace {
    pub fn dwell_s(&self) -> Option<f64> {
        self.approach_enter_s
            .zip(self.approach_exit_s)
            .map(|(a, b)| b - a)
    }
}
pub fn simulate_trips_phase15c(
    seed: u64,
    policy: &dyn Policy,
    mut trips: Vec<Trip>,
    net: &Network,
    config: crate::record::RecordConfig,
    probe: u32,
    approach: usize,
) -> Result<(Run, crate::record::Snapshot, LabourApproachTrace), String> {
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
    let mut trace = LabourApproachTrace::default();
    let road = &net.links[approach];
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
                return Err("15c policy identities mismatch".into());
            }
            for d in batch {
                sim.set_precedence(d.car, d.granted);
                decisions.push(d);
            }
        }
        if let Some((route, idx, _, speed, _)) = sim.vehicle_route_position(probe) {
            let l = &net.links[route.links[idx]];
            let on_approach =
                !l.is_connector() && (l.edge, l.from, l.to) == (road.edge, road.from, road.to);
            if on_approach {
                trace
                    .approach_enter_s
                    .get_or_insert((sim.time() - crate::network::NET_DT_S).max(0.0));
                if speed < crate::network::QUEUED_MPS {
                    trace.approach_queued_s += crate::network::NET_DT_S;
                }
            } else if trace.approach_enter_s.is_some() {
                trace.approach_exit_s.get_or_insert(sim.time());
            }
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
    Ok((run, snapshot, trace))
}
