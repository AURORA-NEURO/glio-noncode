#!/usr/bin/env python3
"""Compile Python sources in memory without creating path-length-sensitive bytecode."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _python_files(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    files: set[Path] = set()
    for root in roots:
        if root.is_file():
            if root.suffix != ".py":
                raise ValueError(f"syntax-check input is not a Python file: {root}")
            files.add(root)
        elif root.is_dir():
            files.update(root.rglob("*.py"))
        else:
            raise ValueError(f"syntax-check input does not exist: {root}")
    return tuple(sorted(files, key=lambda path: path.as_posix()))


def check_python_syntax(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    """Return checked files after compiling their exact bytes without writing ``.pyc``."""

    files = _python_files(roots)
    if not files:
        raise ValueError("syntax-check inputs contain no Python files")
    failures: list[str] = []
    for path in files:
        try:
            source = path.read_bytes()
            compile(source, str(path), "exec", dont_inherit=True)
        except (OSError, SyntaxError, UnicodeError) as exc:
            failures.append(f"{path}: {exc}")
    if failures:
        raise SyntaxError("Python syntax check failed:\n" + "\n".join(failures))
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile Python source bytes in memory without writing bytecode files."
    )
    parser.add_argument("roots", nargs="+", type=Path)
    args = parser.parse_args(argv)
    try:
        files = check_python_syntax(tuple(args.roots))
    except (OSError, SyntaxError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Python syntax is valid: {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
