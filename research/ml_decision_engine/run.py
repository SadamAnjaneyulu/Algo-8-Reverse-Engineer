"""Reproducible CLI; audit old evidence, run the study and retain failure state."""
from __future__ import annotations
import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
import time
import traceback
from pathlib import Path
import pandas as pd
from .dataset import HERE,ROOT,digest,build_dataset
from .models import train_models
from .quantities import run_quantities
from .first_passage import run_first_passage
from .replay import run_replay
from .reporting import summarize,write_report

PRIOR_REPORTS = [
 'STRONG_FINDINGS.md','ALLOCATION_ENTRY_EXIT_RISK_PLAYBOOK.md',
 'research/hypothesis_controller_search/HYPOTHESIS_CONTROLLER_SEARCH.md',
 'research/policy_execution_separation/POLICY_EXECUTION_RECONSTRUCTION.md',
 'research/intermediate_exit_study/INTERMEDIATE_EXIT_CONTROLLER.md',
 'research/final_alpha_attribution/FINAL_ALPHA_ATTRIBUTION_AND_FALSIFICATION.md',
]


def snapshot_evidence():
    paths=[ROOT/p for p in PRIOR_REPORTS]
    paths.extend(p for p in (ROOT/'research').rglob('*') if p.is_file() and HERE not in p.parents and '.cache' not in p.parts and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.bin'])
    paths.extend(p for p in (ROOT/'data/breeze').rglob('*') if p.is_file())
    paths.extend([ROOT/'Trades_GKOHNP140.csv',ROOT/'Info.txt'])
    return {str(p.relative_to(ROOT)):digest(p) for p in sorted(set(paths))}


def main():
    """Compatibility entry point: use the same resumable stage CLI."""
    from .stages import main as staged_main
    staged_main()


if __name__=="__main__":main()
