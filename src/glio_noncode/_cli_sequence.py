"""Focused CLI for deterministic phased sequence and motif analysis."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import replace
from typing import Any
from urllib.parse import urlsplit

from ._cli_support import read_mapping, write_json
from .data_sources import FetchReceipt, FetchStatus, SequenceSlice
from .errors import StoreError, ValidationError
from .identity import parse_variant
from .sequence_inference import (
    MAX_HAPLOTYPE_VARIANTS,
    MAX_MOTIF_DEFINITIONS,
    MotifDefinition,
    PhasedVariantIdentity,
    SequenceInference,
)
from .serialization import content_hash

_SCHEMA = "glio-noncode.sequence-haplotype-input.v1"
_OUTPUT_SCHEMA = "glio-noncode.sequence-haplotype-analysis.v1"
_SEQUENCE_FIELDS = frozenset(
    {
        "assembly",
        "chromosome",
        "start",
        "end",
        "sequence",
        "source_id",
        "source_url",
        "source_version",
        "retrieved_at",
    }
)
_OPTIONAL_SEQUENCE_FIELDS = frozenset({"downloaded_inputs"})
_VARIANT_FIELDS = frozenset(
    {"notation", "variant_id", "sample_id", "phase_set", "haplotype_index"}
)
_MOTIF_FIELDS = frozenset({"motif_id", "name", "pattern", "source_id"})
_DOWNLOAD_FIELDS = frozenset(
    {
        "role",
        "source_id",
        "source_url",
        "source_version",
        "retrieved_at",
        "sha256",
        "size_bytes",
        "compression",
    }
)
_SHA256_ADDRESS_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode sequence-haplotype",
        description=(
            "Apply an explicitly phased SNV/indel set to a bounded reference window "
            "and report deterministic motif creation or disruption."
        ),
    )
    parser.add_argument("input", help="bounded sequence-haplotype input JSON, or - for stdin")
    parser.add_argument("--output", default="-", help="JSON result path, or - for stdout")
    parser.add_argument(
        "--save-to-workspace",
        action="store_true",
        help="persist the completed aggregate report in the local workspace",
    )
    parser.add_argument(
        "--data-root",
        default=".glio",
        help="workspace root used with --save-to-workspace",
    )
    return parser


def _error_report(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": _OUTPUT_SCHEMA,
        "status": "invalid",
        "error": {"code": code, "message": message},
    }


def _text(value: object, label: str, *, maximum: int = 4096) -> str:
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{label} must be non-empty text within its bound")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValidationError(f"{label} must not contain control characters")
    return value


def _integer(value: object, label: str, *, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        raise ValidationError(f"{label} must be an integer of at least {minimum}")
    return value


def _exact_mapping(value: object, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or frozenset(value) != fields:
        raise ValidationError(f"{label} has an invalid exact shape")
    return value


def _receipt(sequence: dict[str, Any]) -> FetchReceipt:
    sequence_bytes = sequence["sequence"].encode("ascii")
    request_payload = content_hash(
        {
            "assembly": sequence["assembly"],
            "chromosome": sequence["chromosome"],
            "start": sequence["start"],
            "end": sequence["end"],
            "source_id": sequence["source_id"],
        }
    ).encode("utf-8")
    request_hash = f"sha256:{hashlib.sha256(request_payload).hexdigest()}"
    response_hash = f"sha256:{hashlib.sha256(sequence_bytes).hexdigest()}"
    return FetchReceipt(
        source_id=sequence["source_id"],
        source_version=sequence["source_version"],
        url=sequence["source_url"],
        request_hash=request_hash,
        response_hash=response_hash,
        status=FetchStatus.FETCHED,
        http_status=200,
        attempts=1,
        retrieved_at=sequence["retrieved_at"],
        elapsed_seconds=0.0,
        cache_expires_at=None,
    )


def _build_sequence(raw: dict[str, Any]) -> SequenceSlice:
    if (
        type(raw) is not dict
        or not _SEQUENCE_FIELDS.issubset(raw)
        or not frozenset(raw).issubset(_SEQUENCE_FIELDS | _OPTIONAL_SEQUENCE_FIELDS)
    ):
        raise ValidationError("sequence has an invalid exact shape")
    sequence = raw
    assembly = _text(sequence["assembly"], "sequence assembly", maximum=256)
    chromosome = _text(sequence["chromosome"], "sequence chromosome", maximum=256)
    start = _integer(sequence["start"], "sequence start")
    end = _integer(sequence["end"], "sequence end")
    sequence_text = _text(sequence["sequence"], "sequence bases", maximum=10_000_000).upper()
    source_id = _text(sequence["source_id"], "sequence source_id", maximum=128)
    source_url = _text(sequence["source_url"], "sequence source_url", maximum=8192)
    source_version = _text(sequence["source_version"], "sequence source_version")
    retrieved_at = _text(sequence["retrieved_at"], "sequence retrieved_at", maximum=128)
    if end - start + 1 != len(sequence_text):
        raise ValidationError("sequence end does not match the sequence length")
    normalized = sequence | {
        "assembly": assembly,
        "chromosome": chromosome,
        "start": start,
        "end": end,
        "sequence": sequence_text,
        "source_id": source_id,
        "source_url": source_url,
        "source_version": source_version,
        "retrieved_at": retrieved_at,
    }
    return SequenceSlice(
        assembly=assembly,
        chromosome=chromosome,
        start=start,
        end=end,
        sequence=sequence_text,
        source_id=source_id,
        receipt=_receipt(normalized),
    )


def _build_downloaded_inputs(raw: object) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if type(raw) is not list or not 1 <= len(raw) <= 2:
        raise ValidationError("downloaded_inputs must contain one or two receipts")
    receipts: list[dict[str, Any]] = []
    roles: set[str] = set()
    for index, item in enumerate(raw):
        receipt = _exact_mapping(item, _DOWNLOAD_FIELDS, f"downloaded input {index + 1}")
        role = _text(receipt["role"], f"downloaded input {index + 1} role", maximum=32)
        if role not in {"fasta", "vcf"} or role in roles:
            raise ValidationError("downloaded input roles must be unique FASTA/VCF values")
        roles.add(role)
        source_id = _text(
            receipt["source_id"], f"downloaded input {index + 1} source_id", maximum=128
        )
        source_url = _text(
            receipt["source_url"], f"downloaded input {index + 1} source_url", maximum=8_192
        )
        parsed_url = urlsplit(source_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValidationError(f"downloaded input {index + 1} source_url must be absolute HTTP")
        source_version = _text(
            receipt["source_version"],
            f"downloaded input {index + 1} source_version",
            maximum=256,
        )
        retrieved_at = _text(
            receipt["retrieved_at"], f"downloaded input {index + 1} retrieved_at", maximum=128
        )
        sha256 = _text(receipt["sha256"], f"downloaded input {index + 1} sha256", maximum=71)
        if _SHA256_ADDRESS_RE.fullmatch(sha256.casefold()) is None:
            raise ValidationError(f"downloaded input {index + 1} sha256 is invalid")
        size_bytes = _integer(
            receipt["size_bytes"], f"downloaded input {index + 1} size_bytes", minimum=0
        )
        if size_bytes > 128 * 1024 * 1024:
            raise ValidationError(f"downloaded input {index + 1} is too large")
        compression = _text(
            receipt["compression"], f"downloaded input {index + 1} compression", maximum=16
        )
        if compression not in {"none", "gzip"}:
            raise ValidationError(f"downloaded input {index + 1} compression is unsupported")
        receipts.append(
            {
                "role": role,
                "source_id": source_id,
                "source_url": source_url,
                "source_version": source_version,
                "retrieved_at": retrieved_at,
                "sha256": sha256.casefold(),
                "size_bytes": size_bytes,
                "compression": compression,
            }
        )
    return receipts


def _build_variants(raw: object, *, genome_build: str) -> tuple[PhasedVariantIdentity, ...]:
    if type(raw) is not list or not 1 <= len(raw) <= MAX_HAPLOTYPE_VARIANTS:
        raise ValidationError(
            f"variants must contain between 1 and {MAX_HAPLOTYPE_VARIANTS} records"
        )
    phased: list[PhasedVariantIdentity] = []
    for index, item in enumerate(raw):
        variant = _exact_mapping(item, _VARIANT_FIELDS, f"variant {index + 1}")
        notation = _text(variant["notation"], f"variant {index + 1} notation", maximum=512)
        variant_id = _text(variant["variant_id"], f"variant {index + 1} ID", maximum=256)
        sample_id = _text(variant["sample_id"], f"variant {index + 1} sample ID", maximum=256)
        phase_set = _text(variant["phase_set"], f"variant {index + 1} phase set", maximum=256)
        haplotype_index = _integer(
            variant["haplotype_index"], f"variant {index + 1} haplotype index"
        )
        parsed = parse_variant(notation, genome_build=genome_build, variant_id=variant_id)
        phased.append(
            PhasedVariantIdentity(
                replace(parsed, sample_id=sample_id),
                phase_set=phase_set,
                haplotype_index=haplotype_index,
            )
        )
    return tuple(phased)


def _build_motifs(raw: object) -> tuple[MotifDefinition, ...]:
    if type(raw) is not list or len(raw) > MAX_MOTIF_DEFINITIONS:
        raise ValidationError(
            f"motifs must contain at most {MAX_MOTIF_DEFINITIONS} records"
        )
    motifs: list[MotifDefinition] = []
    for index, item in enumerate(raw):
        motif = _exact_mapping(item, _MOTIF_FIELDS, f"motif {index + 1}")
        motifs.append(
            MotifDefinition(
                motif_id=_text(motif["motif_id"], f"motif {index + 1} ID", maximum=256),
                name=_text(motif["name"], f"motif {index + 1} name", maximum=512),
                pattern=_text(motif["pattern"], f"motif {index + 1} pattern", maximum=4096),
                source_id=_text(
                    motif["source_id"], f"motif {index + 1} source ID", maximum=256
                ),
            )
        )
    return tuple(motifs)


def build_analysis_report(raw: dict[str, Any]) -> dict[str, Any]:
    if frozenset(raw) != frozenset({"schema", "genome_build", "sequence", "variants", "motifs"}):
        raise ValidationError("sequence-haplotype input has an invalid exact top-level shape")
    if raw["schema"] != _SCHEMA:
        raise ValidationError("sequence-haplotype input schema is unsupported")
    genome_build = _text(raw["genome_build"], "genome_build", maximum=256)
    sequence_input = raw["sequence"]
    sequence = _build_sequence(sequence_input)
    downloaded_inputs = _build_downloaded_inputs(sequence_input.get("downloaded_inputs"))
    phased = _build_variants(raw["variants"], genome_build=genome_build)
    motifs = _build_motifs(raw["motifs"])
    result = SequenceInference().analyze_haplotype(phased, sequence, motifs=motifs)
    body: dict[str, Any] = {
        "schema": _OUTPUT_SCHEMA,
        "status": "completed",
        "analysis_state": result.state,
        "source": {
            "source_id": sequence.source_id,
            "source_version": sequence.receipt.source_version,
            "source_url": sequence.receipt.url,
            "retrieved_at": sequence.receipt.retrieved_at,
            "response_hash": sequence.receipt.response_hash,
            "sequence_interval": (sequence.chromosome, sequence.start, sequence.end),
            "sequence_hash": content_hash(sequence.sequence),
        },
        "inputs": {
            "genome_build": genome_build,
            "variant_count": len(phased),
            "motif_count": len(motifs),
            "variants": [
                {
                    "variant_id": item.variant.variant_id,
                    "canonical_key": item.variant.canonical_key,
                    "phase_set": item.phase_set,
                    "haplotype_index": item.haplotype_index,
                }
                for item in phased
            ],
            "motifs": [motif.to_dict() for motif in motifs],
        },
        "analysis": result.to_dict(),
        "limitations": list(result.limitations),
    }
    if downloaded_inputs:
        body["source"]["downloaded_inputs"] = downloaded_inputs
    return body | {
        "content_address": content_hash(body, prefix="sequence-haplotype-analysis")
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = build_analysis_report(dict(read_mapping(args.input, "sequence-haplotype input")))
    except (OSError, ValueError, ValidationError) as error:
        report = _error_report(
            "invalid_sequence_haplotype_input",
            "The sequence window, phased variants, motifs, or provenance fields failed validation.",
        )
        if args.output == "-":
            print(f"error: {type(error).__name__}: {error}", file=sys.stderr)
    if report.get("status") == "completed" and args.save_to_workspace:
        try:
            from .sequence_haplotype_store import SequenceHaplotypeStore

            saved = SequenceHaplotypeStore(args.data_root).save(report)
        except (OSError, StoreError, ValidationError) as error:
            report = _error_report(
                "sequence_haplotype_persistence_failed",
                "The completed sequence report could not be saved to the workspace.",
            )
            if args.output == "-":
                print(f"error: {type(error).__name__}: {error}", file=sys.stderr)
        else:
            print(
                f"Saved sequence analysis {saved['analysis_id']} to {args.data_root}",
                file=sys.stderr,
            )
    try:
        write_json(report, args.output)
    except (OSError, ValueError, ValidationError) as error:
        print(
            f"error: sequence-haplotype report could not be written ({type(error).__name__})",
            file=sys.stderr,
        )
        return 2
    return 0 if report.get("status") == "completed" else 2


__all__ = ["build_analysis_report", "build_parser", "main"]
