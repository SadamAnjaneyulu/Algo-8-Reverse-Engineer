import hashlib, subprocess, io
from . import config as C


class Src:
    def __init__(self, commit=C.DATA_COMMIT, repo='/home/user/Algo-8-Reverse-Engineer', prefix=C.DATA_PREFIX):
        self.repo, self.prefix = repo, prefix
        out = subprocess.run(['git', '-C', repo, 'ls-tree', '-r', '-z', commit, prefix + '/normalized/'], check=True, capture_output=True).stdout.decode()
        self.tree = {}
        for rec in out.split('\0'):
            if rec: meta, path = rec.split('\t', 1); self.tree[path[len(prefix) + 1:]] = meta.split()[2]

    def read(self, rel): return subprocess.run(['git', '-C', self.repo, 'cat-file', 'blob', self.tree[rel]], check=True, capture_output=True).stdout

    def csv(self, rel):
        import pandas as pd
        return pd.read_csv(io.BytesIO(self.read(rel)))
