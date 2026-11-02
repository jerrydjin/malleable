#!/usr/bin/env python3
"""Apply the previously committed structural rule without any traffic outcomes."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2]
def placement():
 m=json.loads((ROOT/'maps/us101.json').read_text());meta=json.loads((ROOT/'assets/phase15e/import-manifest.json').read_text());gate=json.loads((ROOT/'assets/phase15e/map-validity.json').read_text())
 if not gate['valid']:raise SystemExit('STOP: map gate must pass before placement')
 edges={e['id']:e for e in m['edges']};tags={e['edge']:e for e in meta['edges']};main={i for i,t in tags.items() if t['osm_tags'].get('highway')=='motorway' and '101' in t['osm_tags'].get('ref','')}
 outs={};ins={}
 for i in main:outs.setdefault(edges[i]['from'],[]).append(i);ins.setdefault(edges[i]['to'],[]).append(i)
 ramps={edges[i]['from'] for i,t in tags.items() if t['osm_tags'].get('highway')=='motorway_link'}
 starts=sorted(i for i in main if not ins.get(edges[i]['from']) or tags[i]['boundary_entry'])
 paths=[]
 def visit(path):
  end=edges[path[-1]]['to'];nexts=[i for i in sorted(outs.get(end,[])) if i not in path]
  if not nexts:paths.append(path);return
  for i in nexts:visit(path+[i])
 for start in starts:visit([start])
 pairs=[];chains=[]
 for chain in paths:
  nodes=[edges[chain[0]]['from']]+[edges[i]['to'] for i in chain];prefix=[0.]
  for i in chain:prefix.append(prefix[-1]+edges[i]['length_m'])
  exits=[k for k,node in enumerate(nodes) if node in ramps and k<len(chain)]
  chains.append({'edges':chain,'nodes':nodes,'exit_nodes':[nodes[k] for k in exits],'length_m':prefix[-1],'boundary_entry':tags[chain[0]]['boundary_entry'],'boundary_exit':tags[chain[-1]]['boundary_exit']})
  for a,b in zip(exits,exits[1:]):
   candidates=[{'edge':chain[k],'osm_way':tags[chain[k]]['osm_way'],'part':tags[chain[k]]['part'],'D_m':prefix[k]+edges[chain[k]]['length_m']/2-prefix[a],'edge_length_m':edges[chain[k]]['length_m']} for k in range(a,b)]
   pairs.append({'upstream_exit_node':nodes[a],'upstream_osm_key':meta['node_keys'][nodes[a]],'downstream_exit_node':nodes[b],'downstream_osm_key':meta['node_keys'][nodes[b]],'gap_m':prefix[b]-prefix[a],'edges':chain[a:b],'chain':chain,'candidates':candidates,'direction':'northbound' if m['nodes'][nodes[-1]]['lat']>m['nodes'][nodes[0]]['lat'] else 'southbound'})
 pairs.sort(key=lambda p:(-p['gap_m'],str(p['upstream_osm_key']),str(p['downstream_osm_key']),[tags[i]['osm_way'] for i in p['edges']]))
 chosen=pairs[0] if pairs else None
 tree=sorted(chosen['candidates'],key=lambda c:(-c['D_m'],c['osm_way'],c['part']))[0] if chosen else None
 valid=bool(tree and tree['D_m']>300 and tree['edge_length_m']>=8)
 result={'kind':'structural_placement_before_traffic','rule_commit':'f8a4f7f','map_sha256':hashlib.sha256((ROOT/'maps/us101.json').read_bytes()).hexdigest(),'chains':chains,'exit_pairs':pairs,'chosen_gap':chosen,'tree':tree,'footprint_length_m':8,'start_s':240,'duration_s':900,'valid':valid,'decision':'CONTINUE_TO_SEE_ONLY_VALIDITY' if valid else 'STOP','reason':None if valid else 'No tree midpoint under the fixed longest-exit-gap rule exceeds 300 m with an upstream exit and room for the footprint'}
 return result
if __name__=='__main__':
 result=placement();(ROOT/'assets/phase15e/placement.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ['tree','valid','decision','reason']}))
