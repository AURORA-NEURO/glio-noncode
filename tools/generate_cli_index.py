"""Generate the lightweight CLI command index from the compatibility parser."""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
OUTPUT_PATH = SOURCE_ROOT / "glio_noncode" / "_cli_index.py"
SHELL_COMMANDS = (
    ("case", "prepare and run a case from source manifests"),
    ("expression", "analyze expression and allele-specific RNA evidence"),
    ("geo-outlier", "compare one GEO expression feature with explicit references"),
    ("geo-qc", "summarize sample coverage and matrix quality before analysis"),
    ("geo-metadata", "inventory GEO sample characteristics before contrast design"),
    ("geo-contrast", "screen two GEO sample groups across all platform features"),
    ("verify-release-evidence", "verify a portable release-evidence ZIP"),
    ("assessment-capabilities", "inspect verified-run assessment contracts and limits"),
    ("report-capabilities", "inspect supported report audiences, formats, and limits"),
    ("run-assessment", "build one replay, quality, report, and rendering closure"),
    ("run-report", "render one replay-verified persisted run"),
)


def _legacy_commands() -> tuple[tuple[str, str], ...]:
    sys.path.insert(0, str(SOURCE_ROOT))
    legacy_cli = importlib.import_module("glio_noncode._legacy_cli")
    parser = legacy_cli.build_parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    help_by_name = {
        action.dest: "" if action.help is argparse.SUPPRESS else str(action.help or "")
        for action in subparsers._choices_actions
    }
    return tuple(
        sorted(
            (str(name), help_by_name.get(str(name), ""))
            for name in subparsers.choices
        )
    )


def _render_rows(rows: tuple[tuple[str, str], ...]) -> str:
    rendered = []
    for name, help_text in rows:
        rendered.extend(("    (", f"        {name!r},", f"        {help_text!r},", "    ),"))
    return "\n".join(rendered)


def main() -> int:
    legacy_commands = _legacy_commands()
    legacy_names = {name for name, _ in legacy_commands}
    collisions = sorted(name for name, _ in SHELL_COMMANDS if name in legacy_names)
    if collisions:
        raise RuntimeError(f"shell command collides with legacy parser: {collisions}")

    source = f'''\
# ruff: noqa: E501
"""Generated static command index for the lightweight CLI shell.

Regenerate with ``python tools/generate_cli_index.py`` after changing the legacy
parser. The shell can use this module without importing the compatibility graph.
"""

from __future__ import annotations

LEGACY_COMMANDS: tuple[tuple[str, str], ...] = (
{_render_rows(legacy_commands)}
)

SHELL_COMMANDS: tuple[tuple[str, str], ...] = (
{_render_rows(tuple(sorted(SHELL_COMMANDS)))}
)

COMMANDS: tuple[tuple[str, str], ...] = tuple(sorted(LEGACY_COMMANDS + SHELL_COMMANDS))
COMMAND_BY_NAME: dict[str, str] = dict(COMMANDS)

__all__ = ["COMMANDS", "COMMAND_BY_NAME", "LEGACY_COMMANDS", "SHELL_COMMANDS"]
'''
    OUTPUT_PATH.write_text(source, encoding="utf-8", newline="\n")
    print(f"wrote {len(legacy_commands)} legacy commands to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
