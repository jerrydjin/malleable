#!/usr/bin/env python3
"""Materialize a v2 crate without editing a single retained v1 file."""
from pathlib import Path
import hashlib,os,shutil,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
OUT=Path('/tmp/malleable-phase15-v2-build')
def sync(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 if not path.exists() or path.read_bytes()!=data:path.write_bytes(data)
# This version is explicitly based on the retained v1 sources and FAR audit.
subprocess.run(['git','diff','--exit-code','de1b1a2','--','src','Cargo.toml','Cargo.lock','examples/phase15_birth.rs'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
with tempfile.TemporaryDirectory(prefix='p15-v2-source-') as temporary:
 stage=Path(temporary)
 shutil.copytree(ROOT/'src',stage/'src')
 for name in ['Cargo.toml','Cargo.lock']:shutil.copyfile(ROOT/name,stage/name)
 cargo=(stage/'Cargo.toml').read_text().replace('publish = false','publish = false\nautoexamples = false',1)
 cargo+='\n[[example]]\nname = "phase15_v2_gate"\npath = "examples/phase15_v2_gate.rs"\n'
 (stage/'Cargo.toml').write_text(cargo)
 subprocess.run(['patch','--batch','-s','-p1','-d',str(stage),'-i',str(ROOT/'experiments/phase15-v2/record-host.patch')],check=True)
 shutil.copyfile(ROOT/'experiments/phase15-v2/runner.rs',stage/'src/phase15_v2_runner.rs')
 (stage/'examples').mkdir();(stage/'tests').mkdir()
 shutil.copyfile(ROOT/'experiments/phase15-v2/gate.rs',stage/'examples/phase15_v2_gate.rs')
 shutil.copyfile(ROOT/'examples/phase15_birth.rs',stage/'examples/phase15_birth.rs')
 with (stage/'examples/phase15_birth.rs').open('a') as out:
  out.write('\npub fn v2_row(seed:u64,range:f64,case:&str,name:&str,probe:u32,r:&Run,s:&record::Snapshot,b:&Run,replies:&Replies)->Value {row(seed,range,case,name,probe,r,s,b,replies)}\n')
 shutil.copyfile(ROOT/'examples/phase15_gate.rs',stage/'examples/phase15_tree_v1_rows.rs')
 with (stage/'examples/phase15_tree_v1_rows.rs').open('a') as out:
  out.write('\npub fn v2_row(seed:u64,range:f64,name:&str,r:&Run,s:&record::Snapshot,b:&Run,bs:&record::Snapshot,link:usize,start:f64,free:f64,source:&str,spoof:bool)->Value {row(seed,range,name,r,s,b,bs,link,start,free,source,spoof)}\n')
 shutil.copyfile(ROOT/'experiments/phase15-v2/tests.rs',stage/'tests/phase15_v2.rs')
 # Exercise the retained safety/leak regressions against the corrected host too.
 retained=(ROOT/'tests/road_record.rs').read_text().replace('    RoadEdit {\n','    RoadEdit {\n        kind: "hazard".into(),\n',1)
 (stage/'tests/road_record.rs').write_text(retained)
 for source in sorted(stage.rglob('*')):
  if source.is_file():sync(OUT/source.relative_to(stage),source.read_bytes())
 for name in ['maps','assets','scenarios','docs']:
  target=OUT/name
  if not target.exists():target.symlink_to(ROOT/name,target_is_directory=True)
 fixtures=OUT/'tests/fixtures'
 if not fixtures.exists():fixtures.symlink_to(ROOT/'tests/fixtures',target_is_directory=True)
 paths=sorted(p for p in stage.rglob('*') if p.is_file())
 manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(stage))+'\n' for p in paths)
 sync(OUT/'generated-code.sha256',manifest.encode())
print(OUT)
