"""Records the sha256 of tp03/config.yaml in tp03/config.sha256 (run once, when the configuration is frozen)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp03_common as c
open(c.FREEZE_PATH, 'w').write(f'{c.config_sha256()}  config.yaml\n'); print(c.config_sha256())
