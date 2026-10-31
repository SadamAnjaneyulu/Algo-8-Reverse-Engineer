"""Atomic, hash-verified checkpoints bound to inputs, protocol and model code.

Only checkpoints produced by this trusted repository workflow may be loaded:
pickle model/data checkpoints are executable Python objects, not public inputs.
"""
from __future__ import annotations
import hashlib
import json
import os
import pickle
import tempfile
from pathlib import Path


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def atomic_bytes(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def atomic_json(path,value):
    atomic_bytes(path,(json.dumps(value,indent=2,sort_keys=True,default=str)+'\n').encode())


def atomic_frame(frame,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.stem+'.tmp'+path.suffix)
    if path.suffix=='.parquet':frame.to_parquet(tmp,index=False)
    else:frame.to_csv(tmp,index=False)
    os.replace(tmp,path)


class CheckpointStore:
    def __init__(self,out,signature):
        self.out=Path(out);self.root=self.out/'checkpoints';self.root.mkdir(parents=True,exist_ok=True)
        self.signature=signature

    def load(self,key):
        folder=self.root/key;marker=folder/'complete.json'
        if not marker.exists():return None
        info=json.loads(marker.read_text())
        if info['signature']!=self.signature:
            raise RuntimeError(f'Checkpoint signature mismatch: {key}; refusing stale reuse')
        for name,digest in info['files'].items():
            path=self.out/name
            if not path.is_file() or sha(path)!=digest:
                raise RuntimeError(f'Checkpoint missing/corrupt: {key}: {name}')
        with (folder/'payload.pkl').open('rb') as f:return pickle.load(f)

    def save(self,key,payload,dependencies=()):
        folder=self.root/key;folder.mkdir(parents=True,exist_ok=True)
        p=folder/'payload.pkl';atomic_bytes(p,pickle.dumps(payload,protocol=5))
        files=[p]+[Path(x) for x in dependencies]
        hashes={str(x.relative_to(self.out)):sha(x) for x in files}
        # Marker is committed last. A torn payload is never treated as complete.
        atomic_json(folder/'complete.json',{'signature':self.signature,'files':hashes})


def runtime_signature(protocol,input_sha,modules,extra=None):
    import importlib.metadata
    packages={x:importlib.metadata.version(x) for x in ['numpy','pandas','scikit-learn','lightgbm','catboost','interpret-core','pyarrow']}
    payload={'protocol':protocol,'input_sha256':input_sha,
             'code':{Path(p).name:sha(p) for p in modules},'packages':packages,'extra':extra}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()


def publish_partial(out,stage,completed,expected,metrics=None):
    out=Path(out)
    atomic_json(out/'partial_progress.json',dict(stage=stage,completed_units=completed,expected_units=expected,
        status='complete' if completed==expected else 'partial',final_assessment=False))
    text=['# Partial ML research report','',f'Stage: {stage}. Completed units: {completed}/{expected}.','',
          'These are saved partial results. No final 75% assessment, autonomous-policy recovery or stop/target identification is claimed. Whole-cycle splits and the registered standards are unchanged.','']
    if metrics is not None and len(metrics):text+=['```csv',metrics.to_csv(index=False),'```']
    atomic_bytes(out/'PARTIAL_RESEARCH_REPORT.md',('\n'.join(text)+'\n').encode())
