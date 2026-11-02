# Phase 15e: US-101 freeway shared road record

Prediction fixed 2 November 2026, before any simulation: where a last exit is
more than 300 m before a blockage, a reviewed shared-record warning can arrive
before that exit and save time compared with 300 m eyesight alone. This is a
hypothesis, not a reported result.

Base main e4ba2a6. All retained files stay byte-identical. Only new experiment,
asset, map and phase15e script paths are used. Import/build changes are opt-in
and isolated; judge, schema and make_way.rs stay unchanged. Reuse the retained
v2 record/review code and known-closure time-cost exception.

## Fixed structural placement rule, before outcomes

Use exactly bbox south 37.738, west -122.410, north 37.762, east -122.400.
Clip drivable OSM roads to this box, preserving directed connectivity, every
in-box ramp and explicit OSM lane counts. Boundary cuts are entry/source or
exit/sink nodes; do not require a strongly connected freeway. Default imports
of both retained SF OSM files must reproduce unchanged JSON.

Enumerate directed US-101 mainline chains between boundary cuts. An exit
diverge is a mainline node with an outgoing OSM motorway_link branch leaving
the mainline. Enumerate consecutive exit-diverge pairs on each chain. Choose
the pair with the longest along-mainline distance; ties use upstream OSM node,
then downstream OSM node, then ordered way IDs. Candidate tree positions are
mainline road midpoints strictly between the pair. Choose the midpoint farthest
from the upstream exit, ties by OSM way/segment ID. It must be >300 m after
that exit and leave an upstream exit in the box. Record all pairs/candidates.
If no midpoint satisfies the rule, STOP rather than change the rule or map.
The footprint is 8 m, all lanes, starts at 240 s and lasts 900 s as in 15a.

## Demand and validity, before record-versus-eyesight outcomes

Use a published Caltrans US-101 traffic-census row in or nearest the box,
recording exact URL, row, year and figures. Use its published peak-hour total
when available, divided equally by direction unless a direction factor is
published for that location; otherwise use AADT/24, divided equally by
 direction. This choice is made from the published columns, never queue scores.
Local street flow uses the retained network::demand_vph rule by road class.
Arrivals last 900 s; the host horizon remains 10,000 inclusive 0.25 s steps.
Seeds 1–10. No demand, duration, range or horizon adjustment after diagnostics.

Validity uses see_only at 300 m only and same-route solo references. Affected
cars are original mainline routes through the blocked road with demand times
at/after incident start and before expiry. Missing entries/finishes remain
explicit. Require paired median ON-MAP excess >=30 s on >=8/10 seeds.
Also require the queue stays on-map: report source waiting and actual boundary
queue spillback during the incident separately, including never-entered cars.
Any failed structural or baseline-validity check requires a committed STOP
and PR. No record-versus-eyesight scoring is allowed before passing validity
and a separate committed dated preregistration with code/input SHA-256s.

## Conditional scored bars

At 300 m, record vs see_only: affected median gain >=15 s on >=7/10 seeds;
exit-ramp/local absorbing cars' median extra delay <=10 s; everyone else p95
<=30 s and max <60 s; zero collisions/overlaps; all trips finish; spoof gives
zero reroutes. A first car's SAM-supported edit needs a distinct sensor
confirmation before merge; only a merged delivered edit can inform a car.
No model calls at score time. Retain every seed, zero, negative and unfinished
status. No tuning after preregistration.

## Time box

Run `TZ=Europe/London date` throughout. If steps 1–3 are not committed by
18:00 Europe/London on 2 November, commit current work with STOP and open the
PR. Never continue past a failed validity check or a committed STOP.
