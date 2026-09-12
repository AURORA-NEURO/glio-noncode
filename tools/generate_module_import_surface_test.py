#!/usr/bin/env python3
"""Generate the exhaustive static module-import smoke-test manifest."""

from __future__ import annotations

from pathlib import Path


def _module_ids(source_root: Path) -> tuple[str, ...]:
    modules: list[str] = []
    for path in source_root.rglob("*.py"):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(source_root).with_suffix("")
        parts = relative.parts
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        modules.append(".".join(("glio_noncode", *parts)) if parts else "glio_noncode")
    return tuple(sorted(set(modules)))


def render(module_ids: tuple[str, ...]) -> str:
    lines = [
        '"""Generated import-surface coverage for every package module.',
        "",
        "Regenerate with ``python tools/generate_module_import_surface_test.py``.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import importlib",
        "import sys",
        "import unittest",
        "from contextlib import redirect_stderr, redirect_stdout",
        "from io import StringIO",
        "",
        "from glio_noncode.module_inventory import build_module_inventory",
        "",
        "MODULE_IDS = (",
    ]
    lines.extend(f'    "{module_id}",' for module_id in module_ids)
    lines.extend(
        [
            ")",
            "",
            "",
            "class ModuleImportSurfaceTests(unittest.TestCase):",
            "    def test_every_discovered_module_imports_cleanly(self) -> None:",
            "        inventory = build_module_inventory()",
            "        expected = tuple(item.module_id for item in inventory.modules)",
            "        self.assertEqual(MODULE_IDS, expected)",
            "        for module_id in MODULE_IDS:",
            "            output = StringIO()",
            "            try:",
                "                with redirect_stdout(output), redirect_stderr(output):",
            "                    original_argv = sys.argv",
            "                    sys.argv = [module_id]",
            "                    try:",
            "                        importlib.import_module(module_id)",
            "                    finally:",
            "                        sys.argv = original_argv",
            "            except SystemExit as exc:",
            "                self.assertEqual(exc.code, 0, module_id)",
            "            except BaseException as exc:  # pragma: no cover - diagnostic branch",
            "                self.fail(f\"{module_id} raised {type(exc).__name__}: {exc}\")",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    repository_root = Path(__file__).resolve().parents[1]
    source_root = repository_root / "src" / "glio_noncode"
    destination = repository_root / "tests" / "test_module_import_surface.py"
    module_ids = _module_ids(source_root)
    destination.write_text(render(module_ids), encoding="utf-8", newline="\n")
    print(f"wrote {destination} with {len(module_ids)} module IDs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
