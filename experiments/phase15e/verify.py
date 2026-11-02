#!/usr/bin/env python3
from pathlib import Path
import hashlib,subprocess,json,sys
ROOT=Path(__file__).resolve().parents[2];BASE='e4ba2a6e9555f99baec8dfaf1ea9c5a6a7766b50'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
retained=git('ls-tree','-r','--name-only',BASE).decode().splitlines();rows=[]
for f in retained:
 b=(ROOT/f).read_bytes();original=git('show',BASE+':'+f)
 if b!=original:raise SystemExit('retained bytes changed: '+f)
 rows.append(hashlib.sha256(b).hexdigest()+'  '+f)
after='\n'.join(rows)+'\n';before=(ROOT/'assets/phase15e/retained-before.sha256').read_text()
if before!=after:raise SystemExit('before/after SHA lists differ')
if '--write-after' in sys.argv:(ROOT/'assets/phase15e/retained-after.sha256').write_text(after)
allowed=lambda f:f.startswith(('experiments/phase15e/','assets/phase15e/','scripts/phase15e','maps/us101.'))
for line in git('diff','--name-status',BASE).decode().splitlines():
 status,f=line.split('\t',1)
 if status!='A' or not allowed(f):raise SystemExit('unexpected retained change/new path: '+line)
for f in git('ls-files','--others','--exclude-standard').decode().splitlines():
 if not allowed(f):raise SystemExit('unexpected new path: '+f)
for f in ['src/judge.rs','src/schema.rs','src/make_way.rs','src/osm.rs']:
 p=Path('/tmp/malleable-phase15e-build')/f
 if p.exists() and p.read_bytes()!=(ROOT/f).read_bytes():raise SystemExit('generated protected/default importer file changed: '+f)
print(json.dumps({'base_commit':BASE,'retained_files':len(retained),'before_after_sha_lists_equal':True,'all_retained_bytes_equal_git':True,'all_changes_are_new_15e_paths':True,'generated_judge_schema_make_way_default_osm_unchanged':True},sort_keys=True))
