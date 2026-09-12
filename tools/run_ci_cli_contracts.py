"""Validate and execute the exact CI CLI contract inventory efficiently.

The sidecar is the former expanded quality workflow.  Keeping it as data makes
every historical command and its ordering reviewable, while this runner imports
the large compatibility CLI and builds its parser only once per CI job.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import os
import re
import shlex
import shutil
import stat
import sys
import tempfile
import traceback
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPOSITORY_ROOT / ".github" / "ci" / "cli-contracts.yml"
EXPECTED_CONTRACT_COUNT = 2107
EXPECTED_LITERAL_COUNT = 1614
EXPECTED_LOOP_EXPANSION_COUNT = 493
EXPECTED_DISTINCT_COMMAND_COUNT = 2080
EXPECTED_SOURCE_STEP_COUNT = 790
DEFAULT_BATCH_SIZE = 64
WORKSPACE_OUTPUT_PATHS = frozenset({"data/service-surface-closure.json"})
ARCHITECTURE_BUNDLE_REQUIRED_FILES = (
    "fixture.json",
    "release.json",
    "report.json",
    "runtime.json",
)
DIRECTORY_OUTPUT_REQUIREMENTS = {
    command: ARCHITECTURE_BUNDLE_REQUIRED_FILES
    for command in (
        "specimen-architecture-bundle",
        "reference-architecture-bundle",
        "atlas-architecture-bundle",
        "sequence-architecture-bundle",
        "chromatin-architecture-bundle",
        "cell-state-architecture-bundle",
        "topology-architecture-bundle",
        "link-graph-architecture-bundle",
        "causal-architecture-bundle",
        "cohort-architecture-bundle",
        "planning-architecture-bundle",
        "evidence-architecture-bundle",
        "workbench-architecture-bundle",
        "platform-execution-architecture-bundle",
    )
}


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
class DeclaredArtifact:
    kind: str
    path: Path
    is_directory: bool
    required_files: tuple[str, ...] = ()


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
                contracts.append(
                    CliContract(
                        len(contracts) + 1, step_name, _parse_argv(arguments, step_name=step_name)
                    )
                )
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
                arguments = template.replace("${base}", base_match.group("base")).replace(
                    "${suffix}", suffix
                )
                contracts.append(
                    CliContract(
                        len(contracts) + 1, step_name, _parse_argv(arguments, step_name=step_name)
                    )
                )
                loop_expansion_count += 1
    return ContractInventory(
        tuple(contracts), literal_count, loop_expansion_count, source_step_count
    )


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
        raise ContractInventoryError(
            f"CLI contract inventory drifted: observed {observed}, expected {expected}"
        )


def validate_contracts(inventory: ContractInventory) -> Any:
    """Build the compatibility parser once and parse every exact argv."""

    legacy_cli = importlib.import_module("glio_noncode._legacy_cli")
    parser = legacy_cli.build_parser()
    for contract in inventory.contracts:
        try:
            parsed = parser.parse_args(list(contract.argv))
        except SystemExit as exc:
            raise ContractInventoryError(
                f"contract {contract.ordinal} ({contract.step_name}) does not parse: "
                f"{shlex.join(contract.argv)}"
            ) from exc
        if parsed.command != contract.command:
            raise ContractInventoryError(
                f"contract {contract.ordinal} parsed as {parsed.command!r}, "
                f"expected {contract.command!r}"
            )
    return parser


def _remap_temporary_value(value: str, output_root: Path) -> str:
    if value == "/tmp":
        return str(output_root)
    if value.startswith("/tmp/"):
        return str(output_root / value.removeprefix("/tmp/"))
    if value in WORKSPACE_OUTPUT_PATHS:
        return str(output_root / "workspace" / value)
    return value


def _remap_temporary_token(token: str, output_root: Path) -> str:
    remapped = _remap_temporary_value(token, output_root)
    if remapped != token:
        return remapped
    if "=" in token:
        prefix, value = token.split("=", 1)
        remapped_value = _remap_temporary_value(value, output_root)
        if remapped_value != value:
            return f"{prefix}={remapped_value}"
    return token


def remap_temporary_paths(argv: Sequence[str], output_root: Path) -> tuple[str, ...]:
    return tuple(_remap_temporary_token(token, output_root) for token in argv)


def _declared_output(argv: Sequence[str]) -> Path | None:
    return _declared_path(argv, "--output")


def _declared_path(argv: Sequence[str], flag: str) -> Path | None:
    equals_prefix = f"{flag}="
    declarations = tuple(
        (position, None if token == flag else token.removeprefix(equals_prefix))
        for position, token in enumerate(argv)
        if token == flag or token.startswith(equals_prefix)
    )
    if not declarations:
        return None
    if len(declarations) != 1:
        raise ContractInventoryError(f"{flag} must occur at most once")
    position, inline_value = declarations[0]
    if inline_value is None:
        if position + 1 >= len(argv):
            raise ContractInventoryError(f"{flag} has no value")
        value = argv[position + 1]
    else:
        value = inline_value
    if not value:
        raise ContractInventoryError(f"{flag} has no value")
    return Path(value)


def _declared_artifacts(argv: Sequence[str]) -> tuple[DeclaredArtifact, ...]:
    artifacts: list[DeclaredArtifact] = []
    output = _declared_path(argv, "--output")
    if output is not None:
        required_files = DIRECTORY_OUTPUT_REQUIREMENTS.get(argv[0], ()) if argv else ()
        artifacts.append(
            DeclaredArtifact(
                kind="output",
                path=output,
                is_directory=bool(required_files),
                required_files=required_files,
            )
        )
    destination = _declared_path(argv, "--destination")
    if destination is not None:
        artifacts.append(
            DeclaredArtifact(kind="destination", path=destination, is_directory=True)
        )
    return tuple(artifacts)


def _is_link_or_reparse_point(path: Path) -> bool:
    """Return whether *path* redirects traversal instead of being a real artifact."""

    try:
        status = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(status, "st_file_attributes", 0)
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(status.st_mode) or bool(attributes & reparse_attribute)


def _assert_no_link_or_reparse_components(
    path: Path,
    *,
    kind: str,
    isolation_root: Path,
    contract: CliContract,
    target_error: str,
) -> None:
    """Reject redirects in the lexical path before containment resolves them away."""

    lexical_path = Path(os.path.abspath(path))
    lexical_root = Path(os.path.abspath(isolation_root))
    try:
        relative = lexical_path.relative_to(lexical_root)
    except ValueError as exc:
        raise ContractInventoryError(
            f"contract {contract.ordinal} ({contract.step_name}) {kind} escaped "
            f"the isolated output root: {path}"
        ) from exc
    component = lexical_root
    for part in relative.parts:
        component /= part
        if _is_link_or_reparse_point(component):
            if component == lexical_path:
                raise ContractInventoryError(target_error)
            raise ContractInventoryError(
                f"contract {contract.ordinal} ({contract.step_name}) {kind} path contains "
                f"a link or reparse point: {component}"
            )


def _assert_declared_artifact_contained(
    path: Path,
    *,
    kind: str,
    isolation_root: Path,
    contract: CliContract,
) -> None:
    path_resolved = path.resolve(strict=False)
    if path_resolved == isolation_root:
        raise ContractInventoryError(
            f"contract {contract.ordinal} ({contract.step_name}) {kind} cannot target "
            "the isolated output root itself"
        )
    try:
        path_resolved.relative_to(isolation_root)
    except ValueError as exc:
        raise ContractInventoryError(
            f"contract {contract.ordinal} ({contract.step_name}) {kind} escaped "
            f"the isolated output root: {path}"
        ) from exc


def _preflight_declared_artifact(
    artifact: DeclaredArtifact,
    *,
    isolation_root: Path,
    contract: CliContract,
) -> None:
    """Validate one target without changing any filesystem state."""

    path = artifact.path
    _assert_no_link_or_reparse_components(
        path,
        kind=artifact.kind,
        isolation_root=isolation_root,
        contract=contract,
        target_error=(
            f"contract {contract.ordinal} ({contract.step_name}) {artifact.kind} target "
            f"is a link or reparse point: {path}"
        ),
    )
    _assert_declared_artifact_contained(
        path,
        kind=artifact.kind,
        isolation_root=isolation_root,
        contract=contract,
    )
    if not path.exists():
        return
    if artifact.is_directory and not path.is_dir():
        raise ContractInventoryError(
            f"contract {contract.ordinal} ({contract.step_name}) {artifact.kind} target "
            f"is not a directory: {path}"
        )
    if not artifact.is_directory and path.is_dir():
        raise ContractInventoryError(
            f"contract {contract.ordinal} ({contract.step_name}) {artifact.kind} target "
            f"is a directory: {path}"
        )
    if not artifact.is_directory and not path.is_file():
        raise ContractInventoryError(
            f"contract {contract.ordinal} ({contract.step_name}) {artifact.kind} target "
            f"is not a regular file: {path}"
        )
    if artifact.is_directory:
        _inspect_real_directory_tree(artifact, contract=contract)


def _prepare_declared_artifact(
    artifact: DeclaredArtifact,
    *,
    isolation_root: Path,
    contract: CliContract,
) -> None:
    path = artifact.path
    _assert_no_link_or_reparse_components(
        path,
        kind=artifact.kind,
        isolation_root=isolation_root,
        contract=contract,
        target_error=(
            f"contract {contract.ordinal} ({contract.step_name}) {artifact.kind} target "
            f"is a link or reparse point: {path}"
        ),
    )
    _assert_declared_artifact_contained(
        path,
        kind=artifact.kind,
        isolation_root=isolation_root,
        contract=contract,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return
    if artifact.is_directory:
        if not path.is_dir():
            raise ContractInventoryError(
                f"contract {contract.ordinal} ({contract.step_name}) {artifact.kind} target "
                f"is not a directory: {path}"
            )
        shutil.rmtree(path)
        return
    if not path.is_file():
        raise ContractInventoryError(
            f"contract {contract.ordinal} ({contract.step_name}) {artifact.kind} target "
            f"is not a regular file: {path}"
        )
    path.unlink()


def _inspect_real_directory_tree(
    artifact: DeclaredArtifact,
    *,
    contract: CliContract,
) -> frozenset[Path]:
    regular_files: set[Path] = set()
    pending = [artifact.path]
    while pending:
        directory = pending.pop()
        for child in directory.iterdir():
            if _is_link_or_reparse_point(child):
                raise ContractInventoryError(
                    f"contract {contract.ordinal} ({contract.step_name}) found a link or "
                    f"reparse point inside declared {artifact.kind} {artifact.path}: {child}"
                )
            if child.is_dir():
                pending.append(child)
            elif child.is_file():
                regular_files.add(child.relative_to(artifact.path))
            else:
                raise ContractInventoryError(
                    f"contract {contract.ordinal} ({contract.step_name}) created a non-regular "
                    f"artifact inside declared {artifact.kind} {artifact.path}: {child}"
                )
    return frozenset(regular_files)


def _verify_declared_artifact(
    artifact: DeclaredArtifact,
    *,
    isolation_root: Path,
    contract: CliContract,
) -> None:
    path = artifact.path
    _assert_no_link_or_reparse_components(
        path,
        kind=artifact.kind,
        isolation_root=isolation_root,
        contract=contract,
        target_error=(
            f"contract {contract.ordinal} ({contract.step_name}) did not create a new real "
            f"artifact at declared {artifact.kind} {path}"
        ),
    )
    _assert_declared_artifact_contained(
        path,
        kind=artifact.kind,
        isolation_root=isolation_root,
        contract=contract,
    )
    valid = path.is_dir() if artifact.is_directory else path.is_file()
    if not valid:
        expected = "directory" if artifact.is_directory else "regular file"
        raise ContractInventoryError(
            f"contract {contract.ordinal} ({contract.step_name}) did not create a new "
            f"{expected} at declared {artifact.kind} {path}"
        )
    if not artifact.is_directory:
        return
    regular_files = _inspect_real_directory_tree(artifact, contract=contract)
    missing = tuple(
        required for required in artifact.required_files if Path(required) not in regular_files
    )
    if missing:
        raise ContractInventoryError(
            f"contract {contract.ordinal} ({contract.step_name}) did not create required "
            f"regular file(s) {', '.join(missing)} in declared {artifact.kind} {path}"
        )
    if not regular_files:
        raise ContractInventoryError(
            f"contract {contract.ordinal} ({contract.step_name}) did not create any regular "
            f"artifacts in declared {artifact.kind} {path}"
        )


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
    isolation_root = output_root.resolve()
    for local_index, contract in enumerate(contracts, start=1):
        index = offset + local_index
        argv = remap_temporary_paths(contract.argv, output_root)
        original_artifacts = _declared_artifacts(contract.argv)
        artifacts = _declared_artifacts(argv)
        if tuple(
            (artifact.kind, artifact.is_directory, artifact.required_files)
            for artifact in artifacts
        ) != tuple(
            (artifact.kind, artifact.is_directory, artifact.required_files)
            for artifact in original_artifacts
        ):
            raise ContractInventoryError(
                f"contract {contract.ordinal} ({contract.step_name}) declared artifacts drifted"
            )
        for original, artifact in zip(
            original_artifacts,
            artifacts,
            strict=True,
        ):
            if artifact.path == original.path:
                raise ContractInventoryError(
                    f"contract {contract.ordinal} ({contract.step_name}) {artifact.kind} was not "
                    "remapped into the isolated output root"
                )
        for artifact in artifacts:
            _preflight_declared_artifact(
                artifact,
                isolation_root=isolation_root,
                contract=contract,
            )
        for artifact in artifacts:
            _prepare_declared_artifact(
                artifact,
                isolation_root=isolation_root,
                contract=contract,
            )
        if progress_every and (index == 1 or index % progress_every == 0 or index == total):
            print(f"[{index}/{total}] {contract.step_name}: {contract.command}", flush=True)
        status = public_cli.main(list(argv))
        if status != 0:
            raise ContractInventoryError(
                f"contract {contract.ordinal} ({contract.step_name}) returned {status}: "
                f"{shlex.join(argv)}"
            )
        for artifact in artifacts:
            _verify_declared_artifact(
                artifact,
                isolation_root=isolation_root,
                contract=contract,
            )


def _chunks(
    values: Sequence[CliContract], size: int
) -> Iterator[tuple[int, Sequence[CliContract]]]:
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
    legacy_cli: Any = importlib.import_module("glio_noncode._legacy_cli")
    original_build_parser = legacy_cli.build_parser
    legacy_cli.build_parser = lambda: parser
    output_root.mkdir(parents=True, exist_ok=True)
    batches = tuple(_chunks(contracts, batch_size))
    try:
        fork_process: Callable[[], int] | None = getattr(os, "fork", None)
        if not isolate_batches or fork_process is None or len(batches) <= 1:
            _execute_in_process(contracts, output_root=output_root, progress_every=progress_every)
            return 1
        for offset, batch in batches:
            sys.stdout.flush()
            sys.stderr.flush()
            process_id = fork_process()
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
    mode.add_argument(
        "--check", action="store_true", help="validate inventory shape and parser compatibility"
    )
    mode.add_argument(
        "--execute", action="store_true", help="execute every contract in source order"
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--output-root", type=Path, default=None, help="retain remapped /tmp outputs at this path"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="execute only the first N contracts (local diagnostics)",
    )
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
        print(
            f"Executed {len(contracts)} exact CLI contracts successfully in "
            f"{batch_count} batch(es).",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
