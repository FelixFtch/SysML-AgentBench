"""Verify packaged bytes. Rebuilds and new test output legitimately change hashes."""
from pathlib import Path
import hashlib, json, sys
root=Path(__file__).resolve().parent
manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
bad=[]
for item in manifest['files']:
 p=root/item['path']
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:
  bad.append(item['path'])
if bad:
 print('CHANGED/MISSING:',*bad,sep='\n');sys.exit(1)
print(f"OK: {len(manifest['files'])} files verified.")
