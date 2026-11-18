"""Immutable raw store + SQLite manifest. Nothing here ever holds credentials, headers or provider error bodies."""
import hashlib, json, os, sqlite3, tempfile
from datetime import datetime, timezone

SCHEMA = '''
CREATE TABLE IF NOT EXISTS tasks(task_id TEXT PRIMARY KEY, kind TEXT, und TEXT, expiry TEXT, strike INTEGER, right TEXT, from_day TEXT, to_day TEXT, tier INTEGER, priority INTEGER,
  params_json TEXT, status TEXT, attempts INTEGER DEFAULT 0, last_error TEXT, raw_relpath TEXT, raw_sha256 TEXT, response_rows INTEGER, updated_utc TEXT);
CREATE TABLE IF NOT EXISTS contract_days(kind TEXT, und TEXT, expiry TEXT, strike INTEGER, right TEXT, trade_day TEXT, status TEXT, source TEXT, task_id TEXT,
  normalized_relpath TEXT, normalized_sha256 TEXT, bars INTEGER, PRIMARY KEY(kind, und, expiry, strike, right, trade_day));
CREATE TABLE IF NOT EXISTS request_log(id INTEGER PRIMARY KEY AUTOINCREMENT, ts_utc TEXT, ist_day TEXT, task_id TEXT, outcome TEXT);
CREATE INDEX IF NOT EXISTS ix_tasks_status ON tasks(status, priority);
'''


def now_utc(): return datetime.now(timezone.utc).isoformat(timespec='seconds')


def sha256_bytes(b): return hashlib.sha256(b).hexdigest()


def canonical(obj): return (json.dumps(obj, sort_keys=True, separators=(',', ':')) + '\n').encode()


def write_once(path, content):
    """Atomic, write-once. Existing identical content: no-op. Existing different content: refuse (raw data is never overwritten)."""
    if os.path.exists(path):
        if open(path, 'rb').read() != content: raise FileExistsError(f'refusing to overwrite {path}')
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix='.tmp-'); 
    try:
        with os.fdopen(fd, 'wb') as f: f.write(content); f.flush(); os.fsync(f.fileno())
        os.chmod(tmp, 0o444); os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp): os.unlink(tmp)
        raise
    return True


class Store:
    def __init__(self, root):
        self.root = root; os.makedirs(root, exist_ok=True)
        self.db = sqlite3.connect(os.path.join(root, 'manifest.sqlite')); self.db.row_factory = sqlite3.Row; self.db.executescript(SCHEMA); self.db.commit()

    def path(self, *parts): return os.path.join(self.root, *parts)

    def add_task(self, t):
        self.db.execute('INSERT OR IGNORE INTO tasks(task_id,kind,und,expiry,strike,right,from_day,to_day,tier,priority,params_json,status,updated_utc) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (t['task_id'], t['kind'], t['und'], t.get('expiry'), t.get('strike'), t.get('right'), t['from_day'], t['to_day'], t['tier'], t['priority'], json.dumps(t['params'], sort_keys=True), 'PENDING', now_utc()))

    def set_task(self, task_id, **kw):
        cols = ', '.join(f'{k}=?' for k in kw) + ', updated_utc=?'
        self.db.execute(f'UPDATE tasks SET {cols} WHERE task_id=?', (*kw.values(), now_utc(), task_id))

    def pending(self, kinds=None, max_tier=None, limit=None, retry_failed=True):
        q = "SELECT * FROM tasks WHERE status IN ('PENDING'" + (",'FAILED_RETRYABLE'" if retry_failed else '') + ')'
        a = []
        if kinds: q += ' AND kind IN (%s)' % ','.join('?' * len(kinds)); a += list(kinds)
        if max_tier is not None: q += ' AND tier<=?'; a.append(max_tier)
        q += ' ORDER BY tier, priority, task_id' + (f' LIMIT {int(limit)}' if limit else '')
        return [dict(r) for r in self.db.execute(q, a)]

    def set_day(self, key, **kw):
        k = ('kind', 'und', 'expiry', 'strike', 'right', 'trade_day')
        vals = [key[c] for c in k] + [kw.get(c) for c in ('status', 'source', 'task_id', 'normalized_relpath', 'normalized_sha256', 'bars')]
        self.db.execute('INSERT OR REPLACE INTO contract_days VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', vals)

    def day_status(self, key):
        r = self.db.execute('SELECT status FROM contract_days WHERE kind=? AND und=? AND expiry IS ? AND strike IS ? AND right IS ? AND trade_day=?', [key[c] for c in ('kind', 'und', 'expiry', 'strike', 'right', 'trade_day')]).fetchone()
        return r[0] if r else None

    def log_request(self, task_id, outcome, ist_day):
        self.db.execute('INSERT INTO request_log(ts_utc,ist_day,task_id,outcome) VALUES(?,?,?,?)', (now_utc(), ist_day, task_id, outcome)); self.db.commit()

    def requests_today(self, ist_day): return self.db.execute('SELECT COUNT(*) FROM request_log WHERE ist_day=?', (ist_day,)).fetchone()[0]

    def commit(self): self.db.commit()

    def counts(self):
        return {r[0]: r[1] for r in self.db.execute('SELECT status, COUNT(*) FROM tasks GROUP BY status')}
