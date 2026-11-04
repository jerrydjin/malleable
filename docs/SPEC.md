# Malleable: the shared road record

**The demonstrated loop is observe, confirm, merge and deliver; reject the spoof.**
The experiment combines a genuine cached SAM mask with simulated car sightings:
an observing car proposes a tree edit, a different car confirms it, the host
merges it, and recipients learn the hazard on delivery. The spoof is rejected
and causes no reroute. This is a protocol demonstration, not a headline claim
that sharing makes trips faster.
([docs/gates/phase-15a-v2-scores.jsonl @ a38931b](https://github.com/jerrydjin/malleable/blob/a38931b/docs/gates/phase-15a-v2-scores.jsonl),
[docs/phase-15a-v2-results.md @ a38931b](https://github.com/jerrydjin/malleable/blob/a38931b/docs/phase-15a-v2-results.md))

AVs can read and write a live shared road record much as coding agents commit
to a codebase: edits are commits, another car's confirmation is review, priority
claims are reservations, and clashing claims would be merge conflicts. The
request determines how far a message reaches. In the implemented simulator,
the scopes are `nearby`, `route` and `city`; a fleet can receive requests through
a host API, but `fleet` is not a reach value. Persistent fleet deployment,
general reservation arbitration and merge-conflict resolution are **not built**;
those parts of the analogy describe the intended protocol, not existing services.
([src/record.rs @ e4ba2a6](https://github.com/jerrydjin/malleable/blob/e4ba2a6/src/record.rs),
[src/make_way.rs @ e4ba2a6](https://github.com/jerrydjin/malleable/blob/e4ba2a6/src/make_way.rs))

## Implementation boundary

The retained root implementation and the corrected experiment are distinct.
The corrected record results cited here use the isolated build materialized from the root plus
`experiments/phase15-v2/record-host.patch`. It repairs hazard route costing and
publishes granted priorities as deliverable edits. The original results and
source remain retained; the correction was disclosed after the original scores.
([docs/phase-15-v2-preregistration.md @ 89616b3](https://github.com/jerrydjin/malleable/blob/89616b3/docs/phase-15-v2-preregistration.md),
[experiments/phase15-v2/record-host.patch @ 14d1ed9](https://github.com/jerrydjin/malleable/blob/14d1ed9/experiments/phase15-v2/record-host.patch))

## Messages and actual recorded examples

These are the implemented fields, rather than a proposed network standard.
Graph links and routes are host identifiers, not steering commands.

| Type | Fields and meaning |
|---|---|
| Evidence classification, `Reply` | `label`, `blocks` (`road`, `lane`, `none`), `reach` (`scope`, `radius_m`), `rationale`. Unknown fields are rejected. |
| Hazard, `RoadEdit` | `id`, `link`, `route`, `blocks`, `since_s`, `author_car`, `evidence` (`image_sha256`, `mask_sha256`, `label`), `status`, `confirmations`, `expires_at`, `merged_at`. The isolated build adds `kind` to distinguish hazard and priority edits. |
| Review, `Confirmation` | `car`, `at_s`, `saw_blockage`. This is a host-recorded sensor observation by a distinct car. |
| Priority, `PriorityEdit` | `kind`, `author_car`, `route`, `since_s`, `expires_at`, `reach`. In the corrected RECORD arm a host grant also creates a merged road edit with `kind: priority`, `blocks: none` and no hazard confirmations. |
| Claim policy input and decision | Input: `car`, `rider`, `reason`, `at_s`, completed `history`. Decision: `granted`, explanation, requester/other driver lines and provenance. Current-trip truth, current destination and future outcomes are not policy inputs; history can include prior destinations. |
| Make-way wire request, `MakeWayRequest` | `id`, `issuer`, `route`, `urgency`, `reason`, `issued_at`, `expires_at`, optional `signature`. Authentication using that signature is **not built**. |
| Internal make-way message, `MakeWayMessage` | `emergency`, `route`, `urgency`, `expiry_s`, `issued_at_s`. The host turns it into eligible local action proposals. |

Sources: [src/record.rs](https://github.com/jerrydjin/malleable/blob/e4ba2a6/src/record.rs),
[src/rush_hour.rs](https://github.com/jerrydjin/malleable/blob/e4ba2a6/src/rush_hour.rs),
[src/make_way.rs](https://github.com/jerrydjin/malleable/blob/e4ba2a6/src/make_way.rs), all at `e4ba2a6`,
and [the isolated patch @ 14d1ed9](https://github.com/jerrydjin/malleable/blob/14d1ed9/experiments/phase15-v2/record-host.patch).

The following are field projections of committed messages, with omitted fields
left out rather than invented. The hazard and review are from the RECORD row
for seed **1**, sensor range **300 m** in
[docs/gates/phase-15a-v2-scores.jsonl @ a38931b](https://github.com/jerrydjin/malleable/blob/a38931b/docs/gates/phase-15a-v2-scores.jsonl):

```json
{
  "id": "tree",
  "kind": "hazard",
  "link": 27,
  "route": [305,1043,24,1552,25,830,26,1046,27,964,317,1701,513,1499,302,1049,306],
  "author_car": 1108,
  "blocks": "road",
  "since_s": 240.0,
  "expires_at": 1140.0,
  "status": "Merged",
  "confirmations": [{"car":1221,"at_s":240.25,"saw_blockage":true}],
  "merged_at": 240.25
}
```

That row's first delivery is
`{"edit_id":"tree","car":1304,"at_s":240.35000867701393}`.
The isolated snapshot records deliveries per edit and recipient, in addition
to first receipt and first sighting. The recorded model classification is
`label: blocked`, `blocks: road`, `reach: {scope: route, radius_m: 1500.0}`;
the priority reply selects `nearby` with `radius_m: 500.0`.
([docs/gates/phase-15a-v2-scores.jsonl @ a38931b](https://github.com/jerrydjin/malleable/blob/a38931b/docs/gates/phase-15a-v2-scores.jsonl),
[docs/gates/phase-15-model-replies.json @ 33ceabc](https://github.com/jerrydjin/malleable/blob/33ceabc/docs/gates/phase-15-model-replies.json))

For the labour illustration, the corresponding RECORD row for seed **1** at
**300 m** contains this priority projection and reach. Its host policy source
is `mock`, and its reach source is `model`:
([docs/gates/phase-15b-v2-scores.jsonl @ bb7746a](https://github.com/jerrydjin/malleable/blob/bb7746a/docs/gates/phase-15b-v2-scores.jsonl))

```json
{
  "id": "priority:1164",
  "kind": "priority",
  "author_car": 1164,
  "blocks": "none",
  "since_s": 345.5,
  "expires_at": 585.5,
  "status": "Merged",
  "merged_at": 345.5,
  "confirmations": []
}
```

The same row has **1 edit, 70 deliveries and 88 accepted action records**, but
her arrival gain is **0 s**. These are action records, not a count of distinct
drivers helped or a claim of faster arrival. The gym twin is denied, with
**0 gain, cost, edits, deliveries and actions**.
([docs/gates/phase-15b-v2-scores.jsonl @ bb7746a](https://github.com/jerrydjin/malleable/blob/bb7746a/docs/gates/phase-15b-v2-scores.jsonl))

A complete make-way wire request from an earlier retained run illustrates
route, urgency, lifetime and the unused signature field. This is not the labour
edit above; its lifetime belongs to that earlier run.
([docs/gates/phase-13c/sf-peak-1.messages.json @ 4ff7d80](https://github.com/jerrydjin/malleable/blob/4ff7d80/docs/gates/phase-13c/sf-peak-1.messages.json), `requests[0]`)

```json
{
  "id": "car:1164@345.5",
  "issuer": 1164,
  "route": [305,1043,24,1552,25,830,26,1046,27,964,317,1701,513,1499,302,1049,306],
  "urgency": 1.0,
  "reason": "Host granted emergency precedence",
  "issued_at": 345.5,
  "expires_at": 10345.5,
  "signature": null
}
```

## Lifecycle and spoof rejection

**Observe → propose → review → merge → broadcast → expire.** The physical
sensor boundary checks whether the car is in range of the host obstacle. It
adds a sighted hazard to that car's `KnownHazards`. The experiment attaches the
committed image/mask evidence to a proposal; it does not run a camera model
independently for each car. Another car must confirm from its own simulated
sensor, strictly after the proposal. Self-review and repeated reviews are
ignored. Positive confirmation can merge a blocking edit; negative confirmations
can reject it, and pending expiry rejects an unmerged edit.
([src/record.rs](https://github.com/jerrydjin/malleable/blob/e4ba2a6/src/record.rs),
[src/record_host.rs](https://github.com/jerrydjin/malleable/blob/e4ba2a6/src/record_host.rs), at `e4ba2a6`)

Only a merged, unexpired edit schedules recipient knowledge. Reach filtering
and host message delays determine delivery; the car may act only after its
own sighting or receipt. Expiry removes eligibility to act on the knowledge;
the historical snapshot may retain the edit. A granted priority uses a different
authorization path: the grant permits merge, without pretending that hazard
sensor review verifies a medical claim.
([src/record_host.rs @ e4ba2a6](https://github.com/jerrydjin/malleable/blob/e4ba2a6/src/record_host.rs),
[experiments/phase15-v2/record-host.patch @ 14d1ed9](https://github.com/jerrydjin/malleable/blob/14d1ed9/experiments/phase15-v2/record-host.patch))

In the committed spoof row corresponding to the hazard example, the edit is
`Rejected`, `merged_at` is null, and delivery/event arrays are empty: **0 spoof
reroutes**. Across the tested ranges, the true edit merges on **10/10 seeds at
each range**, while the spoof merges on **0/10**. This demonstrates the review
boundary under the supplied simulated spoof, not resistance to colluding or
authenticated malicious fleets.
([docs/gates/phase-15a-v2-scores.jsonl @ a38931b](https://github.com/jerrydjin/malleable/blob/a38931b/docs/gates/phase-15a-v2-scores.jsonl))

## Fleet receive API and allowed actions

`FleetReceiver::receive(request, now, vehicles)` takes a `MakeWayRequest` and
host-generated `VehicleProposal`s, returning an action for each supplied vehicle
in input order. `SafetyFleet` applies request lifetime, self-request, numeric,
hold-budget and physics acceptance checks; a receiver can always decline.
The serialized action variants are `lane_change {to_link}`, `reroute` with a
link sequence, `hold {duration_s}`, and `ignore`. Holds are budget-clamped;
failed host acceptance becomes `ignore`. This is an in-process fleet boundary,
not a deployed fleet transport or permission to override driving safety.
([src/make_way.rs @ e4ba2a6](https://github.com/jerrydjin/malleable/blob/e4ba2a6/src/make_way.rs))

## Safety enforcement and its limits

The model never touches physics. The earlier merge schema permits ranked lane
intents; the record model permits evidence labels and reach; the claim policy
permits grant/deny and words. Hosts calculate paths, check gaps, execute motion
and retain the option to ignore. These record experiments install no signals,
sirens or queue reordering. Hazard rerouting reads active per-car
`KnownHazards`, rather than the incident list; ground truth belongs to physical
obstacles and the range-checked sensor boundary.
([src/schema.rs](https://github.com/jerrydjin/malleable/blob/e4ba2a6/src/schema.rs),
[src/make_way.rs](https://github.com/jerrydjin/malleable/blob/e4ba2a6/src/make_way.rs),
[src/record_host.rs](https://github.com/jerrydjin/malleable/blob/e4ba2a6/src/record_host.rs), at `e4ba2a6`)

The isolated correction includes known remaining closure time in the old
route's cost. A disclosed record-host-only exception permits a legal detour
that exceeds the inherited emergency-yield distance ceiling when its time
cost qualifies against that known closure. It preserves physical distances,
the existing time slack and host safety checks; it does not modify
`src/make_way.rs`, `src/schema.rs` or `src/judge.rs`.
([docs/phase-15-v2-preregistration.md @ 89616b3](https://github.com/jerrydjin/malleable/blob/89616b3/docs/phase-15-v2-preregistration.md),
[docs/phase-15-v2-verification.md @ a864b76](https://github.com/jerrydjin/malleable/blob/a864b76/docs/phase-15-v2-verification.md))

The unchanged judge scores trajectories for collisions/overlap, completion,
time and fairness; network experiments additionally record their own gate
diagnostics. The corrected tree and labour matrices report **0 collisions and
0 overlaps**, with all trips finished; tree leak violations are **0**. Those
observations are bounded to those runs, not a general safety guarantee. The
freeway baseline below demonstrates that the engine can still produce overlaps.
([src/judge.rs @ e4ba2a6](https://github.com/jerrydjin/malleable/blob/e4ba2a6/src/judge.rs),
[docs/gates/phase-15a-v2-scores.jsonl @ a38931b](https://github.com/jerrydjin/malleable/blob/a38931b/docs/gates/phase-15a-v2-scores.jsonl),
[docs/gates/phase-15b-v2-scores.jsonl @ bb7746a](https://github.com/jerrydjin/malleable/blob/bb7746a/docs/gates/phase-15b-v2-scores.jsonl))

## Where the Meta models sit

**Eyes:** Meta **SAM 2.1 tiny**, model ID `facebook/sam2.1-hiera-tiny`, produced
the committed CPU mask. The image is an illustrative fallen-tree photograph,
not a Potrero camera capture. The original and corrected tree scores replay
that cache; live per-car image capture and SAM inference are **not built**.
([assets/phase15/sam.json @ 11772c2](https://github.com/jerrydjin/malleable/blob/11772c2/assets/phase15/sam.json),
[docs/phase-15a-results.md @ cbb9139](https://github.com/jerrydjin/malleable/blob/cbb9139/docs/phase-15a-results.md),
[docs/phase-15a-v2-results.md @ a38931b](https://github.com/jerrydjin/malleable/blob/a38931b/docs/phase-15a-v2-results.md))

**Semantic classification and reach:** the configured Meta LLM is
`meta-models/muse-spark-open-1026`, hosted by **Baseten** at
`https://inference.baseten.co/v1`; `MODEL_API_MODEL` can override it. That is the
literal model identifier, not the project's name. The committed replies are
marked `source: model` and the registration identifies the Baseten adapter,
but the cache omits the runtime model ID and any override. Consequently its
exact historical model version cannot be independently established from the
recording. No Llama model is identified by these files.
([src/muse.rs @ e4ba2a6](https://github.com/jerrydjin/malleable/blob/e4ba2a6/src/muse.rs),
[docs/gates/phase-15-model-replies.json @ 33ceabc](https://github.com/jerrydjin/malleable/blob/33ceabc/docs/gates/phase-15-model-replies.json),
[docs/phase-15a-preregistration.md @ 7eb04d6](https://github.com/jerrydjin/malleable/blob/7eb04d6/docs/phase-15a-preregistration.md))

The original and corrected record runs consume these replies offline. Labour
and gym grants use **Mock**, with only reach taken from the model recording.
The LLM classifies and selects message reach; another car's host-recorded
sensor observation supplies peer review, and the host computes routes. The
adapter can make live calls, but none occur during these scored matrices.
The later labour and freeway studies stopped at baseline validity and have
no scored RECORD runs.
([docs/phase-15-v2-preregistration.md @ 89616b3](https://github.com/jerrydjin/malleable/blob/89616b3/docs/phase-15-v2-preregistration.md),
[docs/phase-15c-results.md @ 6d8b38c, PR #45](https://github.com/jerrydjin/malleable/blob/6d8b38c/docs/phase-15c-results.md),
[experiments/phase15e/STOP-r2.md @ e9db1c5, PR #46](https://github.com/jerrydjin/malleable/blob/e9db1c5/experiments/phase15e/STOP-r2.md))

## Predictions we made in advance that held

**NEAR was a control: eyesight should already be enough.** At **300 m**, the
preregistered condition was absolute affected median gain **<10 s on at least
8/10 seeds**, with others' **p95 loss ≤30 s and maximum <60 s** per seed.
It held on **8/10**. Gains were small and mixed, from **−1 s to 15.5 s**;
the mean of seed medians was **5.825 s**. The control passed its written
tolerance; it did not show exact equality in every seed or a headline efficacy
win. The **60 m and 150 m** runs are hypothetical sensitivities with no outcome
bar. The stronger gains at the shorter range do not establish the claim at
the declared range.
([docs/phase-15-v2-preregistration.md @ 89616b3](https://github.com/jerrydjin/malleable/blob/89616b3/docs/phase-15-v2-preregistration.md),
[docs/phase-15a-v2-results.md @ a38931b](https://github.com/jerrydjin/malleable/blob/a38931b/docs/phase-15a-v2-results.md),
[docs/gates/phase-15a-v2-scores.jsonl @ a38931b](https://github.com/jerrydjin/malleable/blob/a38931b/docs/gates/phase-15a-v2-scores.jsonl))

## Limits and next work

- **Potrero has no qualifying FAR tree.** The retained feasibility finding
  selects none beyond **300 m** from the last turn-off. Even the permissive
  stop-line-to-road-end upper bound is **179.04446096056432 m**, about **180 m**;
  this is an upper bound, not the measured distance of a chosen FAR site.
  ([docs/phase-15-v2-feasibility.md @ de1b1a2](https://github.com/jerrydjin/malleable/blob/de1b1a2/docs/phase-15-v2-feasibility.md),
  [assets/phase15/v2-site-manifest.json @ de1b1a2](https://github.com/jerrydjin/malleable/blob/de1b1a2/assets/phase15/v2-site-manifest.json))
- **Labour illustrates priority, not faster arrival.** Her corrected run
  gained **0 s on every seed and range** despite published edits and actions.
  The benefit claim **FAILS**.
  ([docs/phase-15b-v2-results.md @ bb7746a](https://github.com/jerrydjin/malleable/blob/bb7746a/docs/phase-15b-v2-results.md))
- **The follow-up labour validity check STOPPED.** Only **5/10** seeds met
  the required **≥30 s** on-map approach excess, against **≥8/10** required.
  No RECORD efficacy comparison followed.
  ([docs/phase-15c-results.md @ 6d8b38c](https://github.com/jerrydjin/malleable/blob/6d8b38c/docs/phase-15c-results.md),
  [PR #45](https://github.com/jerrydjin/malleable/pull/45))
- **The freeway map gate passes, but its see-only baseline STOPPED.** Both
  mainline directions, lane counts and ramp connectivity pass. The baseline
  spills back on **10/10 seeds**, with unfinished affected cohorts in every
  seed. Seed **1** records **1,938 overlaps** and **9,804/13,034 trips finished**;
  reported collisions are **0**. The engine cannot yet carry the declared
  freeway volume safely to completion in this configuration. No RECORD or
  spoof comparison was scored. The freeway remains the next experiment,
  after a separately declared engine/validity repair, not a result in favour
  of the record.
  ([assets/phase15e/map-validity.json @ e9db1c5](https://github.com/jerrydjin/malleable/blob/e9db1c5/assets/phase15e/map-validity.json),
  [assets/phase15e/validity-summary.json @ e9db1c5](https://github.com/jerrydjin/malleable/blob/e9db1c5/assets/phase15e/validity-summary.json),
  [experiments/phase15e/STOP-r2.md @ e9db1c5](https://github.com/jerrydjin/malleable/blob/e9db1c5/experiments/phase15e/STOP-r2.md),
  [PR #46](https://github.com/jerrydjin/malleable/pull/46))

[Scoreboard of declared claims and retained outcomes](SCOREBOARD.md).
