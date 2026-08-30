"""Run the downloaded-data boundary against a real ZIP without extracting it.

Example:

    python examples/downloaded_data_catalog_demo.py \
      C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip \
      artifacts/downloaded-data-demo
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from glio_noncode import downloaded_data_catalog as catalog_model
from glio_noncode import downloaded_data_catalog_audit as audit_model


def build_demo(source: str | Path, destination: str | Path | None = None) -> dict[str, object]:
    """Catalog the structured members and optionally persist a review bundle."""

    catalog = catalog_model.build_catalog(source, catalog_id="glio-noncode-downloaded-demo")
    audit = audit_model.audit_catalog(catalog)
    replay = catalog_model.catalog_from_mapping(catalog.to_dict())
    summary = {
        "source": catalog.source_name,
        "source_size": catalog.source_size,
        "structured_member_count": catalog.member_count,
        "structured_data_bytes": catalog.total_data_bytes,
        "json_count": catalog.json_count,
        "delimited_count": catalog.delimited_count,
        "yaml_count": catalog.yaml_count,
        "catalog_address": catalog.content_address,
        "catalog_audit_address": audit.content_address,
        "audit_passed": audit.accepted,
        "replay_address_matches": replay.content_address == catalog.content_address,
        "members": [
            {
                "ordinal": item.ordinal,
                "member_name": item.member_name,
                "data_kind": item.data_kind,
                "shape": item.shape,
                "record_count": item.record_count,
                "field_count": item.field_count,
                "byte_size": item.byte_size,
            }
            for item in catalog.members
        ],
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        (root / "catalog.json").write_text(catalog_model.catalog_json(catalog), encoding="utf-8")
        (root / "audit.json").write_text(audit_model.audit_json(audit), encoding="utf-8")
        (root / "catalog.csv").write_text(catalog_model.catalog_csv(catalog), encoding="utf-8")
        (root / "catalog.md").write_text(catalog_model.render_catalog_markdown(catalog), encoding="utf-8")
        (root / "audit.md").write_text(audit_model.render_audit_markdown(audit), encoding="utf-8")
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        summary["output_directory"] = str(root.resolve())
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Catalog structured data in a downloaded ZIP")
    parser.add_argument("source", type=Path, help="path to the downloaded ZIP")
    parser.add_argument("destination", type=Path, nargs="?", help="optional review bundle directory")
    args = parser.parse_args()
    summary = build_demo(args.source, args.destination)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["audit_passed"] and summary["replay_address_matches"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
