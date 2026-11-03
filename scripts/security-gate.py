"""Fail closed unless all security checks required for this scope succeeded."""

import json
import os


def validate(results, full_scan):
    scope = results["changes"]["outputs"]
    flags = {}
    for name in ("backend_code", "frontend_code", "dependencies", "containers"):
        value = scope[name]
        if value not in ("true", "false"):
            raise ValueError("Invalid security scope")
        flags[name] = full_scan or value == "true"
    required = {
        "changes": True,
        "secrets": True,
        "dependency-audit": flags["dependencies"],
        "backend-tests": flags["backend_code"],
        "frontend-tests": flags["frontend_code"] or flags["dependencies"],
        "codeql-python": flags["backend_code"],
        "codeql-javascript": flags["frontend_code"],
        "container-security": flags["containers"],
        "installed-stack": flags["backend_code"] or flags["containers"],
    }
    for name, applicable in required.items():
        result = results[name]["result"]
        if result != "success" and (applicable or result != "skipped"):
            raise ValueError(f"Required security check did not pass: {name} ({result})")


if __name__ == "__main__":
    try:
        flag = os.environ["FULL_SCAN"]
        if flag not in ("true", "false"):
            raise ValueError("Invalid full-scan flag")
        validate(json.loads(os.environ["RESULTS"]), flag == "true")
    except (KeyError, TypeError, ValueError) as error:
        raise SystemExit(f"Security gate blocked: {error}") from None
    print("All applicable security and regression checks passed.")
