"""Exercise fail-closed security policy with synthetic workflow results."""

import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("gate", Path(__file__).with_name("security-gate.py"))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class GateTests(unittest.TestCase):
    def fixture(self, scoped=False):
        names = (
            "changes",
            "secrets",
            "dependency-audit",
            "backend-tests",
            "frontend-tests",
            "codeql-python",
            "codeql-javascript",
            "container-security",
        )
        result = {name: {"result": "success"} for name in names}
        result["changes"]["outputs"] = dict.fromkeys(
            ("backend_code", "frontend_code", "dependencies", "containers"),
            "false" if scoped else "true",
        )
        if scoped:
            for name in names[2:]:
                result[name]["result"] = "skipped"
        return result

    def test_full_scan_success(self):
        gate.validate(self.fixture(), True)

    def test_only_irrelevant_checks_may_be_skipped(self):
        result = self.fixture(scoped=True)
        gate.validate(result, False)
        with self.assertRaises(ValueError):
            gate.validate(result, True)

    def test_every_required_check_blocks_on_failure_cancel_or_skip(self):
        for name in self.fixture():
            for status in ("failure", "cancelled", "skipped", "unknown"):
                result = self.fixture()
                result[name]["result"] = status
                with self.subTest(name=name, status=status), self.assertRaises(ValueError):
                    gate.validate(result, True)

    def test_missing_results_or_invalid_scope_are_rejected(self):
        result = self.fixture()
        del result["container-security"]
        with self.assertRaises(KeyError):
            gate.validate(result, True)
        result = self.fixture()
        result["changes"]["outputs"]["containers"] = ""
        with self.assertRaises(ValueError):
            gate.validate(result, True)

    def test_dependency_scope_requires_audit_and_frontend_regression(self):
        result = self.fixture(scoped=True)
        result["changes"]["outputs"]["dependencies"] = "true"
        result["dependency-audit"]["result"] = "success"
        with self.assertRaises(ValueError):
            gate.validate(result, False)
        result["frontend-tests"]["result"] = "success"
        gate.validate(result, False)


if __name__ == "__main__":
    unittest.main()
