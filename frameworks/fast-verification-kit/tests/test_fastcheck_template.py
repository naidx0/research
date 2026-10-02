"""The template's selftest, run in a scratch copy so the repo stays clean."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "fastcheck_template.py"


class TemplateTest(unittest.TestCase):
    def test_selftest_passes_in_a_scratch_copy(self):
        d = Path(tempfile.mkdtemp(prefix="fastcheck-"))
        self.addCleanup(shutil.rmtree, d, True)
        shutil.copy(TEMPLATE, d)
        r = subprocess.run([sys.executable, "fastcheck_template.py", "selftest"], cwd=d,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("selftest ok", r.stdout)

    def test_check_runs_subjects_in_parallel(self):
        d = Path(tempfile.mkdtemp(prefix="fastcheck-"))
        self.addCleanup(shutil.rmtree, d, True)
        shutil.copy(TEMPLATE, d)
        subprocess.run([sys.executable, "fastcheck_template.py", "selftest"], cwd=d, capture_output=True)
        r = subprocess.run([sys.executable, "fastcheck_template.py", "check", "--jobs", "2"], cwd=d,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(r.stdout.strip().splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
