"""Read-only CodeGraph tree API tests."""
import unittest
from pathlib import Path
from unittest.mock import patch
from tempfile import TemporaryDirectory

from code_annotations.tree import operation


class TreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / ".codegraph").mkdir()
        (self.root / "mod.py").write_text("def start():\n    return 1\n", encoding="utf-8")

    def test_files(self):
        with patch("code_annotations.tree._codegraph", return_value=[{"path": "mod.py"}]):
            self.assertEqual(operation({"action": "files", "root": str(self.root)})["files"],
                             [{"path": "mod.py"}])

    def test_call_edge_excludes_references(self):
        result = {"definitions": [{"definition": {"filePath": "mod.py"}, "callees": [
            {"id": "a", "name": "target", "filePath": "mod.py", "startLine": 10, "relationships": ["calls"]},
            {"id": "b", "name": "callback", "filePath": "mod.py", "startLine": 15, "relationships": ["references"]}
        ]}]}
        with patch("code_annotations.tree._codegraph", return_value=result):
            nodes = operation({"action": "edges", "root": str(self.root), "file": "mod.py",
                               "name": "start", "direction": "callees"})["nodes"]
        self.assertEqual([n["name"] for n in nodes], ["target"])

    def test_rejects_parent_path(self):
        with self.assertRaises(ValueError):
            operation({"action": "source", "root": str(self.root), "file": "../other.py", "line": 1})

    def test_source_and_symbols(self):
        s = operation({"action": "symbols", "root": str(self.root), "file": "mod.py"})
        self.assertEqual(s["symbols"][0]["name"], "start")
        source = operation({"action": "source", "root": str(self.root), "file": "mod.py", "line": 1})
        self.assertIn("def start():", source["source"])


if __name__ == "__main__":
    unittest.main()
