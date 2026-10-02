import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


class Layout(unittest.TestCase):
    def test_arloop_copies_match(self):
        home = (ROOT / "frameworks/arloop/arloop.py").read_bytes()
        skill = (ROOT / "skills/research-loop/scripts/arloop.py").read_bytes()
        self.assertEqual(home, skill)

    def test_arloop_selftest_passes(self):
        out = subprocess.run(
            [sys.executable, str(ROOT / "frameworks/arloop/arloop.py"), "selftest"],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout.strip().splitlines()[-1])["selftest"], "PASS")

    def test_every_skill_has_a_skill_md(self):
        skills = [p for p in (ROOT / "skills").iterdir() if p.is_dir()]
        self.assertTrue(skills)
        for p in skills:
            self.assertTrue((p / "SKILL.md").is_file(), p.name)

    def test_every_framework_has_a_readme(self):
        frameworks = [p for p in (ROOT / "frameworks").iterdir() if p.is_dir()]
        self.assertTrue(frameworks)
        for p in frameworks:
            self.assertTrue((p / "README.md").is_file(), p.name)

    def test_fast_verification_kit_tests_pass(self):
        kit = ROOT / "frameworks/fast-verification-kit"
        out = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            capture_output=True, text=True, cwd=kit,
        )
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])

    def test_four_asserts_tests_pass(self):
        out = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            capture_output=True, text=True, cwd=ROOT / "frameworks/four-asserts",
        )
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])

    def test_pages_root_points_at_the_inspector(self):
        page = (ROOT / "frameworks/executed-pivots/inspector/index.html").read_text(encoding="utf-8")
        self.assertIn("Pivot Inspector", page)
        self.assertIn("frameworks/executed-pivots/inspector/", (ROOT / "index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
