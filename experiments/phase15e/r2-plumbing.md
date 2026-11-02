# Phase 15e r2 plumbing revision — 2 November 2026

The user authorized continuation after the retained STOP commits 7b4fd03 and
8618bfd. Both remain ancestors; their STOP note and verification are unchanged.
The failed map gate and rejection report are copied to map-validity-v1.json
and rejected-edges-v1.json. No outcome has been scored or used for this fix.

The opt-in clipped importer now splits every closed OSM way at an interior
node, without identifying particular way IDs. It validates every resulting
directed edge before building the map. Remaining self-loops, nonpositive or
nonfinite lengths/speeds and bad lane counts are dropped with OSM way ID,
segment, endpoints, tags and reasons. The existing 0.1 m geometric threshold
is also reported rather than silently skipped. Any rejected US-101 road or
motorway-link ramp requires STOP (all motorway links are conservatively
protected). The real extract drops zero edges after the split.

Tests cover one-way and two-way closed rings and invalid protected ramp
reporting. The default importer and host code are unchanged by this revision.
The committed Caltrans volume, placement rule, demand, horizon, sensor range
and outcome bars are unchanged. After code/tests are committed, rerun the map
gate; if it fails, retain a new STOP without further repair or simulation.
