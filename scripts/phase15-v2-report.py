#!/usr/bin/env python3
"""Render complete v2 outcomes; every seed/range/arm is retained."""
import json,statistics,sys
from pathlib import Path
rows=[json.loads(l) for l in Path(sys.argv[1]).read_text().splitlines()];gate=rows[-1];scores=rows[:-1];near=gate['part']=='near'
def f(x):
 if x is None:return 'null'
 if isinstance(x,bool):return str(x).lower()
 if isinstance(x,(int,float)):return f'{x:.3f}'
 return str(x)
print('# Phase '+('15a NEAR control' if near else '15b labour claim')+' — v2 results\n')
print('**'+('PASS' if gate['pass'] else 'FAIL')+'** at the preregistered **300 m** range. All ten seeds, ranges and arms are retained. Zeros, negatives and unfinished trips are not removed. No code or scenario was tuned after the v2 preregistration.\n')
print('V1 files and FAILs remain unchanged. These v2 harness changes were made after the post-v1-scoring diagnosis: known remaining blockage contributes to the old-route time cost; known closures use time comparison instead of the emergency-yield distance ceiling, with original route/safety checks; priority grants create merged edits and due public deliveries before RECORD actions. make_way.rs, judge, schema, map, demand, arrival window, horizon and SAM evidence are unchanged. The accepted FAR stop remains a retained finding; this experiment has no FAR arm.\n')
print('300 m is the claim/control range, citing [Waymo’s up-to-300-m lidar range](https://support.google.com/waymo/answer/9190838). 60 m and 150 m are hypothetical sensitivities with no benefit/control bar. Sensing is front-based, straight-line and unoccluded in every arm. The model replies are the unchanged v1 cache: route/1500 m for the tree, nearby/500 m for priority; grant decisions use the existing Mock policy.\n')
print('Gate output:\n\n```json\n'+json.dumps(gate,indent=2)+'\n```\n')
print('| Range m | Paired seeds | Mean gain s | Median gain s | Minimum s | Maximum s | '+('Control holds: abs median <10 s' if near else 'Positive claimant gains')+' |')
print('|---|---|---|---|---|---|---|')
for radius in [60,150,300]:
 a=[r for r in scores if r['arm']=='RECORD' and r['sensor_range_m']==radius and (near or r['case']=='labour')]
 v=[r['affected']['median_s'] if near else r['arrival_gain_s'] for r in a];v=[x for x in v if x is not None]
 holds=sum(abs(x)<10 if near else x>0 for x in v)
 print('| '+' | '.join(f(x) for x in [radius,len(v),statistics.mean(v) if v else None,statistics.median(v) if v else None,min(v) if v else None,max(v) if v else None,holds])+' |')
print('\nEvery score row contains per-trip completion status and final link. Missing arrivals remain null and completion/pair coverage is explicit. Costs retain negatives. RECORD_CITY is diagnostic only.\n')
if near:
 print('Edge 15 is the accepted NEAR control: last turn-off node 55, D ≈85.12 m. Coverage counts require actual entry after start_s and observation on-map with the blocked link still on the remaining route before the last turn-off during the incident. Both unique and peak simultaneous counts are reported. The per-car `turnoff_timeline` retains merge time, observed node-passing time and their signed difference; a missing pass is null (for example, diversion before that node), not zero.\n')
 print('| Seed | Range | Arm | Finished | Original / observed blocked-route cars | Before turn-off unique / peak | Merge s | Passed before / after merge / never | Reroutes before / after sight | Affected median gain s | Others mean / p95 / max loss s | Total / on-map median delay s |')
 print('|---|---|---|---|---|---|---|---|---|---|---|---|')
 for r in scores:
  c=r['unaffected_costs']
  cells=[r['seed'],r['sensor_range_m'],r['arm'],f"{r['completed']}/{r['trips']}",f"{r['cars_with_blocked_edge_on_original_route']} / {r['cars_observed_on_map_with_blocked_edge_remaining']}",f"{r['affected_before_turnoff_distinct_cars']} / {r['affected_before_turnoff_max_simultaneous_cars']}",r['merge_at_s'],f"{r['cars_passed_turnoff_before_merge']} / {r['cars_passed_turnoff_at_or_after_merge']} / {r['cars_never_passed_turnoff']}",f"{r['rerouted_before_ever_seeing_tree']} / {r['rerouted_after_sighting']}",r['affected']['median_s'],' / '.join(f(c[k]) for k in ['mean_s','p95_s','max_s']),f"{f(r['total_delay']['median_s'])} / {f(r['on_map_delay']['median_s'])}"]
  print('| '+' | '.join(f(x) for x in cells)+' |')
else:
 vals={}
 for radius in [60,150,300]:vals[radius]=any(r['arrival_gain_s'] is not None and r['arrival_gain_s']>0 for r in scores if r['arm']=='RECORD' and r['case']=='labour' and r['sensor_range_m']==radius)
 print(('The record wins only at shorter ranges; it does not pass the 300 m claim.' if not vals[300] and (vals[60] or vals[150]) else 'There are no positive claimant gains at any range.' if not any(vals.values()) else 'Positive gains are not confined to the shorter sensitivities.')+'\n')
 print('Priority edits, per-edit/per-car due deliveries and accepted actions are included in every row’s record. Each RECORD action is checked against a due delivery for its beneficiary. Baseline local sensor actions do not create shared-record receipts.\n')
 print('| Seed | Range | Twin | Arm | Finished | Granted | Gain s | Edits / deliveries / actions | Others mean / p95 / max loss s | Crossing mean / p95 / max loss s |')
 print('|---|---|---|---|---|---|---|---|---|---|')
 for r in scores:
  c=r['others_costs'];x=r['crossing_costs']
  cells=[r['seed'],r['sensor_range_m'],r['case'],r['arm'],f"{r['completed']}/{r['trips']}",r['granted'],r['arrival_gain_s'],f"{r['priority_edits']} / {r['priority_deliveries']} / {r['accepted_actions']}",' / '.join(f(c[k]) for k in ['mean_s','p95_s','max_s']),' / '.join(f(x[k]) for k in ['mean_s','p95_s','max_s'])]
  print('| '+' | '.join(f(x) for x in cells)+' |')
