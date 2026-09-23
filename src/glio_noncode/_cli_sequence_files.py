"""CLI adapter from local FASTA and explicitly phased VCF files."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import re
import sys
from pathlib import Path
from typing import Any

from ._cli_sequence import build_analysis_report
from ._cli_support import write_json
from .errors import StoreError, ValidationError
from .identity import normalize_chromosome
from .sequence_haplotype_store import SequenceHaplotypeStore

MAX_SEQUENCE_FILE_BYTES = 128 * 1024 * 1024
MAX_SEQUENCE_FILE_TEXT = 256 * 1024 * 1024
MAX_SEQUENCE_FILE_VARIANTS = 1_024
MAX_SEQUENCE_FILE_MOTIFS = 2_048


def _fasta_contig_header(header_name: str) -> tuple[str, int]:
    """Normalize a contig and origin from a bare or Ensembl FASTA header."""

    fields = header_name.split(":")
    if len(fields) >= 6 and fields[0].casefold() == "chromosome":
        header_name = fields[2]
        try:
            return normalize_chromosome(header_name), _positive_int(
                fields[3], "FASTA coordinate-style header start"
            )
        except ValueError as exc:
            raise ValidationError("FASTA coordinate-style header start is invalid") from exc
    return normalize_chromosome(header_name), 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode sequence-files",
        description=(
            "Read a downloaded FASTA window and explicitly phased VCF calls, "
            "then run the bounded sequence-haplotype analysis."
        ),
    )
    parser.add_argument("--fasta", required=True, help="downloaded FASTA file, optionally .gz")
    parser.add_argument("--vcf", required=True, help="downloaded phased VCF file, optionally .gz")
    parser.add_argument("--sample-id", required=True, help="exact VCF sample column to analyze")
    parser.add_argument("--genome-build", required=True, help="reference assembly label")
    parser.add_argument("--chromosome", required=True, help="FASTA/VCF contig label")
    parser.add_argument("--start", required=True, type=int, help="1-based inclusive window start")
    parser.add_argument("--end", required=True, type=int, help="1-based inclusive window end")
    parser.add_argument(
        "--source-id", required=True, help="stable source identifier for the reference FASTA"
    )
    parser.add_argument(
        "--source-url", required=True, help="canonical HTTPS URL for the reference FASTA"
    )
    parser.add_argument(
        "--source-version", required=True, help="reference FASTA download or release version"
    )
    parser.add_argument("--retrieved-at", required=True, help="UTC retrieval timestamp")
    parser.add_argument(
        "--variant-source-id",
        default=None,
        help="optional stable source identifier for the downloaded VCF",
    )
    parser.add_argument(
        "--variant-source-url",
        default=None,
        help="optional canonical HTTPS URL for the downloaded VCF",
    )
    parser.add_argument(
        "--variant-source-version",
        default=None,
        help="optional downloaded VCF release or version",
    )
    parser.add_argument(
        "--variant-retrieved-at",
        default=None,
        help="optional UTC retrieval timestamp for the downloaded VCF",
    )
    parser.add_argument(
        "--fasta-sha256",
        default=None,
        help="expected SHA-256 digest of the downloaded FASTA payload before decompression",
    )
    parser.add_argument(
        "--vcf-sha256",
        default=None,
        help="expected SHA-256 digest of the downloaded VCF payload before decompression",
    )
    parser.add_argument(
        "--phase-set",
        default=None,
        help="fallback phase-set label when a VCF record has no PS FORMAT value",
    )
    parser.add_argument("--haplotype-index", type=int, default=1, help="1-based phased haplotype")
    parser.add_argument(
        "--motifs",
        default=None,
        help="JSON file containing an array of motif definitions",
    )
    parser.add_argument("--output", default="-", help="JSON analysis report path, or - for stdout")
    parser.add_argument("--save-to-workspace", action="store_true")
    parser.add_argument("--data-root", default=".glio")
    return parser


def _expected_sha256(value: str | None, *, label: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip().casefold()
    if re.fullmatch(r"[0-9a-f]{64}", normalized) is None:
        raise ValidationError(f"{label} SHA-256 digest must be exactly 64 hexadecimal characters")
    return normalized


def _read_download(
    path_value: str,
    *,
    label: str,
    expected_sha256: str | None = None,
) -> tuple[bytes, dict[str, Any]]:
    normalized_expected = _expected_sha256(expected_sha256, label=label)
    path = Path(path_value)
    if path.is_symlink() or not path.is_file():
        raise ValidationError(f"{label} must be a regular local file")
    if path.stat().st_size > MAX_SEQUENCE_FILE_BYTES:
        raise ValidationError(f"{label} exceeds the downloaded-file byte limit")
    raw = path.read_bytes()
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if normalized_expected is not None and actual_sha256 != normalized_expected:
        raise ValidationError(f"{label} SHA-256 digest does not match the expected download")
    if path.suffix.casefold() == ".gz":
        try:
            raw = gzip.decompress(raw)
        except (OSError, EOFError) as exc:
            raise ValidationError(f"{label} gzip payload is invalid") from exc
    receipt = {
        "sha256": f"sha256:{actual_sha256}",
        "size_bytes": path.stat().st_size,
        "compression": "gzip" if path.suffix.casefold() == ".gz" else "none",
    }
    if len(raw) > MAX_SEQUENCE_FILE_TEXT:
        raise ValidationError(f"{label} decompressed payload exceeds its limit")
    return raw, receipt


def _read_motifs(path_value: str | None) -> list[dict[str, Any]]:
    if path_value is None:
        return []
    from ._cli_support import read_mapping

    value = read_mapping(path_value, "motif definitions")
    if type(value) is not dict or frozenset(value) != {"motifs"}:
        raise ValidationError("motif definitions must be an object with one motifs array")
    motifs = value["motifs"]
    if type(motifs) is not list or len(motifs) > MAX_SEQUENCE_FILE_MOTIFS:
        raise ValidationError("motif definitions exceed the supported limit")
    return motifs


def _fasta_window(raw: bytes, *, chromosome: str, start: int, end: int) -> str:
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValidationError("FASTA must contain ASCII bases") from exc
    target = normalize_chromosome(chromosome)
    records: dict[str, tuple[int, str]] = {}
    current: str | None = None
    current_start = 1
    chunks: list[str] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line:
            continue
        if line.startswith(">"):
            if current is not None:
                if current in records:
                    raise ValidationError(f"FASTA repeats contig {current}")
                records[current] = (current_start, "".join(chunks))
            name = line[1:].split(None, 1)[0]
            if not name:
                raise ValidationError(f"FASTA header is empty on line {line_number}")
            current, current_start = _fasta_contig_header(name)
            chunks = []
            continue
        if current is None:
            raise ValidationError("FASTA sequence appears before its header")
        sequence = "".join(line.split()).upper()
        if any(base not in "ACGTN" for base in sequence):
            raise ValidationError(f"FASTA contains an unsupported base on line {line_number}")
        chunks.append(sequence)
    if current is not None:
        if current in records:
            raise ValidationError(f"FASTA repeats contig {current}")
        records[current] = (current_start, "".join(chunks))
    record = records.get(target)
    if record is None:
        raise ValidationError(f"FASTA does not contain contig {target}")
    record_start, sequence = record
    record_end = record_start + len(sequence) - 1
    if start < record_start or end < start or end > record_end:
        raise ValidationError("requested FASTA interval is outside the downloaded contig")
    return sequence[start - record_start : end - record_start + 1]


def _vcf_variants(
    raw: bytes,
    *,
    sample_id: str,
    chromosome: str,
    start: int,
    end: int,
    phase_set_fallback: str | None,
    haplotype_index: int,
    genome_build: str,
) -> list[dict[str, Any]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("VCF must be valid UTF-8 text") from exc
    if not sample_id.strip():
        raise ValidationError("VCF sample ID must not be empty")
    target = normalize_chromosome(chromosome)
    sample_column: int | None = None
    variants: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line or line.startswith("##"):
            continue
        if line.startswith("#CHROM"):
            header = line.split("\t")
            if len(header) < 10:
                raise ValidationError("VCF must contain FORMAT and at least one sample column")
            names = header[9:]
            if names.count(sample_id) != 1:
                raise ValidationError("VCF sample ID must identify exactly one sample column")
            sample_column = 9 + names.index(sample_id)
            continue
        if line.startswith("#"):
            continue
        if sample_column is None:
            raise ValidationError("VCF is missing its #CHROM header")
        fields = line.split("\t")
        if len(fields) <= sample_column or len(fields) < 10:
            raise ValidationError(f"VCF record is truncated on line {line_number}")
        record_chromosome = normalize_chromosome(fields[0])
        position = _positive_int(fields[1], f"VCF position on line {line_number}")
        if record_chromosome != target or not start <= position <= end:
            continue
        reference = fields[3].upper()
        alternates = fields[4].upper().split(",")
        if not reference or not alternates or any(not alternate for alternate in alternates):
            raise ValidationError(f"VCF alleles are empty on line {line_number}")
        format_fields = fields[8].split(":")
        sample_fields = fields[sample_column].split(":")
        if "GT" not in format_fields:
            raise ValidationError(f"VCF record has no GT field on line {line_number}")
        genotype_index = format_fields.index("GT")
        genotype = sample_fields[genotype_index] if len(sample_fields) > genotype_index else ""
        if "|" not in genotype:
            raise ValidationError(f"VCF genotype is not explicitly phased on line {line_number}")
        haplotypes = genotype.split("|")
        if not 1 <= haplotype_index <= len(haplotypes):
            raise ValidationError("requested haplotype index is absent from a VCF genotype")
        allele_index = _positive_or_zero_int(haplotypes[haplotype_index - 1], "VCF genotype allele")
        if allele_index == 0:
            continue
        if allele_index > len(alternates):
            raise ValidationError(f"VCF genotype ALT index is invalid on line {line_number}")
        phase_set = phase_set_fallback
        if "PS" in format_fields:
            position_in_sample = format_fields.index("PS")
            if (
                len(sample_fields) > position_in_sample
                and sample_fields[position_in_sample] not in {"", "."}
            ):
                phase_set = sample_fields[position_in_sample]
        if phase_set is None:
            raise ValidationError(f"VCF record has no explicit phase set on line {line_number}")
        variant_id = (
            fields[2]
            if fields[2] not in {"", "."}
            else f"{record_chromosome}-{position}-{reference}-{alternates[allele_index - 1]}"
        )
        variants.append(
            {
                "notation": (
                    f"{record_chromosome}:{position}:{reference}"
                    f">{alternates[allele_index - 1]}"
                ),
                "variant_id": variant_id,
                "sample_id": sample_id,
                "phase_set": phase_set,
                "haplotype_index": haplotype_index,
            }
        )
        if len(variants) > MAX_SEQUENCE_FILE_VARIANTS:
            raise ValidationError("VCF phased variant count exceeds the supported limit")
    if sample_column is None:
        raise ValidationError("VCF is missing its #CHROM header")
    return variants


def _positive_int(value: str, label: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValidationError(f"{label} must be an integer") from exc
    if parsed < 1:
        raise ValidationError(f"{label} must be positive")
    return parsed


def _positive_or_zero_int(value: str, label: str) -> int:
    if value == ".":
        raise ValidationError(f"{label} must be called")
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValidationError(f"{label} must be an integer") from exc
    if parsed < 0:
        raise ValidationError(f"{label} must not be negative")
    return parsed


def build_sequence_haplotype_input(args: argparse.Namespace) -> dict[str, Any]:
    if args.end < args.start:
        raise ValidationError("sequence window end must not precede its start")
    if args.haplotype_index < 1:
        raise ValidationError("haplotype index must be positive")
    variant_source_values = (
        args.variant_source_id,
        args.variant_source_url,
        args.variant_source_version,
    )
    if any(value is not None for value in variant_source_values) and not all(
        value is not None for value in variant_source_values
    ):
        raise ValidationError(
            "variant source ID, URL, and version must be supplied together"
        )
    variant_source = {
        "source_id": args.variant_source_id or args.source_id,
        "source_url": args.variant_source_url or args.source_url,
        "source_version": args.variant_source_version or args.source_version,
        "retrieved_at": args.variant_retrieved_at or args.retrieved_at,
    }
    fasta_raw, fasta_receipt = _read_download(
        args.fasta, label="FASTA", expected_sha256=args.fasta_sha256
    )
    vcf_raw, vcf_receipt = _read_download(
        args.vcf, label="VCF", expected_sha256=args.vcf_sha256
    )
    sequence = _fasta_window(
        fasta_raw,
        chromosome=args.chromosome,
        start=args.start,
        end=args.end,
    )
    variants = _vcf_variants(
        vcf_raw,
        sample_id=args.sample_id,
        chromosome=args.chromosome,
        start=args.start,
        end=args.end,
        phase_set_fallback=args.phase_set,
        haplotype_index=args.haplotype_index,
        genome_build=args.genome_build,
    )
    return {
        "schema": "glio-noncode.sequence-haplotype-input.v1",
        "genome_build": args.genome_build,
        "sequence": {
            "assembly": args.genome_build,
            "chromosome": normalize_chromosome(args.chromosome),
            "start": args.start,
            "end": args.end,
            "sequence": sequence,
            "source_id": args.source_id,
            "source_url": args.source_url,
            "source_version": args.source_version,
            "retrieved_at": args.retrieved_at,
            "downloaded_inputs": [
                fasta_receipt
                | {
                    "role": "fasta",
                    "source_id": args.source_id,
                    "source_url": args.source_url,
                    "source_version": args.source_version,
                    "retrieved_at": args.retrieved_at,
                },
                vcf_receipt | {"role": "vcf"} | variant_source,
            ],
        },
        "variants": variants,
        "motifs": _read_motifs(args.motifs),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = build_analysis_report(build_sequence_haplotype_input(args))
        if args.save_to_workspace:
            saved = SequenceHaplotypeStore(args.data_root).save(report)
            print(
                f"Saved sequence analysis {saved['analysis_id']} to {args.data_root}",
                file=sys.stderr,
            )
    except (OSError, StoreError, ValidationError, ValueError) as error:
        report = {
            "schema": "glio-noncode.sequence-haplotype-analysis.v1",
            "status": "invalid",
            "error": {
                "code": "invalid_downloaded_sequence_input",
                "message": str(error),
            },
        }
        if args.output == "-":
            print(f"error: {type(error).__name__}: {error}", file=sys.stderr)
    try:
        write_json(report, args.output)
    except (OSError, ValueError, ValidationError) as error:
        print(
            f"error: sequence-files report could not be written ({type(error).__name__})",
            file=sys.stderr,
        )
        return 2
    return 0 if report.get("status") == "completed" else 2


__all__ = ["build_parser", "build_sequence_haplotype_input", "main"]
