"""Template audit regressions using real assets and isolated mutations."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "audit_templates", ROOT / ".github" / "scripts" / "audit_templates.py"
)
audit = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(audit)


class AuditTemplatesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checker = audit.load_checker()
        cls.text = audit.VARIANTS.read_text(encoding="utf-8")
        cls.sections = list(audit.variant_sections(cls.text))

    def run_variants(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "variants.md"
            path.write_text(text, encoding="utf-8")
            output = io.StringIO()
            with patch.object(audit, "VARIANTS", path), contextlib.redirect_stdout(output):
                failures = audit.audit_variants(self.checker)
            return failures, output.getvalue()

    def replace_body(self, number, replacement):
        body = next(body for n, _, body in self.sections if n == number)
        self.assertEqual(self.text.count(body), 1)
        return self.text.replace(body, replacement, 1)

    def test_real_assets_pass_main(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = audit.main()
        self.assertEqual(result, 0, output.getvalue())
        self.assertEqual(output.getvalue().count("passes the full prompt checker"), 2)
        self.assertIn("12 specialised variant(s) audited, 0 failure(s).", output.getvalue())

    def test_real_reference_table_is_the_only_skip(self):
        self.assertEqual([n for n, _, _ in self.sections], [str(n) for n in range(1, 14)])
        failures, output = self.run_variants(self.text)
        self.assertEqual(failures, 0, output)
        self.assertEqual(output.count("SKIP variant"), 1)
        self.assertIn("SKIP variant 6 (分语言定制要点): reference table, no prompt block", output)

    def test_each_prompt_requires_fences(self):
        for number, title, body in self.sections:
            if number == "6":
                continue
            for mutation, replacement in (
                ("deleted block", audit.FENCE.sub("", body)),
                ("unfenced content", body.replace("```text", "").replace("```", "")),
                ("missing closing fence", body.rsplit("```", 1)[0]),
            ):
                with self.subTest(number=number, mutation=mutation):
                    failures, output = self.run_variants(self.replace_body(number, replacement))
                    self.assertEqual(failures, 1, output)
                    self.assertIn(f"FAIL variant {number} ({title}): prompt block not found", output)
                    self.assertIn("12 specialised variant(s) audited, 1 failure(s).", output)

    def test_reference_exemption_requires_number_and_title(self):
        for heading in ("## 6. 普通变体", "## 14. 分语言定制要点"):
            with self.subTest(heading=heading):
                failures, output = self.run_variants(
                    self.text.replace("## 6. 分语言定制要点", heading)
                )
                self.assertEqual(failures, 1, output)
                self.assertIn("prompt block not found", output)
                self.assertNotIn("SKIP variant", output)

    def test_reference_section_prompt_is_still_audited(self):
        failures, output = self.run_variants(self.replace_body("6", "\n```text\n没有锚点\n```\n"))
        self.assertEqual(failures, 1, output)
        self.assertIn("FAIL variant 6", output)
        self.assertIn("no verification anchor", output)

    def test_guard_requires_each_marker(self):
        for marker in ("NO_CODE_PROVIDED", "NO_REFACTORING_NEEDED"):
            with self.subTest(marker=marker):
                failures, output = self.run_variants(self.text.replace(marker, "REMOVED"))
                self.assertEqual(failures, 1, output)
                self.assertIn("FAIL variant 8", output)
                self.assertIn("guard variant lacks", output)

    def test_guard_markers_outside_prompt_do_not_count(self):
        text = self.replace_body("8", "\nNO_CODE_PROVIDED NO_REFACTORING_NEEDED\n```text\n测试\n```\n")
        failures, output = self.run_variants(text)
        self.assertEqual(failures, 1, output)
        self.assertIn("guard variant lacks", output)

    def test_verification_anchor_outside_prompt_does_not_count(self):
        text = self.replace_body("1", "\n验收测试\n```text\n只给出建议。\n```\n")
        failures, output = self.run_variants(text)
        self.assertEqual(failures, 1, output)
        self.assertIn("no verification anchor", output)

    def test_error_anti_pattern_still_fails(self):
        text = self.replace_body("1", "\n```text\n测试；rewrite the whole project\n```\n")
        failures, output = self.run_variants(text)
        self.assertEqual(failures, 1, output)
        self.assertIn("anti-pattern: boil-the-ocean", output)

    def test_warning_and_fragment_structure_remain_nonblocking(self):
        text = self.replace_body("1", "\n```text\n测试；also clean up\n```\n")
        failures, output = self.run_variants(text)
        self.assertEqual(failures, 0, output)
        self.assertIn("PASS variant 1", output)

    def test_main_returns_failure_for_missing_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "variants.md"
            path.write_text(self.replace_body("1", "\n测试\n"), encoding="utf-8")
            output = io.StringIO()
            with patch.object(audit, "VARIANTS", path), contextlib.redirect_stdout(output):
                result = audit.main()
            self.assertEqual(result, 1, output.getvalue())
            self.assertIn("TOTAL: 1 audit failure(s).", output.getvalue())


if __name__ == "__main__":
    unittest.main()
