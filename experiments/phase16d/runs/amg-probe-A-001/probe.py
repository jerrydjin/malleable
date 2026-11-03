#!/usr/bin/env python3
"""One genuine official-SAM development proposal probe; never a video score."""
import hashlib,json,os,platform,shutil,signal,subprocess,sys,threading,time,resource
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path('/workspace/malleable');EXPERIMENT=ROOT/'experiments/phase16d'
sys.path.insert(0,str(EXPERIMENT));OUT=EXPERIMENT/'runs/amg-probe-A-001'
OUT.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,OUT/'probe.py')
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb')as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def write(name,obj):
 p=OUT/name;tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n');tmp.replace(p)
def memory():
 stat=dict(line.split()for line in Path('/sys/fs/cgroup/memory.stat').read_text().splitlines())
 return {'current':int(Path('/sys/fs/cgroup/memory.current').read_text()),'limit':int(Path('/sys/fs/cgroup/memory.max').read_text()),'anon':int(stat['anon']),'file':int(stat['file']),'inactive_file':int(stat['inactive_file']),'file_dirty':int(stat['file_dirty'])}
m=memory();extra=int(3.2*(1<<30));working=m['current']-m['inactive_file']
record={'phase':'development_proposal_probe','not_a_scored_video_run':True,'state':'preflight','started_at_utc':datetime.now(timezone.utc).isoformat(),'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'checkpoint_inference_attempts':0,'memory_preflight':m,'estimated_incremental_peak_bytes':extra,'estimated_working_set_peak_bytes':working+extra,'watchdog_working_set_limit_bytes':m['limit']-(1<<29),'threads':1,'boxes_supplied_to_sam':False,'heldout_opened':False}
write('run.json',record)
if working+extra>m['limit']-(1<<29):
 record.update(state='NOT_RUN',reason='Estimated working-set peak exceeds cgroup limit minus 512 MiB reserve');write('run.json',record);print(json.dumps(record));raise SystemExit(3)
stop=threading.Event();peak={'current':m['current'],'working_set':working,'anon':m['anon']}
def watch():
 with(OUT/'memory.jsonl').open('w')as stream:
  while not stop.is_set():
   x=memory();x['working_set']=x['current']-x['inactive_file'];x['elapsed_s']=time.monotonic()-start
   for k in peak:peak[k]=max(peak[k],x[k])
   stream.write(json.dumps(x)+'\n');stream.flush()
   if x['working_set']>record['watchdog_working_set_limit_bytes']:
    write('memory-abort.json',{'state':'FAIL','reason':'Probe-only memory watchdog terminated this process before the 8 GiB limit','observed':x,'baseline_process_untouched':True});os._exit(77)
   stop.wait(.5)
start=time.monotonic();thread=threading.Thread(target=watch,daemon=True);thread.start()
try:
 import cv2,numpy as np,torch,torchvision,sam2
 from torchvision.ops.boxes import batched_nms
 from sam2.build_sam import build_sam2_video_predictor
 from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
 import tracker
 cv2.setNumThreads(1);torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(0);torch.use_deterministic_algorithms(True)
 cfg=json.loads((EXPERIMENT/'config.json').read_text());sam=cfg['sam'];checkpoint=(ROOT/sam['checkpoint']).resolve()
 folders=list(Path('/workspace/.cache/phase16d/tracking').glob('.A.tracking-*'))
 folder=Path('/workspace/.cache/phase16d/tracking/A')if Path('/workspace/.cache/phase16d/tracking/A/metadata.json').exists()else folders[-1]
 image_path=folder/'frames/00020.jpg';image=tracker._read_rgb(image_path);height,width=image.shape[:2]
 provenance=tracker._verified_source(sam2,sam['source_revision'])
 record.update(state='loading_official_checkpoint',checkpoint_sha256=sha(checkpoint),checkpoint_bytes=checkpoint.stat().st_size,checkpoint_path=str(checkpoint.relative_to(ROOT)),input_jpeg_sha256=sha(image_path),input_jpeg_path=str(image_path),input_rgb_sha256=hashlib.sha256(image.tobytes()).hexdigest(),source_clip_sha256=sha(ROOT/cfg['clips']['A']['path']),source_clip=cfg['clips']['A']['path'],source_frame_index=20*cfg['frame_stride'],sampled_frame_index=20,source_s=cfg['clips']['A']['source_start_s']+20*cfg['frame_stride']/30.,image_size_wh=[width,height],model_source=provenance,versions={'torch':torch.__version__,'torchvision':torchvision.__version__,'opencv':cv2.__version__,'numpy':np.__version__,'python':platform.python_version()},model_id=sam['model_id'],model_config=sam['model_config'],device='cpu',dtype='float32',seed=0,apply_postprocessing=False,vos_optimized=False)
 write('run.json',record)
 model=build_sam2_video_predictor(sam['model_config'],str(checkpoint),device='cpu',apply_postprocessing=False,vos_optimized=False,hydra_overrides_extra=['++model.add_all_frames_to_correct_as_cond=true',f"++model.max_cond_frames_in_attn={sam['max_cond_frames_in_attn']}"])
 model.to(dtype=torch.float32)
 parameters={'points_per_side':16,'points_per_batch':8,'pred_iou_thresh':0.,'stability_score_thresh':0.,'mask_threshold':sam['mask_threshold'],'box_nms_thresh':1.,'crop_n_layers':0,'min_mask_region_area':0,'output_mode':'binary_mask','multimask_output':True}
 generator=SAM2AutomaticMaskGenerator(model,**parameters)
 record.update(state='generating_genuine_masks',checkpoint_inference_attempts=1,parameters=parameters,model_parameter_count=sum(p.numel()for p in model.parameters()));write('run.json',record)
 generated=time.monotonic()
 with torch.inference_mode():raw=generator.generate(image)
 record.update(state='packing_outputs',generation_elapsed_s=time.monotonic()-generated,raw_mask_count=len(raw));write('run.json',record)
 identifiers=np.arange(1,len(raw)+1,dtype=np.int64);packed=np.empty((len(raw),(height*width+7)//8),dtype=np.uint8);metadata=[]
 def finite(value):
  value=float(value);return value if np.isfinite(value)else None
 for i,p in enumerate(raw):
  mask=np.asarray(p['segmentation'],bool);packed[i]=np.packbits(mask.reshape(-1),bitorder='little')
  metadata.append({'probe_mask_id':i+1,'area_px':int(mask.sum()),'bbox_xyxy':tracker._bbox(mask)if mask.any()else None,'native_bbox_xywh':p['bbox'],'predicted_iou':finite(p['predicted_iou']),'stability_score':finite(p['stability_score']),'point_coords':p['point_coords'],'crop_box':p['crop_box'],'mask_sha256':hashlib.sha256(packed[i].tobytes()).hexdigest()})
 np.savez_compressed(OUT/'masks.npz',ids=identifiers,shape=np.array([height,width]),packed=packed);write('proposals.json',metadata)
 # Evaluation annotations are first opened here, after the single model generation.
 plan=json.loads((EXPERIMENT/'dev-targets.json').read_text());spec=plan['clips']['A'];sw,sh=spec['source_size_wh']
 quality_indices=[i for i,p in enumerate(raw)if p['predicted_iou']>sam['pred_iou_threshold']and p['stability_score']>=sam['stability_threshold']]
 native_boxes=torch.tensor([[p['bbox'][0],p['bbox'][1],p['bbox'][0]+p['bbox'][2],p['bbox'][1]+p['bbox'][3]]for p in raw],dtype=torch.float32)
 scores=torch.tensor([p['predicted_iou']for p in raw],dtype=torch.float32)
 q=torch.tensor(quality_indices,dtype=torch.long)
 nms_indices=[quality_indices[i]for i in batched_nms(native_boxes[q],scores[q],torch.zeros(len(q),dtype=torch.long),sam['box_nms_threshold']).tolist()]if len(q)else[]
 original,counts=tracker.prepare_proposals([raw[i]for i in nms_indices],(height,width),sam)
 def largest_retention(indices):
  ordered=sorted(indices,key=lambda i:(-metadata[i]['area_px'],-raw[i]['predicted_iou'],-raw[i]['stability_score'],i));retained=[]
  for i in ordered:
   if metadata[i]['area_px']<sam['minimum_mask_area_px']:continue
   duplicate=False
   for j in retained:
    iou,containment,ratio=tracker._overlap(raw[i]['segmentation'],raw[j]['segmentation'])
    if iou>=sam['duplicate_iou']or(containment>=sam['duplicate_containment']and ratio<=sam['association_max_area_ratio']):duplicate=True;break
   if not duplicate:retained.append(i)
  return retained
 original_hashes={p['mask_sha256']for p in original};largest_after_nms=largest_retention(nms_indices);largest_before_nms=largest_retention(quality_indices)
 evaluation={'evaluation_only':True,'boxes_opened_after_generation':True,'original_config_sha256':sha(EXPERIMENT/'config.json'),'dev_targets_sha256':sha(EXPERIMENT/'dev-targets.json'),'quality_passing_count':len(quality_indices),'native_nms_passing_count':len(nms_indices),'original_retention_counts':counts,'largest_after_same_native_nms_count':len(largest_after_nms),'largest_before_native_nms_count':len(largest_before_nms),'targets':{}}
 for target in spec['targets']:
  b=target['box_xyxy'];box=[int(np.floor(b[0]*width/sw)),int(np.floor(b[1]*height/sh)),int(np.ceil(b[2]*width/sw)),int(np.ceil(b[3]*height/sh))];x0,y0,x1,y1=box;ba=(x1-x0)*(y1-y0);matches=[]
  for i,p in enumerate(raw):
   mask=p['segmentation'];area=int(mask.sum());inter=int(mask[y0:y1,x0:x1].sum())
   if not area or not inter:continue
   inside=inter/area;coverage=inter/ba
   if inside<.5 or coverage<.04:continue
   xx0,yy0,xx1,yy1=metadata[i]['bbox_xyxy'];xx1+=1;yy1+=1;bi=max(0,min(xx1,x1)-max(xx0,x0))*max(0,min(yy1,y1)-max(yy0,y0));iou=bi/(ba+(xx1-xx0)*(yy1-yy0)-bi)
   matches.append({**metadata[i],'mask_inside_box_fraction':inside,'box_coverage':coverage,'bbox_iou':iou,'bottom_gap_to_annotation_px':y1-yy1,'quality_passing':i in quality_indices,'native_nms_retained':i in nms_indices,'original_quality_first_retained':metadata[i]['mask_sha256']in original_hashes,'largest_after_same_nms_retained':i in largest_after_nms,'largest_before_nms_retained':i in largest_before_nms})
  matches.sort(key=lambda p:(-p['bbox_iou'],-p['area_px'],p['probe_mask_id']));evaluation['targets'][target['id']]={'working_box_xyxy':box,'raw_matching_proposals':matches}
 write('evaluation.json',evaluation)
 record.update(state='complete',elapsed_s=time.monotonic()-start,memory_sampled_peaks=peak,process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,artifact_manifest=[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha(p)}for p in sorted(OUT.iterdir())if p.is_file()and p.name not in('run.json','memory.jsonl')]);write('run.json',record)
 print(json.dumps({'state':'complete','raw_count':len(raw),'quality_passing_count':len(quality_indices),'native_nms_passing_count':len(nms_indices),'original_retained_count':len(original),'largest_after_nms_count':len(largest_after_nms),'largest_before_nms_count':len(largest_before_nms),'output':str(OUT),'process_peak_rss_bytes':record['process_peak_rss_bytes']}))
except BaseException as error:
 record.update(state='failed',failure_type=type(error).__name__,failure_reason=str(error),elapsed_s=time.monotonic()-start,memory_sampled_peaks=peak);write('run.json',record);raise
finally:
 stop.set();thread.join(timeout=1)
