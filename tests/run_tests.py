#!/usr/bin/env python3
"""
Comprehensive unittest suite for ui-ux-design-skill v1.2.
Covers:
1. Design tokens WCAG 2.2 AA verification & JSON <-> CSS synchronization.
2. Reference integrity across all Markdown files (zero dangling IDs).
3. Multi-theme CSS variable scoping, rgba/hex8/shorthand, external CSS, coverage reporting.
4. Line number accuracy & false-positive guards (:focus:not(:focus-visible), ~~~ fences, *** HR).
5. Self-application test: package's own Markdown files produce 0 findings.
"""

import json
import re
import subprocess
import sys
import unittest
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
    if proc.returncode == 2:
        return proc.returncode, {"stderr": proc.stderr}
    return proc.returncode, json.loads(proc.stdout)


class TestUIUXSkillV12(unittest.TestCase):
    def test_01_design_tokens_verified_and_synced_with_css(self):
        token_json = ROOT / "tokens" / "design-tokens.json"
        token_css = ROOT / "tokens" / "design-tokens.css"
        rc, res = run_checker(["--check-tokens", str(token_json)])
        self.assertEqual(rc, 0, res)
        self.assertEqual(res["blocker_count"], 0)
        self.assertGreaterEqual(res["coverage"]["evaluated"], 40)

        # Verify every color in JSON light/dark exists in design-tokens.css
        data = json.loads(token_json.read_text(encoding="utf-8"))
        css_text = token_css.read_text(encoding="utf-8")
        for theme in ("light", "dark"):
            for key, val in data["colors"][theme].items():
                self.assertIn(f"--{key}: {val};", css_text, f"Missing {theme} --{key} in design-tokens.css")

    def test_02_multi_theme_focus_and_a11y_adversarial(self):
        rc, res = run_checker([str(FIXTURES / "01_multi_theme_contrast.html")])
        self.assertEqual(rc, 1)
        rules = [f["rule_id"] for f in res["findings"]]
        # Light theme fails BLK-03 while dark theme passes -> exactly 1 BLK-03
        self.assertEqual(rules.count("BLK-03"), 1, res["findings"])
        self.assertIn("theme:default", [f["target"] for f in res["findings"] if f["rule_id"] == "BLK-03"][0])
        # a:focus (border:0), .btn:focus-visible (transparent shadow), empty img link, div onclick w/o key handler = 4 BLK-05
        self.assertEqual(rules.count("BLK-05"), 4, res["findings"])
        # .icon-btn min-height/min-width 18px -> CHK-W2
        self.assertEqual(rules.count("CHK-W2"), 1, res["findings"])

    def test_03_rgba_hex8_shorthand_line_numbers_and_coverage(self):
        rc, res = run_checker([str(FIXTURES / "02_rgba_hsl_ext.css"), "--strict-tokens"])
        self.assertEqual(rc, 1)
        blk3 = [f for f in res["findings"] if f["rule_id"] == "BLK-03"]
        self.assertEqual(len(blk3), 3, blk3)
        # Verify exact line numbers (line 1, line 2, line 3 — no off-by-one!)
        targets = [f["target"] for f in blk3]
        self.assertTrue(any("(line 1)" in t for t in targets), targets)
        self.assertTrue(any("(line 2)" in t for t in targets), targets)
        self.assertTrue(any("(line 3)" in t for t in targets), targets)
        # Coverage must report .inherited-only as skipped
        self.assertGreaterEqual(len(res["coverage"]["skipped"]), 1)
        # Strict tokens must flag raw hexes (CHK-W6)
        self.assertTrue(any(f["rule_id"] == "CHK-W6" for f in res["findings"]))

    def test_04_external_css_and_heading_start_level(self):
        rc, res = run_checker([str(FIXTURES / "03_external_link.html")])
        self.assertEqual(rc, 1)
        found = {f["rule_id"] for f in res["findings"]}
        # BLK-03 from external CSS, BLK-07 from <h3> start, BLK-04 from unlabeled input, CHK-W5 from "詳細はこちら"
        self.assertTrue({"BLK-03", "BLK-04", "BLK-07", "CHK-W5"}.issubset(found), res["findings"])

    def test_05_false_positive_guards_web(self):
        rc, res = run_checker([str(FIXTURES / "04_false_positive_guard.html"), "--strict-tokens"])
        self.assertEqual(rc, 0, res["findings"])
        self.assertEqual(len(res["findings"]), 0, res["findings"])

    def test_06_false_positive_guards_markdown_and_doc_type(self):
        rc, res = run_checker([str(FIXTURES / "05_markdown_edges.md")])
        self.assertEqual(rc, 0, res["findings"])
        self.assertEqual(len(res["findings"]), 0, res["findings"])

        # General doc flags wall of text as Major (CHK-D2) + heading skip as Blocker (BLK-07)
        rc_gen, res_gen = run_checker([str(FIXTURES / "06_wall_of_text_ja.md"), "--doc-type", "general"])
        self.assertEqual(rc_gen, 1)
        found_gen = {f["rule_id"] for f in res_gen["findings"]}
        self.assertEqual(found_gen, {"BLK-07", "CHK-D2", "CHK-D3", "CHK-D4"})

        # Spec doc relaxes wall-of-text threshold to 800 chars -> CHK-D2 should NOT trigger on ~430 chars
        _, res_spec = run_checker([str(FIXTURES / "06_wall_of_text_ja.md"), "--doc-type", "spec"])
        found_spec = {f["rule_id"] for f in res_spec["findings"]}
        self.assertNotIn("CHK-D2", found_spec)

    def test_07_exit_code_separation(self):
        proc = subprocess.run([sys.executable, str(CHECKER)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)

    def test_08_self_document_markdown_clean(self):
        # Package's own docs (SKILL, README, tactics, evaluation) must pass with 0 findings
        md_files = [
            ROOT / "SKILL.md",
            ROOT / "README.md",
            *(ROOT / "tactics").glob("*.md"),
            *(ROOT / "evaluation").glob("*.md"),
        ]
        for md in md_files:
            rc, res = run_checker([str(md), "--doc-type", "spec"])
            self.assertEqual(rc, 0, f"Self-check failed on {md.name}: {res['findings']}")
            self.assertEqual(len(res["findings"]), 0, f"Unexpected findings on {md.name}: {res['findings']}")

    def test_09_reference_integrity_across_skill(self):
        id_pattern = re.compile(r"\b(?:BLK|DOC|VIS|INT|SLD|PRO|AI)-\d{2}\b|\bPRN-[1-6]\b|\b(?:CHK|UNV)-[WD]\d\b")
        defined_ids = set()
        # Collect defined IDs from canonical definition files
        def_files = [
            ROOT / "SKILL.md",
            *(ROOT / "tactics").glob("*.md"),
            *(ROOT / "evaluation").glob("*.md"),
        ]
        for p in def_files:
            text = p.read_text(encoding="utf-8")
            # Definitions appear as bold **ID ...**, table | **ID** |, or `- `ID` **`
            for m in re.finditer(r"(?:\*\*|`)\s*((?:BLK|DOC|VIS|INT|SLD|PRO|AI)-\d{2}|PRN-[1-6]|(?:CHK|UNV)-[WD]\d)\b", text):
                defined_ids.add(m.group(1))

        # Check all references across all skill markdown files exist in defined_ids
        missing = []
        for p in def_files:
            text = p.read_text(encoding="utf-8")
            for m in id_pattern.finditer(text):
                ref = m.group(0)
                if ref not in defined_ids:
                    missing.append((p.name, ref))
        self.assertEqual(missing, [], f"Dangling ID references found: {missing}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
