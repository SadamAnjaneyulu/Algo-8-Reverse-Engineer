"""The commands and snippets shown in 04_Documentation/02_How_To_Run_and_Add_a_Plugin.docx are real: this test runs them."""
import os, subprocess, sys
import pytest
from helpers import *
from pc import generators as G
from pc._m2 import M2_PATH

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPECTED = 't+600s  flatten_leg proposed CUT B1:WPE qty 195 -> ACCEPTED'


def test_shipped_scenario_files_are_exactly_what_the_generators_write():
    names = sorted(f[:-4] for f in os.listdir(os.path.join(ROOT, 'scenarios')) if f.endswith('.scn'))
    assert names == sorted(G.all_scenarios())
    for n in names: assert open(os.path.join(ROOT, 'scenarios', n + '.scn'), encoding='ascii', newline='').read() == G.all_scenarios()[n].to_text(), n


def test_python_add_a_plugin_example_runs():
    r = subprocess.run([sys.executable, '-S', os.path.join(ROOT, 'examples', 'add_a_plugin.py')], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, PYTHONPATH=os.path.join(ROOT, 'python')))
    assert r.returncode == 0 and r.stdout.strip() == EXPECTED, (r.stdout, r.stderr[-300:])


def test_cpp_add_a_plugin_example_builds_and_runs(tmp_path):
    exe = tmp_path / 'add_a_plugin'
    b = subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-I', os.path.join(ROOT, 'cpp', 'include'), '-I', os.path.join(os.path.dirname(M2_PATH), 'cpp', 'include'), os.path.join(ROOT, 'examples', 'add_a_plugin.cpp'), '-o', str(exe)], capture_output=True, text=True)
    assert b.returncode == 0 and b.stderr.strip() == '', b.stderr[-500:]
    r = subprocess.run([str(exe)], capture_output=True, text=True, cwd=ROOT); assert r.returncode == 0 and r.stdout.strip() == EXPECTED, (r.stdout, r.stderr)
