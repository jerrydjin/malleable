#!/usr/bin/env python3
from pathlib import Path
import subprocess,hashlib,tempfile
ROOT=Path(__file__).resolve().parents[2];OUT=Path('/tmp/malleable-phase15e-build')
base=Path(subprocess.check_output(['python3','experiments/phase15-v2/materialize.py'],cwd=ROOT,text=True).strip())
def sync(p,b):
 p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists() or p.read_bytes()!=b:p.write_bytes(b)
names=[l.split('  ',1)[1] for l in (base/'generated-code.sha256').read_text().splitlines()]
with tempfile.TemporaryDirectory(prefix='phase15e-source-') as tmp:
 stage=Path(tmp)
 for name in names:
  b=(base/name).read_bytes()
  if name=='Cargo.toml':b=b.replace(b'phase15_v2_gate',b'phase15e_gate')
  sync(stage/name,b)
 subprocess.run(['patch','--batch','-s','-p1','-d',str(stage),'-i',str(ROOT/'experiments/phase15e/full-lanes.patch')],check=True)
 for source,target in [('gate.rs','examples/phase15e_gate.rs'),('tests.rs','tests/phase15e.rs')]:sync(stage/target,(ROOT/'experiments/phase15e'/source).read_bytes());names.append(target)
 sync(stage/'generated-code.sha256',(base/'generated-code.sha256').read_bytes());names.append('generated-code.sha256')
 for f in sorted(set(names)):sync(OUT/f,(stage/f).read_bytes())
for name in ['maps','assets','scenarios','docs']:
 p=OUT/name
 if not p.exists():p.symlink_to(ROOT/name,target_is_directory=True)
p=OUT/'tests/fixtures'
if not p.exists():p.symlink_to(ROOT/'tests/fixtures',target_is_directory=True)
manifest=''.join(hashlib.sha256((OUT/f).read_bytes()).hexdigest()+'  '+f+'\n' for f in sorted(set(names)))
sync(OUT/'phase15e-generated-code.sha256',manifest.encode())
print(OUT)
