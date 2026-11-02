#!/usr/bin/env python3
"""Explicit opt-in clipped OSM import. Default Rust importer is not changed."""
from pathlib import Path
import xml.etree.ElementTree as ET
import json,math,argparse,hashlib
BBOX=(-122.410,37.738,-122.400,37.762)
DRIVABLE={'motorway','trunk','primary','secondary','tertiary','unclassified','residential','living_street','service','motorway_link','trunk_link','primary_link','secondary_link','tertiary_link'}
def clip(a,b,box):
 west,south,east,north=box;dx=b[0]-a[0];dy=b[1]-a[1];lo,hi=0.,1.
 for p,q in [(-dx,a[0]-west),(dx,east-a[0]),(-dy,a[1]-south),(dy,north-a[1])]:
  if p==0:
   if q<0:return None
  else:
   r=q/p
   if p<0:lo=max(lo,r)
   else:hi=min(hi,r)
   if lo>hi:return None
 if hi-lo<1e-12:return None
 return lo,hi

def import_boundary(path,box=BBOX):
 root=ET.parse(path).getroot();points={int(n.get('id')):(float(n.get('lon')),float(n.get('lat'))) for n in root.findall('node')}
 ways=[];count={}
 for w in root.findall('way'):
  t={x.get('k'):x.get('v') for x in w.findall('tag')};refs=[int(x.get('ref')) for x in w.findall('nd')]
  if t.get('highway') not in DRIVABLE or t.get('area')=='yes' or any(t.get(k) in ['private','no'] for k in ['access','vehicle','motor_vehicle']):continue
  if any(r not in points for r in refs):raise ValueError('OSM references missing node')
  ways.append((int(w.get('id')),refs,t))
  for r in set(refs):count[r]=count.get(r,0)+1
 lat=(box[1]+box[3])/2;scale=111320*math.cos(math.radians(lat))
 def dist(a,b):return math.hypot((b[0]-a[0])*scale,(b[1]-a[1])*111320)
 coords={};segments=[];rejected=[]
 def key(xy,original=None):
  k=('osm',original) if original is not None else ('boundary',round(xy[0],11),round(xy[1],11))
  coords[k]=xy;return k
 for wid,refs,t in sorted(ways):
  # Split every closed source ring, including one attached at only one junction.
  # Additional shared intersections may split it further; no way ID is special.
  interior=refs[1:-1] if len(refs)>2 and refs[0]==refs[-1] else []
  ring_split=next((r for r in interior[len(interior)//2:]+interior[:len(interior)//2] if r!=refs[0]),None)
  pieces=[];active=[]
  for index,(ra,rb) in enumerate(zip(refs,refs[1:])):
   a,b=points[ra],points[rb];c=clip(a,b,box)
   if c is None:
    if len(active)>=2:pieces.append(active)
    active=[];continue
   lo,hi=c;aa=(a[0]+lo*(b[0]-a[0]),a[1]+lo*(b[1]-a[1]));bb=(a[0]+hi*(b[0]-a[0]),a[1]+hi*(b[1]-a[1]))
   ka=key(aa,ra if lo<1e-12 else None);kb=key(bb,rb if hi>1-1e-12 else None)
   if active and active[-1]!=ka:
    if len(active)>=2:pieces.append(active)
    active=[]
   if not active:active=[ka]
   active.append(kb)
   if hi<1-1e-12 or count.get(rb,0)>1 or rb==ring_split or index==len(refs)-2:
    if len(active)>=2:pieces.append(active)
    active=[]
  if len(active)>=2:pieces.append(active)
  highway=t['highway'];cls='ramp' if highway.endswith('_link') else 'motorway' if highway in ['motorway','trunk'] else 'arterial' if highway in ['primary','secondary','tertiary'] else 'street'
  oneway=t.get('oneway','yes' if highway=='motorway' or t.get('junction')=='roundabout' else 'no');direction=-1 if oneway=='-1' else 1 if oneway in ['yes','1','true'] else 0
  default=65*.44704 if cls=='motorway' else 35*.44704 if cls=='ramp' else 25*.44704
  bad_tags=[]
  try:
   s=t.get('maxspeed','');speed=float(s.replace('mph','').replace('km/h','').strip())*(.44704 if 'mph' in s else 1/3.6)
  except ValueError:
   speed=default
   if t.get('maxspeed'):bad_tags.append('unparseable maxspeed tag')
  try:
   total=int(t.get('lanes',2 if direction==0 else 1));forward=int(t.get('lanes:forward',max(total//2,1) if direction==0 else total));back=int(t.get('lanes:backward',max(total//2,1)))
  except ValueError:
   total=forward=back=0;bad_tags.append('unparseable lanes tag')
  for part,ks in enumerate(pieces):
   length=sum(dist(coords[a],coords[b]) for a,b in zip(ks,ks[1:]))
   directions=[(ks,forward)] if direction==1 else [(ks[::-1],total)] if direction==-1 else [(ks,forward),(ks[::-1],back)]
   for directed,lanes in directions:
    why=bad_tags.copy()
    if directed[0]==directed[-1]:why.append('self-loop after ring split')
    if not math.isfinite(length) or length<=.1:why.append('nonfinite/zero length or below retained 0.1 m import threshold')
    if not 1<=lanes<=8:why.append('bad lane count (supported 1..8)')
    if not math.isfinite(speed) or speed<=0:why.append('nonpositive/nonfinite speed')
    if why:
     rejected.append({'osm_way':wid,'part':part,'from_key':directed[0],'to_key':directed[-1],'reasons':why,'osm_tags':t,'protected_freeway':(highway=='motorway' and '101' in t.get('ref','')) or highway=='motorway_link'})
     continue
    segments.append({'keys':directed,'length':length,'lanes':lanes,'speed':speed,'class':cls,'way':wid,'part':part,'tags':t})
 used=sorted({s['keys'][i] for s in segments for i in [0,-1]},key=str);ids={k:i for i,k in enumerate(used)}
 incoming={k:0 for k in used};outgoing=incoming.copy()
 for s in segments:outgoing[s['keys'][0]]+=1;incoming[s['keys'][-1]]+=1
 def boundary(xy):return min(abs(xy[0]-box[0]),abs(xy[0]-box[2]),abs(xy[1]-box[1]),abs(xy[1]-box[3]))<1e-9
 nodes=[]
 for k in used:
  x,y=coords[k];nodes.append({'id':ids[k],'lat':y,'lon':x,'trim_m':7.,'zipper':False,'demand_per_s':.01 if boundary((x,y)) and outgoing[k] else 0.,'sink_weight':1. if boundary((x,y)) and incoming[k] else 0.,'negotiate':False})
 edges=[];meta=[]
 for s in segments:
  ks=s['keys'];shape=[]
  for a,b in zip(ks,ks[1:]):
   a,b=coords[a],coords[b];steps=max(1,math.ceil(dist(a,b)/2))
   shape.extend({'lat':a[1]+(b[1]-a[1])*i/steps,'lon':a[0]+(b[0]-a[0])*i/steps} for i in range(1,steps+1))
  shape.pop();eid=len(edges)
  edges.append({'id':eid,'from':ids[ks[0]],'to':ids[ks[-1]],'lanes':s['lanes'],'speed_limit_mps':s['speed'],'length_m':s['length'],'one_way':True,'class':s['class'],'shape':shape})
  meta.append({'edge':eid,'osm_way':s['way'],'part':s['part'],'from_key':ks[0],'to_key':ks[-1],'osm_tags':s['tags'],'boundary_entry':boundary(coords[ks[0]]),'boundary_exit':boundary(coords[ks[-1]])})
  nodes[ids[ks[0]]]['trim_m']=min(nodes[ids[ks[0]]]['trim_m'],s['length']*.25);nodes[ids[ks[-1]]]['trim_m']=min(nodes[ids[ks[-1]]]['trim_m'],s['length']*.25)
 data={'version':1,'attribution':'© OpenStreetMap contributors · ODbL 1.0 · https://www.openstreetmap.org/copyright','origin':[lat,(box[0]+box[2])/2],'schedule_scale':1.,'nodes':nodes,'edges':edges}
 metadata={'mode':'boundary opt-in; no SCC deletion','bbox_west_south_east_north':box,'node_keys':used,'edges':meta,'raw_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'rejected_edges':rejected}
 return data,metadata
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--boundary',action='store_true',required=True);args=p.parse_args()
 data,meta=import_boundary('maps/us101.osm')
 Path('maps/us101.json').write_text(json.dumps(data,indent=2)+'\n');Path('assets/phase15e/import-manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
 Path('assets/phase15e/rejected-edges.json').write_text(json.dumps(meta['rejected_edges'],indent=2)+'\n')
 protected=any(e['protected_freeway'] for e in meta['rejected_edges'])
 print(json.dumps({'nodes':len(data['nodes']),'edges':len(data['edges']),'boundary_entries':sum(n['demand_per_s']>0 for n in data['nodes']),'boundary_exits':sum(n['sink_weight']>0 for n in data['nodes']),'dropped_edges':len(meta['rejected_edges']),'protected_freeway_dropped':protected,'decision':'STOP' if protected else 'CONTINUE_TO_MAP_GATE'}))
 if protected:raise SystemExit('STOP: a US-101 mainline or motorway-link edge was dropped')
