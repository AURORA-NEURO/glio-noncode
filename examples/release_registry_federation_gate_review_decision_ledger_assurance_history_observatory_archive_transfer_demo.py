"""Run the archive transfer boundary against a downloaded archive.

Example:
    python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_transfer_demo.py \
      --input observatory.zip --destination observatory-transfer --chunk-size 65536 \
      --resource chunks --format markdown
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import argparse
import json
from pathlib import Path

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_transfer as transfer


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Demonstrate verified archive chunk transfer")
    value.add_argument("--input", required=True, help="downloaded observatory archive ZIP")
    value.add_argument("--destination", default=None, help="optional exact transfer directory")
    value.add_argument("--transfer-id", default=transfer.DEFAULT_TRANSFER_ID)
    value.add_argument("--chunk-size", type=int, default=transfer.DEFAULT_CHUNK_SIZE)
    value.add_argument("--resource", choices=transfer.TransferQuery.RESOURCES, default="summary")
    value.add_argument("--text", default=None)
    value.add_argument("--offset", type=int, default=0)
    value.add_argument("--limit", type=int, default=transfer.DEFAULT_LIMIT)
    value.add_argument("--format", choices=("summary", "json", "csv", "markdown"), default="summary")
    return value


def run_demo(arguments: argparse.Namespace) -> tuple[transfer.ArchiveTransfer, transfer.TransferQueryResult]:
    value = transfer.build_transfer_from_bytes(Path(arguments.input).read_bytes(), transfer_id=arguments.transfer_id, chunk_size=arguments.chunk_size)
    if arguments.destination:
        transfer.write_transfer(value, arguments.destination)
        value = transfer.load_transfer(arguments.destination)
    result = transfer.query_transfer(value, resource=arguments.resource, text=arguments.text, offset=arguments.offset, limit=arguments.limit)
    return value, result


def render(value: transfer.ArchiveTransfer, result: transfer.TransferQueryResult, output_format: str) -> str:
    if output_format == "json":
        return transfer.transfer_query_json(result)
    if output_format == "csv":
        return transfer.transfer_query_csv(result)
    if output_format == "markdown":
        return transfer.render_transfer_query_markdown(result)
    return json.dumps({"transfer": value.summary(), "query": result.to_dict()}, sort_keys=True, separators=(",", ":"))


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        value, result = run_demo(arguments)
        print(render(value, result, arguments.format))
        return 0
    except Exception as error:  # noqa: BLE001 - demo boundary reports one stable failure shape.
        print(json.dumps({"error": str(error)}, sort_keys=True, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
