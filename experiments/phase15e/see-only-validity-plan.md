# See-only validity declaration — 2 November 2026, before traffic outcomes

Map gate b4b3991 passes after the user-authorized ring fix. The original STOP
commits and notes remain retained. The fixed structural placement rule chooses
southbound edge 1611, OSM way 1343758309, D=1508.352460 m from its previous
exit, in a 1519.980218 m gap. The host-centred 8 m footprint fits; starts at
240 s, lasts 900 s. Caltrans volume.json is unchanged: 7600 veh/h/direction.

Two through chains use all their actual OSM lanes. A uniform position q in a
60-bin grid (LCM of the 3/4/5 lane counts) maps to floor(q*lanes/60) on each
road. The bin cycles with trip index and seed, and each transition uses an
existing legal host connector. This balances widened/narrowed roads without
new lane-changing physics. Duplicate paths are simulated only once for SOLO
references; bins retain their weights in demand. Both directions have 1900
trips per seed over 900 s, with the retained 13i/15b seeded departure phase.

Local traffic uses the existing 15b rule at ramp/local junctions: distinct
incoming local roads, straightest legal connector by direction dot product,
connector-ID tie break; keep movements conflicting with a ramp movement.
Deduplicate physical incoming roads and three-link paths. Apply the unchanged
network::demand_vph by incoming class (1250 arterial, 125 other) for 900 s.
There are 35 declared local flows. Every seed's exact population count is in
traffic-inputs.json; no car is dropped to reduce demand or make validity pass.

All cars are ordinary; the host receives no granted priority. No signals,
sirens, queue reordering or model calls. SensorOnly uses the retained v2
KnownHazards and own-sight reroute boundary, at 300 m. The record arm is not run.
The host horizon remains the inclusive 10,000 steps at 0.25 s.

AFFECTED means an original through route uses the blocked edge and demand
starts in [240,1140), per the original fixed README. Reference is an actual
solo no-incident trip on the identical legal lane path. On-map excess is
(home-entry) minus solo (home-entry); spawn waiting is separate. Every trip's
entry, arrival, unfinished status and final link is reported. An incomplete
affected cohort cannot count as a successful delay seed. Zero/negative delays
stay in the distributions. All other completion/safety diagnostics are also
reported; the validity bars remain delay and queue containment as requested.

ON-MAP QUEUE: observe blocked-direction boundary sources during [240,1140).
Spillback is an actual body at the source entry, speed < existing QUEUED_MPS,
rear below the host's entry-clearance threshold, while due demand older than
one simulation tick has not entered. This excludes ordinary fractional-tick
spawn timing. Observe the physics only; the observer changes no action.
Report first spill time, duration, peak unentered demand, examples and each
affected trip's off-map wait. Any observed spillback fails queue containment.
A synthetic regression exercises a real stopped queue and unentered demand.

PASS validity only if affected median ON-MAP excess >=30 s on >=8/10 seeds
and the queue remains on-map for all ten seeds. Run all ten see-only seeds;
no RECORD comparison or efficacy bars are calculated. On failure, STOP without
changing the placement, demand, horizon or observer thresholds. If unfinished
at 18:00 Europe/London, commit the partial work and a STOP instead of scoring.
