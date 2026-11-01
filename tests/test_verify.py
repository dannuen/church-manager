"""B8: verify.py gives the tests at most 600 seconds; a timeout prints one FAIL line, not a traceback."""

import contextlib
import io
import subprocess
import unittest
from unittest import mock

import _support  # noqa: F401 - puts the repo root on sys.path
import verify


class RunTestsTimeoutTest(unittest.TestCase):
    def test_a_timeout_is_one_fail_line(self):
        seen = {}

        def too_slow(cmd, **kwargs):
            seen.update(kwargs)
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

        out = io.StringIO()
        with mock.patch.object(verify.subprocess, "run", too_slow), contextlib.redirect_stdout(out):
            ok = verify.Checks().run("All tests", verify.run_tests)
        self.assertFalse(ok)
        self.assertEqual(seen["timeout"], 600)
        printed = out.getvalue()
        last = printed.splitlines()[-1]
        self.assertTrue(last.startswith("FAIL  All tests: TimeoutExpired: "), printed)
        self.assertIn("timed out after 600 seconds", last)
        self.assertNotIn("Traceback", printed)


if __name__ == "__main__":
    unittest.main()
