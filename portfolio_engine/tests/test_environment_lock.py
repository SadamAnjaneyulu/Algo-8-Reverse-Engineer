"""M2-F E-D09: requirements.lock.txt must exist and pin (==) every third-party package that the project's Python files import.
FAILS: lock file missing; a third-party import without an `==` pin; pandas.read_parquet in use but pyarrow not pinned; the python/g++ comments missing.
REPORTS ONLY (UserWarning, never a failure): a pinned version differs from the one installed here, or a pinned package is not installed (the lock records the reference environment, see docs/ENVIRONMENT.md)."""
import ast, importlib.metadata as md, os, re, sys, warnings
import pytest
from conftest import PE

LOCK = os.path.join(PE, 'requirements.lock.txt')
EXTERNAL_NOT_ON_PYPI = {'market_data'}               # tools/select_demo_cycles.py: raw-bar loader outside this repository (documented in the lock file and docs/ENVIRONMENT.md); not pinnable
IMPORT_TO_DIST = {'yaml': 'pyyaml', 'PIL': 'pillow', 'dateutil': 'python-dateutil'}
SKIP_DIRS = {'__pycache__', 'build', 'runs', 'data_generated', 'reports', '.pytest_cache'}


def norm(n): return re.sub(r'[-_.]+', '-', n).lower()


def parse_lock(path):
    assert os.path.isfile(path), f'{path} is missing (M2-F E-D09: environment must be pinned)'
    pins, comments = {}, []
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        if line.startswith('#'): comments.append(line); continue
        m = re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9._+!-]*)', line); assert m, f'lock line is not an exact `name==version` pin: {line!r}'
        assert norm(m.group(1)) not in pins, f'duplicate pin {m.group(1)}'; pins[norm(m.group(1))] = m.group(2)
    return pins, comments


def project_imports(pe_root):
    """third-party top-level modules imported anywhere in portfolio_engine/{python,tools,tests} (stdlib and project-local modules excluded) -> files importing them; and whether read_parquet is called"""
    local = {'pe'}; files = []
    for sub in ('python', 'tools', 'tests'):
        for d, dirs, names in os.walk(os.path.join(pe_root, sub)):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
            for n in names:
                if n.endswith('.py'): files.append(os.path.join(d, n)); local.add(n[:-3])
            local |= {x for x in dirs}
    third, parquet = {}, False
    for p in files:
        src = open(p, encoding='utf-8').read(); parquet |= 'read_parquet' in src
        for n in ast.walk(ast.parse(src)):
            mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module] if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module else []
            for m in mods:
                t = m.split('.')[0]
                if t not in sys.stdlib_module_names and t not in local: third.setdefault(t, set()).add(os.path.relpath(p, pe_root))
    return third, parquet


def check(lock_path, pe_root):
    """returns (differences to report); raises AssertionError for the failing conditions"""
    pins, comments = parse_lock(lock_path); third, parquet = project_imports(pe_root)
    assert any(c.startswith('# python:') for c in comments) and any(c.startswith('# g++:') for c in comments), 'lock file must record the python and g++ versions as comments'
    need = {t: norm(IMPORT_TO_DIST.get(t, t)) for t in third if t not in EXTERNAL_NOT_ON_PYPI}
    if parquet: need['(pandas.read_parquet)'] = 'pyarrow'
    missing = sorted(f'{t} -> {d}' for t, d in need.items() if d not in pins)
    assert not missing, f'imported third-party packages without an exact pin in {os.path.basename(lock_path)}: {missing}'
    diffs = []
    for name, ver in sorted(pins.items()):
        try: have = md.version(name)
        except md.PackageNotFoundError: diffs.append(f'{name}: pinned {ver}, NOT INSTALLED'); continue
        if have != ver: diffs.append(f'{name}: pinned {ver}, installed {have}')
    return diffs


def test_lock_file_pins_every_imported_third_party_package_and_reports_version_differences():
    diffs = check(LOCK, PE)
    for d in diffs: warnings.warn(f'environment differs from requirements.lock.txt: {d}', UserWarning)


def test_the_check_itself_fails_for_a_missing_lock_a_missing_pin_and_a_loose_pin(tmp_path):
    pe = tmp_path / 'pe'; (pe / 'python').mkdir(parents=True); (pe / 'tools').mkdir(); (pe / 'tests').mkdir()
    (pe / 'tools' / 't.py').write_text('import os, json\nimport numpy as np\nfrom pandas import DataFrame\nimport t\nimport market_data\n'); (pe / 'tests' / 'x.py').write_text('import dateutil.parser\n')
    with pytest.raises(AssertionError, match='is missing'): check(str(tmp_path / 'nope.txt'), str(pe))
    head = '# python: 3.13\n# g++: 13\n'
    lock = tmp_path / 'l.txt'
    lock.write_text(head + 'numpy==2.5.3\n'); (pe / 'tools' / 'u.py').write_text('x = 1\n')
    with pytest.raises(AssertionError, match=r"dateutil -> python-dateutil.*pandas -> pandas"): check(str(lock), str(pe))     # pandas and dateutil imported, not pinned; local module `t` and external market_data ignored
    lock.write_text(head + 'numpy>=2\npandas==3.0.5\npython-dateutil==2.9.0\n')
    with pytest.raises(AssertionError, match='not an exact'): check(str(lock), str(pe))
    lock.write_text('numpy==2.5.3\npandas==3.0.5\npython-dateutil==2.9.0\n')
    with pytest.raises(AssertionError, match='python and g\\+\\+ versions'): check(str(lock), str(pe))
    lock.write_text(head + 'numpy==2.5.3\npandas==3.0.5\npython-dateutil==2.9.0\n'); assert isinstance(check(str(lock), str(pe)), list)     # complete; differences are only reported
    (pe / 'tools' / 'u.py').write_text('import pandas as pd\npd.read_parquet("a")\n')
    with pytest.raises(AssertionError, match=r'pandas.read_parquet\) -> pyarrow'): check(str(lock), str(pe))
    lock.write_text(head + 'numpy==2.5.3\npandas==3.0.5\npython-dateutil==2.9.0\nPyArrow==26.0.1\n'); check(str(lock), str(pe))


def test_the_real_tree_third_party_imports_are_exactly_the_documented_set():
    third, parquet = project_imports(PE)
    assert set(third) == {'numpy', 'pandas', 'matplotlib', 'pytest', 'market_data'} and parquet       # a NEW third-party import must be added to the lock and to docs/ENVIRONMENT.md deliberately
