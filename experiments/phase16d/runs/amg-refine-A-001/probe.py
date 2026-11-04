#!/usr/bin/env python3
"""One genuine SAM automatic part-to-whole refinement probe; development only."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,resource,shutil,subprocess,sys,time
ROOT=Path('/workspace/malleable');EXP=ROOT/'experiments/phase16d';SOURCE=EXP/'runs/amg-probe-A-001';OUT=EXP/'runs/amg-refine-A-001'
OUT.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,OUT/'probe.py')
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb')as s:
  for b in iter(lambda:s.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def write(name,value):
 p=OUT/name;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n');t.replace(p)
start=time.monotonic();record={'phase':'development_automatic_refinement_probe','state':'started','not_a_scored_video_run':True,'started_at_utc':datetime.now(timezone.utc).isoformat(),'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'heldout_opened':False,'evaluation_boxes_supplied_to_sam':False,'automatic_mask_generation_calls':0,'refinement_predict_calls':0,'source_probe_run_sha256':sha(SOURCE/'run.json'),'source_proposals_sha256':sha(SOURCE/'proposals.json'),'threads':2,'device':'cpu','dtype':'float32'};write('run.json',record)
try:
 import cv2,numpy as np,torch,torchvision,sam2
 from torchvision.ops.boxes import batched_nms
 from sam2.build_sam import build_sam2
 from sam2.sam2_image_predictor import SAM2ImagePredictor
 from sam2.utils.amg import calculate_stability_score
 sys.path.insert(0,str(EXP));import tracker
 cv2.setNumThreads(1);torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.manual_seed(0);torch.use_deterministic_algorithms(True)
 cfg=json.loads((EXP/'config.json').read_text());sam=cfg['sam'];base=json.loads((SOURCE/'run.json').read_text());raw=json.loads((SOURCE/'proposals.json').read_text())
 capture=cv2.VideoCapture(str(ROOT/base['source_clip']));capture.set(cv2.CAP_PROP_POS_FRAMES,base['source_frame_index']);ok,bgr=capture.read();capture.release()
 if not ok:raise RuntimeError('Source frame decode failed')
 bgr=cv2.resize(bgr,tuple(base['image_size_wh']),interpolation=cv2.INTER_AREA);ok,encoded=cv2.imencode('.jpg',bgr,[cv2.IMWRITE_JPEG_QUALITY,98])
 if not ok or hashlib.sha256(encoded.tobytes()).hexdigest()!=base['input_jpeg_sha256']:raise RuntimeError('Reconstructed native cached JPEG hash mismatch')
 (OUT/'input.jpg').write_bytes(encoded.tobytes());bgr=cv2.imdecode(encoded,cv2.IMREAD_COLOR);rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)
 if hashlib.sha256(rgb.tobytes()).hexdigest()!=base['input_rgb_sha256']:raise RuntimeError('Reconstructed SAM RGB hash mismatch')
 with np.load(SOURCE/'masks.npz')as data:shape=tuple(data['shape']);packed=data['packed'];identifiers=data['ids']
 mask_cache={}
 def mask(i):
  if i not in mask_cache:mask_cache[i]=np.unpackbits(packed[i-1],bitorder='little',count=int(np.prod(shape))).reshape(shape).astype(bool)
  return mask_cache[i]
 boxes=torch.tensor([[r['native_bbox_xywh'][0],r['native_bbox_xywh'][1],r['native_bbox_xywh'][0]+r['native_bbox_xywh'][2],r['native_bbox_xywh'][1]+r['native_bbox_xywh'][3]]for r in raw],dtype=torch.float32)
 scores=torch.tensor([r['predicted_iou']for r in raw],dtype=torch.float32)
 policy={'primary_min_iou':.8,'secondary_min_iou':.65,'minimum_stability':.9,'nms_iou':.7,'minimum_area_px':96,'body_height_width_ratio':[.4,3.],'lower_width_body_width_ratio':[.5,1.5],'lower_height_body_height_ratio':[.1,.8],'lower_area_body_area_ratio':[.1,.8],'maximum_vertical_gap_px':4,'maximum_vertical_gap_body_height_fraction':.12,'maximum_center_offset_body_width_fraction':.2,'minimum_horizontal_overlap_fraction':.7,'final_min_iou':.8,'final_min_stability':.9,'stability_score_offset':1.0}
 def nms(q):
  ix=[i for i,r in enumerate(raw)if r['predicted_iou']>=q and r['stability_score']>=policy['minimum_stability']and r['area_px']>=policy['minimum_area_px']]
  return [raw[ix[j]]for j in batched_nms(boxes[ix],scores[ix],torch.zeros(len(ix),dtype=torch.long),policy['nms_iou']).tolist()]
 primary=nms(policy['primary_min_iou']);secondary=nms(policy['secondary_min_iou']);pairs=[]
 for a in primary:
  x0,y0,x1,y1=a['bbox_xyxy'];w=x1-x0+1;h=y1-y0+1
  if not policy['body_height_width_ratio'][0]<=h/w<=policy['body_height_width_ratio'][1]:continue
  for b in secondary:
   if a['probe_mask_id']==b['probe_mask_id']:continue
   X0,Y0,X1,Y1=b['bbox_xyxy'];W=X1-X0+1;H=Y1-Y0+1;gap=Y0-y1-1;overlap=max(0,min(x1,X1)-max(x0,X0)+1)/min(w,W)
   if (gap<0 or gap>max(policy['maximum_vertical_gap_px'],policy['maximum_vertical_gap_body_height_fraction']*h)or not .5<=W/w<=1.5 or not .1<=H/h<=.8 or abs((X0+X1)-(x0+x1))/2>.2*w or overlap<.7 or not .1<=b['area_px']/a['area_px']<=.8):continue
   points=[]
   for source in(a,b):
    m=mask(source['probe_mask_id']);dist=cv2.distanceTransform(m.astype(np.uint8),cv2.DIST_L2,5);_,_,_,point=cv2.minMaxLoc(dist);points.append(list(point))
   pairs.append({'body_probe_mask_id':a['probe_mask_id'],'lower_probe_mask_id':b['probe_mask_id'],'box_xyxy':[min(x0,X0),min(y0,Y0),max(x1,X1)+1,max(y1,Y1)+1],'positive_points_xy':points,'vertical_gap_px':gap,'horizontal_overlap_fraction':overlap,'body_predicted_iou':a['predicted_iou'],'lower_predicted_iou':b['predicted_iou'],'body_stability':a['stability_score'],'lower_stability':b['stability_score']})
 checkpoint=ROOT/sam['checkpoint'];provenance=tracker._verified_source(sam2,sam['source_revision'])
 record.update(state='loading_model',input_jpeg_sha256=base['input_jpeg_sha256'],input_rgb_sha256=base['input_rgb_sha256'],input_frame_index=base['source_frame_index'],source_clip=base['source_clip'],source_clip_sha256=base['source_clip_sha256'],source_s=base['source_s'],checkpoint_sha256=sha(checkpoint),checkpoint_bytes=checkpoint.stat().st_size,model_id=sam['model_id'],model_config=sam['model_config'],model_source=provenance,pair_policy=policy,primary_count=len(primary),secondary_count=len(secondary),prompt_count=len(pairs),automatic_prompts=pairs,versions={'torch':torch.__version__,'torchvision':torchvision.__version__,'opencv':cv2.__version__,'numpy':np.__version__});write('run.json',record)
 model=build_sam2(sam['model_config'],str(checkpoint),device='cpu',apply_postprocessing=False);model.to(dtype=torch.float32);predictor=SAM2ImagePredictor(model)
 results=[];refined=[]
 with torch.inference_mode():
  predictor.set_image(rgb)
  for j,pair in enumerate(pairs):
   t=time.monotonic();logits,iou,low=predictor.predict(point_coords=np.array(pair['positive_points_xy'],dtype=np.float32),point_labels=np.ones(len(pair['positive_points_xy']),dtype=np.int32),box=np.array(pair['box_xyxy'],dtype=np.float32),multimask_output=True,return_logits=True);record['refinement_predict_calls']+=1
   stability=calculate_stability_score(torch.from_numpy(logits),sam['mask_threshold'],policy['stability_score_offset']).numpy()
   support=mask(pair['body_probe_mask_id'])|mask(pair['lower_probe_mask_id'])
   for k in range(len(logits)):
    m=logits[k]>sam['mask_threshold'];refined.append(m)
    inside=[bool(m[int(y),int(x)])for x,y in pair['positive_points_xy']]
    result={'refined_mask_id':len(refined),'prompt_index':j,'multimask_index':k,'predicted_iou':float(iou[k]),'stability_score':float(stability[k]),'bbox_xyxy':tracker._bbox(m)if m.any()else None,'area_px':int(m.sum()),'positive_points_inside':inside,'source_parts_coverage':float((m&support).sum()/support.sum()),'quality_pass':bool(float(iou[k])>=policy['final_min_iou']and float(stability[k])>=policy['final_min_stability']),'mask_sha256':hashlib.sha256(np.packbits(m.reshape(-1),bitorder='little').tobytes()).hexdigest(),'predict_elapsed_s':time.monotonic()-t};results.append(result)
 record.update(state='generated',refined_mask_count=len(refined));write('run.json',record)
 np.savez_compressed(OUT/'masks.npz',ids=np.arange(1,len(refined)+1),shape=np.array(shape),packed=np.stack([np.packbits(m.reshape(-1),bitorder='little')for m in refined])if refined else np.empty((0,(int(np.prod(shape))+7)//8),np.uint8));write('proposals.json',results)
 # Evaluation-only data is opened after all prompt selection/model calls complete.
 plan=json.loads((EXP/'dev-targets.json').read_text());target_rows={}
 for target in plan['clips']['A']['targets']:
  scale=np.array([shape[1]/1920,shape[0]/1080]*2);b=np.array(target['box_xyxy'])*scale;box=[int(np.floor(b[0])),int(np.floor(b[1])),int(np.ceil(b[2])),int(np.ceil(b[3]))];x0,y0,x1,y1=box;ba=(x1-x0)*(y1-y0);matches=[]
  for m,r in zip(refined,results):
   inter=int(m[y0:y1,x0:x1].sum());area=int(m.sum());bx=r['bbox_xyxy']
   if not area or not bx:continue
   X0,Y0,X1,Y1=bx;X1+=1;Y1+=1;bi=max(0,min(x1,X1)-max(x0,X0))*max(0,min(y1,Y1)-max(y0,Y0));bbox_iou=bi/(ba+(X1-X0)*(Y1-Y0)-bi)
   matches.append({**r,'mask_inside_box_fraction':inter/area,'box_coverage':inter/ba,'bbox_iou':bbox_iou,'bottom_gap_to_annotation_px':y1-Y1})
  target_rows[target['id']]={'working_box_xyxy':box,'masks':matches}
 write('evaluation.json',{'evaluation_only':True,'boxes_opened_after_generation':True,'dev_targets_sha256':sha(EXP/'dev-targets.json'),'targets':target_rows})
 record.update(state='complete',elapsed_s=time.monotonic()-start,process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,artifact_manifest=[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha(p)}for p in sorted(OUT.iterdir())if p.is_file()and p.name!='run.json']);write('run.json',record)
 print(json.dumps({'state':'complete','prompt_count':len(pairs),'refined_masks':results,'output':str(OUT)}))
except BaseException as error:
 record.update(state='failed',failure_type=type(error).__name__,failure_reason=str(error),elapsed_s=time.monotonic()-start);write('run.json',record);raise
