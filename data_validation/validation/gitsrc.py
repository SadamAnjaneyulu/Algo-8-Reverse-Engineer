"""Read-only access to a dataset at a pinned commit through git objects (nothing is checked out, nothing can be modified)."""
import hashlib, subprocess, io
REPO_DEFAULT = '/home/user/Algo-8-Reverse-Engineer'


class GitSource:
    def __init__(self, commit, repo=REPO_DEFAULT, prefix='data/market_context_3yr_broad'):
        self.repo, self.prefix = repo, prefix.rstrip('/')
        self.commit = self._git('rev-parse', '--verify', commit + '^{commit}').decode().strip()
        self._tree = None

    def _git(self, *a, input=None):
        return subprocess.run(['git', '-C', self.repo, *a], check=True, capture_output=True, input=input).stdout

    def tree(self):
        """{relative path: (blob sha, size)} for every file under the dataset prefix."""
        if self._tree is None:
            out = self._git('ls-tree', '-r', '-l', '-z', self.commit, self.prefix + '/').decode(); t = {}
            for rec in out.split('\0'):
                if not rec: continue
                meta, path = rec.split('\t', 1); mode, typ, sha, size = meta.split()
                t[path[len(self.prefix) + 1:]] = (sha, int(size))
            self._tree = t
        return self._tree

    def read(self, rel): return self._git('cat-file', 'blob', self.tree()[rel][0])

    def text(self, rel): return self.read(rel).decode('utf-8')

    def sha256(self, rel): return hashlib.sha256(self.read(rel)).hexdigest()

    def stream(self, rel): return io.BytesIO(self.read(rel))
