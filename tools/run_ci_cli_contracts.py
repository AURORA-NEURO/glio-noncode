"""Validate and execute the exact CI CLI contract inventory efficiently.

The sidecar is the former expanded quality workflow.  Keeping it as data makes
every historical command and its ordering reviewable, while this runner imports
the large compatibility CLI and builds its parser only once per CI job.
"""

from __future__ import annotations

import argparse
import contextlib
import gc
import importlib
import os
import re
import shlex
import sys
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPOSITORY_ROOT / ".github" / "ci" / "cli-contracts.yml"
EXPECTED_CONTRACT_COUNT = 2107
EXPECTED_LITERAL_COUNT = 1614
EXPECTED_LOOP_EXPANSION_COUNT = 493
EXPECTED_DISTINCT_COMMAND_COUNT = 2080
EXPECTED_SOURCE_STEP_COUNT = 790
DEFAULT_BATCH_SIZE = 64
WORKSPACE_OUTPUT_PATHS = frozenset({"data/service-surface-closure.json"})


def _ensure_repository_import_path() -> None:
    """Match the import path of the original ``python -m`` workflow calls."""

    repository = str(REPOSITORY_ROOT)
    if repository not in sys.path:
        sys.path.insert(0, repository)


_ensure_repository_import_path()

_NAME_PATTERN = re.compile(r"^\s*-\s+name:\s*(?P<name>.+?)\s*$")
_RUN_PATTERN = re.compile(r"^(?P<indent>\s*)run:\s*(?P<value>.*?)\s*$")
_CLI_PATTERN = re.compile(
    r"(?:^|\n|\s+&&\s+)\s*python\s+-m\s+glio_noncode\s+"
    r"(?P<arguments>.*?)(?=\s+&&\s+|\n|$)",
    re.DOTALL,
)
_BASE_PATTERN = re.compile(r'^\s*base=["\'](?P<base>[^"\']+)["\']\s*$', re.MULTILINE)
_LOOP_PATTERN = re.compile(
    r"^\s*for\s+suffix\s+in\s+(?P<suffixes>[^;]+);\s*do\s*$"
    r"(?P<body>.*?)"
    r"^\s*done\s*$",
    re.DOTALL | re.MULTILINE,
)


class ContractInventoryError(RuntimeError):
    """The checked-in contract inventory is malformed or has drifted."""


@dataclass(frozen=True)
class CliContract:
    ordinal: int
    step_name: str
    argv: tuple[str, ...]

    @property
    def command(self) -> str:
        return self.argv[0]


@dataclass(frozen=True)
class ContractInventory:
    contracts: tuple[CliContract, ...]
    literal_count: int
    loop_expansion_count: int
    source_step_count: int


def _unquote_scalar(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def iter_workflow_runs(path: Path) -> Iterator[tuple[str, str]]:
    """Yield step names and shell bodies from the constrained sidecar YAML."""

    lines = path.read_text(encoding="utf-8").splitlines()
    step_name = "unnamed step"
    index = 0
    while index < len(lines):
        line = lines[index]
        name_match = _NAME_PATTERN.match(line)
        if name_match:
            step_name = _unquote_scalar(name_match.group("name"))
            index += 1
            continue
        run_match = _RUN_PATTERN.match(line)
        if not run_match:
            index += 1
            continue
        value = run_match.group("value")
        if value not in {"|", "|-", "|+", ">", ">-", ">+"}:
            yield step_name, value
            index += 1
            continue
        field_indent = len(run_match.group("indent"))
        index += 1
        block: list[str] = []
        while index < len(lines):
            candidate = lines[index]
            if candidate.strip() and len(candidate) - len(candidate.lstrip()) <= field_indent:
                break
            block.append(candidate[field_indent + 2 :] if candidate.strip() else "")
            index += 1
        separator = " " if value.startswith(">") else "\n"
        yield step_name, separator.join(block)


def _command_arguments(script: str) -> tuple[str, ...]:
    return tuple(match.group("arguments").strip() for match in _CLI_PATTERN.finditer(script))


def _parse_argv(arguments: str, *, step_name: str) -> tuple[str, ...]:
    try:
        argv = tuple(shlex.split(arguments, posix=True))
    except ValueError as exc:
        raise ContractInventoryError(f"{step_name}: invalid shell quoting: {exc}") from exc
    if not argv:
        raise ContractInventoryError(f"{step_name}: empty CLI contract")
    if any(token in {"&&", ";", "do", "done"} for token in argv):
        raise ContractInventoryError(f"{step_name}: unsupported shell token in CLI contract")
    return argv


def load_contract_inventory(path: Path = DEFAULT_MANIFEST) -> ContractInventory:
    contracts: list[CliContract] = []
    literal_count = 0
    loop_expansion_count = 0
    source_step_count = 0
    for step_name, script in iter_workflow_runs(path):
        if "python -m glio_noncode" not in script:
            continue
        source_step_count += 1
        loop_match = _LOOP_PATTERN.search(script)
        if loop_match is None:
            for arguments in _command_arguments(script):
                contracts.append(CliContract(len(contracts) + 1, step_name, _parse_argv(arguments, step_name=step_name)))
                literal_count += 1
            continue
        base_match = _BASE_PATTERN.search(script)
        if base_match is None:
            raise ContractInventoryError(f"{step_name}: suffix loop has no quoted base")
        templates = _command_arguments(loop_match.group("body"))
        suffixes = tuple(shlex.split(loop_match.group("suffixes"), posix=True))
        if not templates or not suffixes:
            raise ContractInventoryError(f"{step_name}: suffix loop is empty")
        for suffix in suffixes:
            for template in templates:
                arguments = template.replace("${base}", base_match.group("base")).replace("${suffix}", suffix)
                contracts.append(CliContract(len(contracts) + 1, step_name, _parse_argv(arguments, step_name=step_name)))
                loop_expansion_count += 1
    return ContractInventory(tuple(contracts), literal_count, loop_expansion_count, source_step_count)


def assert_expected_inventory(inventory: ContractInventory) -> None:
    observed = (
        len(inventory.contracts),
        inventory.literal_count,
        inventory.loop_expansion_count,
        inventory.source_step_count,
        len({contract.command for contract in inventory.contracts}),
        len({contract.argv for contract in inventory.contracts}),
    )
    expected = (
        EXPECTED_CONTRACT_COUNT,
        EXPECTED_LITERAL_COUNT,
        EXPECTED_LOOP_EXPANSION_COUNT,
        EXPECTED_SOURCE_STEP_COUNT,
        EXPECTED_DISTINCT_COMMAND_COUNT,
        EXPECTED_CONTRACT_COUNT,
    )
    if observed != expected:
        raise ContractInventoryError(f"CLI contract inventory drifted: observed {observed}, expected {expected}")


def validate_contracts(inventory: ContractInventory) -> Any:
    """Build the compatibility parser once and parse every exact argv."""

    legacy_cli = importlib.import_module("glio_noncode._legacy_cli")
    parser = legacy_cli.build_parser()
    for contract in inventory.contracts:
        try:
            parsed = parser.parse_args(list(contract.argv))
        except SystemExit as exc:
            raise ContractInventoryError(
                f"contract {contract.ordinal} ({contract.step_name}) does not parse: {shlex.join(contract.argv)}"
            ) from exc
        if parsed.command != contract.command:
            raise ContractInventoryError(
                f"contract {contract.ordinal} parsed as {parsed.command!r}, expected {contract.command!r}"
            )
    return parser


def _remap_temporary_token(token: str, output_root: Path) -> str:
    if token == "/tmp":
        return str(output_root)
    if token.startswith("/tmp/"):
        return str(output_root / token.removeprefix("/tmp/"))
    marker = "=/tmp/"
    if marker in token:
        prefix, suffix = token.split(marker, 1)
        return prefix + "=" + str(output_root / suffix)
    if token in WORKSPACE_OUTPUT_PATHS:
        return str(output_root / "workspace" / token)
    return token


def remap_temporary_paths(argv: Sequence[str], output_root: Path) -> tuple[str, ...]:
    return tuple(_remap_temporary_token(token, output_root) for token in argv)


def _declared_output(argv: Sequence[str]) -> Path | None:
    if "--output" not in argv:
        return None
    position = argv.index("--output")
    if position + 1 >= len(argv):
        raise ContractInventoryError("--output has no value")
    return Path(argv[position + 1])


def _execute_in_process(
    contracts: Sequence[CliContract],
    *,
    output_root: Path,
    progress_every: int = 100,
    offset: int = 0,
    total: int | None = None,
) -> None:
    public_cli = importlib.import_module("glio_noncode.cli")
    total = len(contracts) if total is None else total
    for local_index, contract in enumerate(contracts, start=1):
        index = offset + local_index
        argv = remap_temporary_paths(contract.argv, output_root)
        if progress_every and (index == 1 or index % progress_every == 0 or index == total):
            print(f"[{index}/{total}] {contract.step_name}: {contract.command}", flush=True)
        status = public_cli.main(list(argv))
        if status != 0:
            raise ContractInventoryError(
                f"contract {contract.ordinal} ({contract.step_name}) returned {status}: {shlex.join(argv)}"
            )
        output = _declared_output(argv)
        if output is not None and not output.exists():
            raise ContractInventoryError(
                f"contract {contract.ordinal} ({contract.step_name}) did not create {output}"
            )
        if index % 100 == 0:
            gc.collect()


def _chunks(values: Sequence[CliContract], size: int) -> Iterator[tuple[int, Sequence[CliContract]]]:
    for offset in range(0, len(values), size):
        yield offset, values[offset : offset + size]


def execute_contracts(
    contracts: Sequence[CliContract],
    *,
    parser: Any,
    output_root: Path,
    progress_every: int = 100,
    batch_size: int = DEFAULT_BATCH_SIZE,
    isolate_batches: bool = True,
) -> int:
    """Run ordered contracts with one parser and bounded process isolation.

    Linux CI forks a fresh copy-on-write worker per batch, so a completed or
    failed worker cannot mutate the parent used to start a later batch.  State
    is intentionally shared by commands *within* a batch; keep ``batch_size``
    small enough for the measured contract inventory.  Platforms without
    ``fork`` use the same ordered in-process engine for portable local checks.
    """

    if batch_size < 1:
        raise ContractInventoryError("batch size must be positive")
    legacy_cli = importlib.import_module("glio_noncode._legacy_cli")
    original_build_parser = legacy_cli.build_parser
    legacy_cli.build_parser = lambda: parser
    output_root.mkdir(parents=True, exist_ok=True)
    batches = tuple(_chunks(contracts, batch_size))
    try:
        use_fork = isolate_batches and hasattr(os, "fork") and len(batches) > 1
        if not use_fork:
            _execute_in_process(contracts, output_root=output_root, progress_every=progress_every)
            return 1
        for offset, batch in batches:
            sys.stdout.flush()
            sys.stderr.flush()
            process_id = os.fork()
            if process_id == 0:
                try:
                    _execute_in_process(
                        batch,
                        output_root=output_root,
                        progress_every=progress_every,
                        offset=offset,
                        total=len(contracts),
                    )
                except BaseException:
                    traceback.print_exc()
                    sys.stdout.flush()
                    sys.stderr.flush()
                    os._exit(1)
                sys.stdout.flush()
                sys.stderr.flush()
                os._exit(0)
            _, wait_status = os.waitpid(process_id, 0)
            if os.waitstatus_to_exitcode(wait_status) != 0:
                first = batch[0].ordinal
                last = batch[-1].ordinal
                raise ContractInventoryError(f"isolated CLI contract batch {first}-{last} failed")
        return len(batches)
    finally:
        legacy_cli.build_parser = original_build_parser


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="validate inventory shape and parser compatibility")
    mode.add_argument("--execute", action="store_true", help="execute every contract in source order")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-root", type=Path, default=None, help="retain remapped /tmp outputs at this path")
    parser.add_argument("--limit", type=int, default=None, help="execute only the first N contracts (local diagnostics)")
    parser.add_argument("--progress-every", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--in-process", action="store_true", help="disable POSIX batch isolation")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    inventory = load_contract_inventory(args.manifest)
    assert_expected_inventory(inventory)
    parser = validate_contracts(inventory)
    print(
        "Validated "
        f"{len(inventory.contracts)} exact CLI contracts "
        f"({inventory.literal_count} literal, {inventory.loop_expansion_count} loop-expanded, "
        f"{len({item.command for item in inventory.contracts})} command names) "
        f"from {inventory.source_step_count} source steps.",
        flush=True,
    )
    if args.check:
        return 0
    contracts = inventory.contracts if args.limit is None else inventory.contracts[: args.limit]
    if args.limit is not None and args.limit < 1:
        raise ContractInventoryError("--limit must be positive")
    manager = (
        contextlib.nullcontext(args.output_root)
        if args.output_root is not None
        else tempfile.TemporaryDirectory(prefix="glio-ci-cli-contracts-")
    )
    with manager as temporary:
        output_root = Path(temporary)
        batch_count = execute_contracts(
            contracts,
            parser=parser,
            output_root=output_root,
            progress_every=args.progress_every,
            batch_size=args.batch_size,
            isolate_batches=not args.in_process,
        )
        print(f"Executed {len(contracts)} exact CLI contracts successfully in {batch_count} batch(es).", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
