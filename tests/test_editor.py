"""Regression tests for reversible call annotations. Run: python -m unittest discover -s tests -v"""
import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from code_annotations.analyzer import Index
from code_annotations.editor import apply_batch, edit


class AnnotationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.a = self.root / "a.py"
        self.b = self.root / "b.py"

    def index(self):
        return Index(self.root).build()

    def test_roundtrip_human_comments_and_decorators(self):
        original = (
            "# original\n# 功能：测试\n# 说明：必须保留\n"
            "def helper():\n    return 1\n\n"
            "# handcrafted comment\n@staticmethod\ndef test():\n    return helper()\n"
            "\nclass Demo:\n    # initialization note\n"
            "    def run(self):\n        return helper()\n"
        )
        self.a.write_bytes(original.encode())
        idx = self.index()
        before, after = edit(self.a, idx, "write")
        apply_batch([(self.a, before, after)])
        self.assertEqual(after, edit(self.a, self.index(), "write")[1])
        before2, removed = edit(self.a, self.index(), "remove")
        apply_batch([(self.a, before2, removed)])
        self.assertEqual(self.a.read_bytes(), original.encode())
        self.assertEqual(ast.dump(ast.parse(after)), ast.dump(ast.parse(original)))

    def test_crlf_bom(self):
        original = ("# 功能：示例\r\n"
                    "def f():\r\n    return 2\r\n").encode("utf-8-sig")
        self.a.write_bytes(original)
        before, after = edit(self.a, self.index(), "write")
        apply_batch([(self.a, before, after)])
        self.assertIn(b"\r\n", self.a.read_bytes())
        self.assertTrue(self.a.read_bytes().startswith(b"\xef\xbb\xbf"))
        before, after = edit(self.a, self.index(), "remove")
        apply_batch([(self.a, before, after)])
        self.assertEqual(original, self.a.read_bytes())

    def test_batch_preflight_aborts_everything(self):
        self.a.write_text("def a():\n    pass\n")
        self.b.write_text("def b():\n    pass\n")
        idx = self.index()
        x = edit(self.a, idx, "write")
        y = edit(self.b, idx, "write")
        self.b.write_text("def b():\n    return 5\n")
        with self.assertRaises(RuntimeError):
            apply_batch([(self.a, *x), (self.b, *y)])
        self.assertEqual(self.a.read_bytes(), x[0].encode())

    def test_batch_rollback_on_replace_failure(self):
        self.a.write_text("def a():\n    pass\n")
        self.b.write_text("def b():\n    pass\n")
        idx = self.index()
        x = edit(self.a, idx, "write")
        y = edit(self.b, idx, "write")
        original_replace = __import__("os").replace
        counter = [0]
        def flaky(src, dst):
            counter[0] += 1
            if counter[0] == 2:
                raise OSError("injected failure")
            return original_replace(src, dst)
        with patch("code_annotations.editor.os.replace", side_effect=flaky):
            with self.assertRaises(OSError):
                apply_batch([(self.a, *x), (self.b, *y)])
        self.assertEqual(self.a.read_bytes(), x[0].encode())
        self.assertEqual(self.b.read_bytes(), y[0].encode())


if __name__ == "__main__":
    unittest.main()
