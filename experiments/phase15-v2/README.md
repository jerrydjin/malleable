# Isolated Phase 15 v2 record host

V1 and the accepted FAR stop at `de1b1a2` remain byte-identical. This directory
contains a small versioned patch to the retained record host/data types, a
read-only audited runner, and the v2 gate. `materialize.py` copies the retained
sources into `/tmp/malleable-phase15-v2-build`, applies this patch there, and
adds the v2 runner and gate. It never edits the retained source tree. Only the
v2 gate is exposed as an example in that generated package.

The host costs the old route as free-flow plus the car's KNOWN remaining
blockage time. Before registration, the validity run also exposed a second
veto: the emergency-yield distance ceiling rejected a time-favourable NEAR
detour (703.7 m versus 554.0 m). V2 adds a record-only known-closure time-cost
exception. Physical distances are not fabricated; graph legality, current link,
sink, claim/gap checks and receiver safety remain. `make_way.rs`, judge, schema
and every other retained file are unchanged. The three-second time slack is
the existing constant. Expired or future knowledge cannot supply wait cost.

V2 RECORD priority claims appear as merged `kind: priority` edits. Due
per-edit/per-car deliveries populate both `deliveries` and `delivered` before
an accepted lane change or bounded hold. Local SENSOR_ONLY receipts stay local.
Priority evidence is the host grant, not an image; its image hash fields are
empty. Hazard edits retain the committed SAM evidence. No model runs at score
time and no motion policy is delegated to it.

Repeated route counts and shortest paths are cached without changing their
values. Counts are rebuilt after serial route changes; path caches are invalidated
when occupied-link counts change and keyed by current link, sink and KnownHazards.
The original per-candidate count computation is checked by a regression test.
The retained road-record tests are also compiled against this corrected host,
including the test that observes every route change and requires the car's own
sighting or edit receipt first. Only the new `kind` field is added to its test
edit constructor in the generated copy.

```sh
bash scripts/phase15-v2.sh build
bash scripts/phase15-v2.sh test --release --lib v2_
bash scripts/phase15-v2.sh test --release --test phase15_v2
bash scripts/phase15-v2.sh run part=validity
# Only after the separate committed preregistration/freeze:
bash scripts/phase15-v2.sh run part=near seed=1 end=10
bash scripts/phase15-v2.sh run part=birth seed=1 end=10
```

Preparation uses Python only to materialize the build; the `run` command uses
Cargo/Rust only. Root inputs and the complete generated source payload are
hashed separately. The gate refuses outcome scores before a committed v2
preregistration and freeze, or when either source manifest or the exact-code
validity artifact differs. Validity checks report no paired benefit measures.
