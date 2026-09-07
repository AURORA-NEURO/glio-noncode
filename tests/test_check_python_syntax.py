from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PythonSyntaxCheckTests(unittest.TestCase):
    def _run(self, *roots: Path) -> subprocess.CompletedProcess[str]:
        repository = Path(__file__).resolve().parents[1]
        return subprocess.run(
            [
                sys.executable,
                str(repository / "tools" / "check_python_syntax.py"),
                *(str(root) for root in roots),
            ],
            cwd=repository,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_compiles_nested_sources_without_writing_bytecode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "nested" / ("module_" + "x" * 220 + ".py")
            source.parent.mkdir()
            source.write_text("answer: int = 42\n", encoding="utf-8")

            result = self._run(root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "Python syntax is valid: 1 files")
            self.assertEqual(list(root.rglob("*.pyc")), [])
            self.assertEqual(list(root.rglob("__pycache__")), [])

    def test_reports_syntax_errors_and_returns_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "broken.py"
            source.write_text("def broken(:\n", encoding="utf-8")

            result = self._run(source)

            self.assertEqual(result.returncode, 1)
            self.assertIn("Python syntax check failed", result.stderr)
            self.assertIn("broken.py", result.stderr)


if __name__ == "__main__":
    unittest.main()
