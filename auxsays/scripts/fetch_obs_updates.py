#!/usr/bin/env python3
"""Legacy OBS entrypoint.

Kept so older manual workflows or local commands do not break. The actual updater
now lives in fetch_software_updates.py and reads auxsays/_data/patch_sources.yml.
"""
import os
import pathlib
import runpy

os.environ["AUXSAYS_ONLY"] = "obs-studio"
runpy.run_path(str(pathlib.Path(__file__).with_name("fetch_software_updates.py")), run_name="__main__")
