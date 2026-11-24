#!/usr/bin/env python3
"""
Verification suite for ui-ux-design-skill MVP.
Verifies:
1. Design tokens pass WCAG 2.2 AA contrast ratios.
2. Known-defect fixtures are caught with expected rule IDs.
3. Clean reference fixtures produce zero false positives.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "scripts" / "ui_ux_checker.py"
FIXTURES = ROOT / "tests" / "fixtures"


def run_checker(args):
    proc = subprocess.run(
        [sys.executable, str(CHECKER), *args, "--json"],
        capture_output=True,
        text=True,
    )
    return proc.returncode, json.loads(proc.stdout)


def main():
    failures = []

    # 1. Token self-check
    rc, res = run_checker(["--check-tokens", str(ROOT / "tokens" / "design-tokens.json")])
    if rc != 0 or res["blocker_count"] != 0:
        failures.append(f"Token check failed: {res}")
    else:
        print("[PASS] design-tokens.json: All WCAG 2.2 AA pairs verified.")

    # 2. Defect detection tests
    cases = [
        ("01_blocker_contrast.html", {"B-03", "B-05", "M-W2"}),
        ("02_blocker_destructive.html", {"B-05"}),
        ("03_blocker_form_a11y.html", {"B-04", "B-05", "M-W5"}),
        ("04_blocker_doc_scan.md", {"B-07", "M-D3", "M-D4"}),
    ]
    for fname, expected_rules in cases:
        _, res = run_checker([str(FIXTURES / fname)])
        found_rules = {f["rule_id"] for f in res["findings"]}
        missing = expected_rules - found_rules
        if missing:
            failures.append(f"{fname}: Missing expected rules {missing} (found: {found_rules})")
        else:
            print(f"[PASS] {fname}: Detected {sorted(found_rules)}")

    # 3. Clean reference tests (Zero false positives)
    for fname in ("05_clean_web.html", "06_clean_doc.md"):
        rc, res = run_checker([str(FIXTURES / fname)])
        if rc != 0 or len(res["findings"]) != 0:
            failures.append(f"{fname}: Expected 0 findings, got {res['findings']}")
        else:
            print(f"[PASS] {fname}: 0 false positives.")

    if failures:
        print("\n--- TEST FAILURES ---")
        for f in failures:
            print("FAIL:", f)
        sys.exit(1)

    print("\nALL MVP VERIFICATION TESTS PASSED.")


if __name__ == "__main__":
    main()
