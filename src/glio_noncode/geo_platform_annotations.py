"""Bounded, provenance-preserving reads of GEO platform annotation tables."""

from __future__ import annotations

import gzip
import hashlib
import io
import re
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from .errors import ValidationError

MAX_PLATFORM_ANNOTATION_COMPRESSED_BYTES = 600_000_000
MAX_PLATFORM_ANNOTATION_DECOMPRESSED_BYTES = 2_000_000_000
MAX_PLATFORM_ANNOTATION_LINE_BYTES = 4_000_000
MAX_PLATFORM_ANNOTATION_ROWS = 1_000_000
MAX_PLATFORM_ANNOTATION_COLUMNS = 16
MAX_PLATFORM_ANNOTATION_VALUE_LENGTH = 8_192
MAX_PLATFORM_ANNOTATION_RETAINED_BYTES = 64_000_000
_GPL_RE = re.compile(r"GPL[0-9]{1,10}\Z")
_FEATURE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@|/+=_-]{0,255}\Z")


@dataclass(frozen=True, slots=True)
class GeoPlatformAnnotations:
    platform_id: str
    id_column: str
    annotation_columns: tuple[str, ...]
    records: tuple[tuple[str, tuple[str, ...]], ...]
    source_file_name: str
    source_sha256: str
    source_bytes: int
    decompressed_bytes: int


class _DigestingReader(io.RawIOBase):
    def __init__(self, source: BinaryIO) -> None:
        self._source = source
        self.digest = hashlib.sha256()
        self.bytes_read = 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: bytearray) -> int:
        chunk = self._source.read(len(buffer))
        if not chunk:
            return 0
        self.digest.update(chunk)
        self.bytes_read += len(chunk)
        buffer[: len(chunk)] = chunk
        if self.bytes_read > MAX_PLATFORM_ANNOTATION_COMPRESSED_BYTES:
            raise ValidationError("GEO platform annotation exceeds its compressed byte bound")
        return len(chunk)


def _validated_columns(
    id_column: str,
    annotation_columns: tuple[str, ...],
) -> tuple[str, tuple[str, ...]]:
    if not isinstance(id_column, str) or not id_column.strip():
        raise ValidationError("GEO platform annotation ID column must be non-empty text")
    normalized_id = id_column.strip()
    if len(normalized_id) > 256:
        raise ValidationError("GEO platform annotation ID column exceeds its length bound")
    if not isinstance(annotation_columns, tuple) or not annotation_columns:
        raise ValidationError("at least one GEO platform annotation column must be selected")
    if len(annotation_columns) > MAX_PLATFORM_ANNOTATION_COLUMNS:
        raise ValidationError("too many GEO platform annotation columns were selected")
    columns: list[str] = []
    seen = {normalized_id.casefold()}
    for column in annotation_columns:
        if not isinstance(column, str) or not column.strip():
            raise ValidationError("GEO platform annotation columns must be non-empty text")
        normalized = column.strip()
        if len(normalized) > 256:
            raise ValidationError("GEO platform annotation column exceeds its length bound")
        if normalized.casefold() in seen:
            raise ValidationError("GEO platform annotation column names must be unique")
        seen.add(normalized.casefold())
        columns.append(normalized)
    return normalized_id, tuple(columns)


def _split_tab_record(line: str) -> list[str]:
    fields: list[str] = []
    field: list[str] = []
    quoted = False
    after_quote = False
    index = 0
    while index < len(line):
        character = line[index]
        if character == '"':
            if quoted and index + 1 < len(line) and line[index + 1] == '"':
                field.append('"')
                index += 2
                continue
            if quoted:
                quoted = False
                after_quote = True
            elif field or after_quote:
                raise ValidationError("GEO platform annotation has malformed quoted fields")
            else:
                quoted = True
        elif character == "\t" and not quoted:
            fields.append("".join(field))
            field.clear()
            after_quote = False
        elif after_quote:
            raise ValidationError("GEO platform annotation has malformed quoted fields")
        else:
            field.append(character)
        index += 1
    if quoted:
        raise ValidationError("GEO platform annotation has an unterminated quoted field")
    fields.append("".join(field))
    return fields


def read_geo_platform_annotations(
    path: str | Path,
    *,
    expected_platform_id: str,
    annotation_columns: tuple[str, ...],
    id_column: str = "ID",
) -> GeoPlatformAnnotations:
    """Read selected columns from one local GEO SOFT platform table.

    The complete source is hashed and decompressed in a streaming pass. Only the
    feature identifier and explicitly selected columns are retained in memory.
    """

    if not isinstance(expected_platform_id, str) or not _GPL_RE.fullmatch(
        expected_platform_id.strip().upper()
    ):
        raise ValidationError("expected GEO platform ID must be a GPL accession")
    platform_id = expected_platform_id.strip().upper()
    normalized_id_column, requested_columns = _validated_columns(
        id_column,
        annotation_columns,
    )
    source_path = Path(path)
    try:
        source_size = source_path.stat().st_size
    except OSError as error:
        raise ValidationError("GEO platform annotation file cannot be read") from error
    if source_size <= 0 or source_size > MAX_PLATFORM_ANNOTATION_COMPRESSED_BYTES:
        raise ValidationError("GEO platform annotation exceeds its compressed byte bound")

    platform_seen = False
    any_platform_seen = False
    current_platform_entity_id: str | None = None
    current_platform_accession: str | None = None
    table_started = False
    table_ended = False
    header_indices: tuple[int, tuple[int, ...]] | None = None
    header_width = 0
    actual_id_column: str | None = None
    actual_columns: tuple[str, ...] = ()
    records: dict[str, tuple[str, ...]] = {}
    retained_bytes = 0
    decompressed_bytes = 0

    try:
        with source_path.open("rb") as source_file:
            digesting_reader = _DigestingReader(source_file)
            buffered_reader = io.BufferedReader(digesting_reader)
            is_gzip = buffered_reader.peek(2)[:2] == b"\x1f\x8b"
            binary_stream: BinaryIO
            if is_gzip:
                binary_stream = gzip.GzipFile(fileobj=buffered_reader, mode="rb")
            else:
                binary_stream = buffered_reader

            with binary_stream:
                while True:
                    line_bytes = binary_stream.readline(MAX_PLATFORM_ANNOTATION_LINE_BYTES + 1)
                    if not line_bytes:
                        break
                    if len(line_bytes) > MAX_PLATFORM_ANNOTATION_LINE_BYTES:
                        raise ValidationError("GEO platform annotation line exceeds its byte bound")
                    decompressed_bytes += len(line_bytes)
                    if decompressed_bytes > MAX_PLATFORM_ANNOTATION_DECOMPRESSED_BYTES:
                        raise ValidationError(
                            "GEO platform annotation exceeds its decompressed byte bound"
                        )
                    try:
                        line = line_bytes.decode("utf-8").rstrip("\r\n")
                    except UnicodeDecodeError as error:
                        raise ValidationError(
                            "GEO platform annotation is not valid UTF-8"
                        ) from error

                    if line.startswith("^"):
                        if table_started and not table_ended:
                            raise ValidationError("GEO platform annotation table is incomplete")
                        entity, separator, value = line.partition("=")
                        if separator and entity.strip().casefold() == "^platform":
                            any_platform_seen = True
                            current_platform_entity_id = value.strip().upper()
                            current_platform_accession = None
                        else:
                            current_platform_entity_id = None
                            current_platform_accession = None
                        continue

                    key, separator, value = line.partition("=")
                    if key.strip().casefold() == "!platform_geo_accession":
                        if current_platform_entity_id is not None:
                            if current_platform_accession is not None:
                                raise ValidationError(
                                    "GEO platform annotation repeats its platform accession"
                                )
                            candidate_accession = value.strip().upper() if separator else ""
                            if not _GPL_RE.fullmatch(candidate_accession):
                                raise ValidationError(
                                    "GEO platform annotation has an invalid GPL accession"
                                )
                            current_platform_accession = candidate_accession
                        continue

                    if line.casefold() == "!platform_table_begin":
                        candidate_platform_id = current_platform_accession
                        if (
                            candidate_platform_id is None
                            and current_platform_entity_id is not None
                            and _GPL_RE.fullmatch(current_platform_entity_id)
                        ):
                            candidate_platform_id = current_platform_entity_id
                        if candidate_platform_id == platform_id:
                            if table_started:
                                raise ValidationError(
                                    "GEO platform annotation repeats the requested platform table"
                                )
                            if platform_seen:
                                raise ValidationError(
                                    "GEO platform annotation repeats the requested platform"
                                )
                            platform_seen = True
                            table_started = True
                        continue
                    if line.casefold() == "!platform_table_end":
                        if table_started and not table_ended:
                            table_ended = True
                        continue
                    if not table_started or table_ended:
                        continue
                    if not line:
                        continue
                    if line.startswith("#"):
                        continue
                    if header_indices is None:
                        headers = _split_tab_record(line)
                        normalized_headers = [header.strip().casefold() for header in headers]
                        if any(not header for header in normalized_headers):
                            raise ValidationError(
                                "GEO platform annotation has an empty column name"
                            )
                        if len(set(normalized_headers)) != len(normalized_headers):
                            raise ValidationError(
                                "GEO platform annotation has duplicate column names"
                            )
                        try:
                            id_index = normalized_headers.index(normalized_id_column.casefold())
                            selected_indices = tuple(
                                normalized_headers.index(column.casefold())
                                for column in requested_columns
                            )
                        except ValueError as error:
                            raise ValidationError(
                                "a requested GEO platform annotation column is absent"
                            ) from error
                        actual_id_column = headers[id_index].strip()
                        actual_columns = tuple(headers[index].strip() for index in selected_indices)
                        header_indices = (id_index, selected_indices)
                        header_width = len(headers)
                        continue

                    fields = _split_tab_record(line)
                    id_index, selected_indices = header_indices
                    if len(fields) > header_width:
                        raise ValidationError("GEO platform annotation row has an invalid width")
                    if len(fields) < header_width:
                        fields.extend([""] * (header_width - len(fields)))
                    feature_id = fields[id_index].strip()
                    if not _FEATURE_RE.fullmatch(feature_id):
                        raise ValidationError("GEO platform annotation has an invalid feature ID")
                    if feature_id in records:
                        raise ValidationError("GEO platform annotation repeats a feature ID")
                    values = tuple(fields[index] for index in selected_indices)
                    if any(len(value) > MAX_PLATFORM_ANNOTATION_VALUE_LENGTH for value in values):
                        raise ValidationError(
                            "GEO platform annotation value exceeds its length bound"
                        )
                    retained_bytes += len(feature_id.encode("utf-8")) + sum(
                        len(value.encode("utf-8")) for value in values
                    )
                    if retained_bytes > MAX_PLATFORM_ANNOTATION_RETAINED_BYTES:
                        raise ValidationError(
                            "GEO platform annotations exceed their retained-data bound"
                        )
                    records[feature_id] = values
                    if len(records) > MAX_PLATFORM_ANNOTATION_ROWS:
                        raise ValidationError("GEO platform annotation row count exceeds its bound")

            if is_gzip:
                buffered_reader.close()
            if digesting_reader.bytes_read != source_size:
                raise ValidationError("GEO platform annotation source changed while being read")
            source_sha256 = digesting_reader.digest.hexdigest()
    except ValidationError:
        raise
    except (OSError, EOFError, gzip.BadGzipFile, zlib.error) as error:
        raise ValidationError("GEO platform annotation file is unreadable or corrupt") from error

    if not platform_seen and any_platform_seen:
        raise ValidationError("GEO platform annotation accession differs from the matrix")
    if not platform_seen or not table_started or not table_ended or header_indices is None:
        raise ValidationError("GEO platform annotation table is incomplete")
    if not records:
        raise ValidationError("GEO platform annotation table contains no feature rows")
    if actual_id_column is None:
        raise ArithmeticError("GEO platform annotation ID column was not retained")
    return GeoPlatformAnnotations(
        platform_id=platform_id,
        id_column=actual_id_column,
        annotation_columns=actual_columns,
        records=tuple(sorted(records.items())),
        source_file_name=source_path.name,
        source_sha256=source_sha256,
        source_bytes=source_size,
        decompressed_bytes=decompressed_bytes,
    )


__all__ = ["GeoPlatformAnnotations", "read_geo_platform_annotations"]
