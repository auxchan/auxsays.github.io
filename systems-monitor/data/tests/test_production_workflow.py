import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _support import PACKAGE_ROOT


class ProductionWorkflowTests(unittest.TestCase):
    def test_validation_step_runs_every_command_from_its_required_directory(self):
        workflow = (PACKAGE_ROOT.parents[1] / ".github/workflows/systems-monitor-data.yml").read_text(encoding="utf-8")
        match = re.search(r"      - name: Validate data governance and UI consumption\n        run: \|\n((?:          .+\n)+)", workflow)
        self.assertIsNotNone(match)
        script = "\n".join(line[10:] for line in match[1].splitlines())
        bash = shutil.which("bash")
        if os.name == "nt":
            git = shutil.which("git")
            candidate = Path(git).parent.parent / "bin/bash.exe" if git else Path("")
            bash = str(candidate) if candidate.is_file() else bash
        self.assertIsNotNone(bash, "Git Bash or bash is required to execute the production workflow regression")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "systems-monitor/data/tests").mkdir(parents=True)
            (root / "systems-monitor/app").mkdir(parents=True)
            (root / "systems-monitor/app/package.json").write_text("{}", encoding="utf-8")
            # Function stubs validate paths and record invocations; the actual YAML
            # shell block runs unmodified, so a leaking `cd` fails the npm commands.
            harness = """set -euo pipefail
python() { test -d tests; printf 'python\\n' >> ../../calls.txt; }
npm() { test -f systems-monitor/app/package.json; printf '%s\\n' "$2" >> calls.txt; }
""" + script
            result = subprocess.run([bash, "--noprofile", "--norc", "-c", harness], cwd=root, text=True, capture_output=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(["python", "test", "build"], (root / "calls.txt").read_text().splitlines())
