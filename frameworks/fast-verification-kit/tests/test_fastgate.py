"""fastgate on a throwaway project: cache keys, verdicts, exactness and the A/B gate."""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FASTGATE = ROOT / "fastgate.py"
spec = importlib.util.spec_from_file_location("fastgate", FASTGATE)
fastgate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fastgate)

PASS_A = "import unittest\nimport lib\nclass A(unittest.TestCase):\n    def test_one(self):\n        self.assertEqual(lib.two(), 2)\n"
PASS_B = "import unittest\nclass B(unittest.TestCase):\n    def test_two(self):\n        self.assertTrue(True)\n    @unittest.skip('no')\n    def test_skipped(self):\n        pass\n"
FAIL_C = "import unittest\nclass C(unittest.TestCase):\n    def test_bad(self):\n        self.assertEqual(1, 2)\n"


class Project:
    def __init__(self, files):
        self.dir = Path(tempfile.mkdtemp(prefix="fastgate-"))
        for rel, text in files.items():
            self.write(rel, text)

    def write(self, rel, text):
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode())

    def gate(self, **kw):
        args = dict(runner="unittest", jobs=2, fresh=False, excludes=[], env_names=[])
        args.update(kw)
        return fastgate.gate(self.dir, (self.dir / "tests").resolve(), **args)

    def cli(self, *args):
        return subprocess.run([sys.executable, str(FASTGATE), *args, "--root", str(self.dir)],
                              capture_output=True, text=True)

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def passing():
    return Project({"lib.py": "def two():\n    return 2\n",
                    "tests/test_a.py": PASS_A, "tests/test_b.py": PASS_B})


class GateTest(unittest.TestCase):
    def setUp(self):
        self.p = passing()
        self.addCleanup(self.p.close)

    def test_pass_counts_every_test(self):
        r = self.p.gate()
        self.assertEqual(r["verdict"], "PASS")
        self.assertEqual(r["tests"], 3)
        self.assertEqual(r["counts"], {"passed": 2, "skipped": 1})
        self.assertEqual(r["files_rerun"], 2)

    def test_unchanged_tree_is_served_from_cache(self):
        self.p.gate()
        r = self.p.gate()
        self.assertEqual(r["files_rerun"], 0)
        self.assertEqual(r["verdict"], "PASS")

    def test_fresh_ignores_cache(self):
        self.p.gate()
        self.assertEqual(self.p.gate(fresh=True)["files_rerun"], 2)

    def test_editing_one_test_file_reruns_only_that_file(self):
        self.p.gate()
        self.p.write("tests/test_b.py", PASS_B + "# edited\n")
        self.assertEqual(self.p.gate()["files_rerun"], 1)

    def test_editing_source_reruns_every_file(self):
        self.p.gate()
        self.p.write("lib.py", "def two():\n    return 2  # edited\n")
        self.assertEqual(self.p.gate()["files_rerun"], 2)

    def test_env_var_named_by_env_is_in_the_key(self):
        import os
        self.p.gate(env_names=["FASTGATE_TEST_VAR"])
        os.environ["FASTGATE_TEST_VAR"] = "changed"
        self.addCleanup(os.environ.pop, "FASTGATE_TEST_VAR", None)
        self.assertEqual(self.p.gate(env_names=["FASTGATE_TEST_VAR"])["files_rerun"], 2)

    def test_excluded_path_does_not_invalidate(self):
        self.p.gate(excludes=["runs/"])
        self.p.write("runs/out.txt", "new output")
        self.assertEqual(self.p.gate(excludes=["runs/"])["files_rerun"], 0)

    def test_serial_glob_still_runs_the_file(self):
        r = self.p.gate(serial=["tests/test_a.py"])
        self.assertEqual(r["verdict"], "PASS")
        self.assertEqual(r["tests"], 3)


class FailureTest(unittest.TestCase):
    def setUp(self):
        self.p = passing()
        self.p.write("tests/test_c.py", FAIL_C)
        self.addCleanup(self.p.close)

    def test_failing_test_fails_the_gate(self):
        r = self.p.gate()
        self.assertEqual(r["verdict"], "FAIL")
        self.assertEqual(r["counts"].get("failed"), 1)

    def test_failures_are_cached(self):
        self.p.gate()
        r = self.p.gate()
        self.assertEqual((r["verdict"], r["files_rerun"]), ("FAIL", 0))

    def test_retry_failed_reruns_only_cached_failures(self):
        self.p.gate()
        self.assertEqual(self.p.gate(retry_failed=True)["files_rerun"], 1)

    def test_syntax_error_is_rejected_before_any_test_runs(self):
        self.p.write("lib.py", "def two(:\n")
        r = self.p.gate()
        self.assertEqual((r["verdict"], r["tier"]), ("FAIL", "static"))
        self.assertIn("lib.py", r["errors"][0])

    def test_import_error_is_an_error_not_a_pass(self):
        self.p.write("tests/test_d.py", "import no_such_module_here\n")
        r = self.p.gate()
        self.assertEqual(r["verdict"], "FAIL")
        self.assertEqual(r["counts"].get("error"), 1)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.p = passing()
        self.addCleanup(self.p.close)

    def test_run_exit_code_follows_verdict(self):
        ok = self.p.cli("run")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(json.loads(ok.stdout)["verdict"], "PASS")
        self.p.write("tests/test_c.py", FAIL_C)
        self.assertEqual(self.p.cli("run").returncode, 1)

    def test_equal_matches_the_serial_run(self):
        self.p.write("tests/test_c.py", FAIL_C)
        r = self.p.cli("equal")
        out = json.loads(r.stdout)
        self.assertEqual(out["verdict"], "EXACT", out)
        self.assertEqual(out["tests"], 4)


@unittest.skipUnless(importlib.util.find_spec("pytest"), "pytest not installed")
class PytestRunnerTest(unittest.TestCase):
    def test_all_skipped_file_passes(self):
        p = Project({"tests/test_s.py": "import pytest\n@pytest.mark.skip\ndef test_x():\n    pass\n",
                     "tests/test_ok.py": "def test_y():\n    assert True\n"})
        self.addCleanup(p.close)
        r = p.gate(runner="pytest")
        self.assertEqual(r["verdict"], "PASS", r)
        self.assertEqual(r["counts"], {"passed": 1, "skipped": 1})


class PairedGateTest(unittest.TestCase):
    base = {f"i{n}": {"score": 0.5, "g": n // 2} for n in range(20)}

    def cand(self, delta):
        return {k: dict(v, score=v["score"] + delta(int(k[1:]))) for k, v in self.base.items()}

    def test_consistent_gain_is_accepted(self):
        r = fastgate.paired_gate(self.base, self.cand(lambda n: 0.1 + 0.01 * (n % 3)), "g")
        self.assertEqual(r["verdict"], "ACCEPT")
        self.assertEqual(r["groups"], 10)

    def test_consistent_loss_is_rejected(self):
        self.assertEqual(fastgate.paired_gate(self.base, self.cand(lambda n: -0.1), "g")["verdict"], "REJECT")

    def test_noise_is_unsure(self):
        r = fastgate.paired_gate(self.base, self.cand(lambda n: 0.1 if n % 4 < 2 else -0.1), "g")
        self.assertEqual(r["verdict"], "UNSURE")

    def test_different_items_are_refused(self):
        cand = dict(self.base)
        cand.pop("i0")
        with self.assertRaises(SystemExit):
            fastgate.paired_gate(self.base, cand, "g")


if __name__ == "__main__":
    unittest.main()
