#!/usr/bin/env python3
"""Prove retained bytes and 15c's allowed additive paths; never reads credentials."""
from pathlib import Path
import subprocess,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2]
BASE='e4ba2a6e9555f99baec8dfaf1ea9c5a6a7766b50'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def allowed(name):return name.startswith(('experiments/phase15c/','assets/phase15c/','docs/phase-15c-','docs/gates/phase-15c-')) or name=='scripts/phase15c.sh'
def verify():
 files=git('ls-tree','-r','--name-only',BASE).decode().splitlines()
 rows=[]
 for f in files:
  expected=git('show',BASE+':'+f);actual=(ROOT/f).read_bytes()
  if expected!=actual:raise SystemExit('retained file changed: '+f)
  rows.append(hashlib.sha256(actual).hexdigest()+'  '+f)
 for line in git('diff','--name-status',BASE).decode().splitlines():
  status,name=line.split('\t',1)
  if status!='A' or not allowed(name):raise SystemExit('non-additive or unexpected change: '+line)
 for name in git('ls-files','--others','--exclude-standard').decode().splitlines():
  if not allowed(name):raise SystemExit('unexpected untracked path: '+name)
 for f in ['src/judge.rs','src/schema.rs','src/make_way.rs']:
  generated=Path('/tmp/malleable-phase15c-build')/f
  if generated.exists() and generated.read_bytes()!=(ROOT/f).read_bytes():raise SystemExit('generated protected source differs: '+f)
 if '--write-retained-manifest' in sys.argv:
  (ROOT/'assets/phase15c/retained-files.sha256').write_text('\n'.join(rows)+'\n')
 print(json.dumps({'base_commit':BASE,'retained_files':len(files),'byte_identical':True,'all_changes_additive_in_15c_paths':True,'generated_protected_sources_identical':True},sort_keys=True))
if __name__=='__main__':verify()
