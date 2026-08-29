"""Issue a release certificate for an independently audited package."""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json

from glio_noncode import (
    assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate_json,
    audit_assurance_history_observatory_archive_registry_history_release_gate_package_directory,
    evaluate_assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate,
    render_assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="three-file release-gate package directory")
    parser.add_argument("--format", choices=("json", "markdown", "summary"), default="summary")
    args = parser.parse_args()
    audit = audit_assurance_history_observatory_archive_registry_history_release_gate_package_directory(args.input)
    certificate = evaluate_assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate(audit)
    if args.format == "json":
        print(assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate_json(certificate))
    elif args.format == "markdown":
        print(render_assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate_markdown(certificate), end="")
    else:
        print(json.dumps(certificate.summary(), indent=2, sort_keys=True))
    return 0 if certificate.accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
