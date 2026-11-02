#!/usr/bin/env python3
"""Reuse the retained v2 build, then add the isolated 15c observer/gate."""
from pathlib import Path
import hashlib, subprocess, shutil
ROOT=Path(__file__).resolve().parents[2]
OUT=Path('/tmp/malleable-phase15c-build')
BASE='e4ba2a6e9555f99baec8dfaf1ea9c5a6a7766b50'
# Retained inputs must not have been edited, staged or unstaged.
retained=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],cwd=ROOT,text=True).splitlines()
for f in retained:
 expected=subprocess.check_output(['git','show',BASE+':'+f],cwd=ROOT)
 if (ROOT/f).read_bytes()!=expected:raise SystemExit('retained file changed: '+f)
build=Path(subprocess.check_output(['python3','experiments/phase15-v2/materialize.py'],cwd=ROOT,text=True).strip())
def sync(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 if not path.exists() or path.read_bytes()!=data:path.write_bytes(data)
files=[line.split('  ',1)[1] for line in (build/'generated-code.sha256').read_text().splitlines()]
for name in files:
 data=(build/name).read_bytes()
 if name=='Cargo.toml':data=data.replace(b'phase15_v2_gate',b'phase15c_gate')
 if name=='src/rush_hour.rs':data+=b'\ninclude!("phase15c_runner.rs");\n'
 sync(OUT/name,data)
for source,target in [('gate.rs','examples/phase15c_gate.rs'),('runner.rs','src/phase15c_runner.rs'),('tests.rs','tests/phase15c.rs')]:
 sync(OUT/target,(ROOT/'experiments/phase15c'/source).read_bytes())
for name in ['maps','assets','scenarios','docs']:
 p=OUT/name
 if not p.exists():p.symlink_to(ROOT/name,target_is_directory=True)
p=OUT/'tests/fixtures'
if not p.exists():p.symlink_to(ROOT/'tests/fixtures',target_is_directory=True)
sync(OUT/'generated-code.sha256',(build/'generated-code.sha256').read_bytes())
files+=['generated-code.sha256','examples/phase15c_gate.rs','src/phase15c_runner.rs','tests/phase15c.rs']
manifest=''.join(hashlib.sha256((OUT/f).read_bytes()).hexdigest()+'  '+f+'\n' for f in sorted(set(files)))
sync(OUT/'phase15c-generated-code.sha256',manifest.encode())
print(OUT)
