"""Dependency-free BCF2 reader for bounded variant intake.

This module implements the parts of BCF2 required to preserve ordinary small
variant records: BGZF member decompression, the BCF2 fixed record header, typed
strings/vectors, INFO/FILTER fields, and FORMAT/sample values.  Unsupported
typed atoms or malformed blocks produce a typed validation error rather than a
partially decoded variant.  It intentionally does not attempt random access or
index generation; those belong to a future indexed-data capability.
"""

from __future__ import annotations

import re
import struct
import zlib
from collections.abc import Mapping
from dataclasses import dataclass
from math import isnan
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

_MISSING_INT8 = -128
_MISSING_INT16 = -32768
_MISSING_INT32 = -2147483648
_MISSING_FLOAT = 0x7F800001
_HEADER_ID = re.compile(r"<ID=([^,>]+)")


@dataclass(frozen=True, slots=True)
class BcfRecord:
    """Decoded BCF record in a lossless-enough intake representation."""

    record_index: int
    chromosome: str
    position: int
    reference: str
    alternates: tuple[str, ...]
    record_id: str
    quality: float | None
    filters: tuple[str, ...]
    info: Mapping[str, Any]
    samples: Mapping[str, Mapping[str, Any]]
    raw_hash: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BcfDocument:
    """Decoded header and records with compression accounting."""

    version: str
    header_text: str
    contigs: tuple[str, ...]
    filter_names: tuple[str, ...]
    info_names: tuple[str, ...]
    format_names: tuple[str, ...]
    samples: tuple[str, ...]
    records: tuple[BcfRecord, ...]
    bgzf_blocks: int
    input_hash: str
    content_address: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class _Cursor:
    """Bounds-checked little-endian cursor over one decompressed BCF stream."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    def take(self, length: int, field: str) -> bytes:
        if length < 0 or self.offset + length > len(self.data):
            raise ValidationError(f"BCF truncated while reading {field}")
        value = self.data[self.offset : self.offset + length]
        self.offset += length
        return value

    def u8(self, field: str) -> int:
        return self.take(1, field)[0]

    def u16(self, field: str) -> int:
        return struct.unpack("<H", self.take(2, field))[0]

    def u32(self, field: str) -> int:
        return struct.unpack("<I", self.take(4, field))[0]

    def i8(self, field: str) -> int:
        return struct.unpack("<b", self.take(1, field))[0]

    def i16(self, field: str) -> int:
        return struct.unpack("<h", self.take(2, field))[0]

    def i32(self, field: str) -> int:
        return struct.unpack("<i", self.take(4, field))[0]

    def f32(self, field: str) -> float:
        return struct.unpack("<f", self.take(4, field))[0]


@dataclass(frozen=True, slots=True)
class _TypedValue:
    value: Any
    type_code: int
    length: int


class BcfReader:
    """Read BCF2.1/2.2 bytes, including concatenated BGZF members."""

    _supported_types = frozenset({1, 2, 3, 5, 7})

    def read(self, data: bytes) -> BcfDocument:
        if not isinstance(data, bytes) or not data:
            raise ValidationError("BCF input must be non-empty bytes")
        input_hash = content_hash(data.hex())
        decoded, block_count = self._decompress(data)
        cursor = _Cursor(decoded)
        magic = cursor.take(5, "magic")
        if magic[:3] != b"BCF" or magic[3] != 2:
            raise ValidationError(f"unsupported BCF magic: {magic!r}")
        version = f"{magic[3]}.{magic[4]}"
        header_length = cursor.u32("header length")
        header_bytes = cursor.take(header_length, "header text")
        header_text = header_bytes.rstrip(b"\x00").decode("utf-8", errors="strict")
        header = self._parse_header(header_text)
        records: list[BcfRecord] = []
        index = 0
        while cursor.offset < len(decoded):
            if len(decoded) - cursor.offset < 8:
                trailing = decoded[cursor.offset :]
                if trailing and any(trailing):
                    raise ValidationError("BCF has a non-zero truncated record trailer")
                break
            shared_length = cursor.u32("shared record length")
            individual_length = cursor.u32("individual record length")
            shared = cursor.take(shared_length, "shared record")
            individual = cursor.take(individual_length, "individual record")
            records.append(self._record(index, shared, individual, header))
            index += 1
        body = {
            "version": version,
            "header_text": header_text,
            "records": records,
            "bgzf_blocks": block_count,
        }
        return BcfDocument(
            version=version,
            header_text=header_text,
            contigs=header["contigs"],
            filter_names=header["filters"],
            info_names=header["infos"],
            format_names=header["formats"],
            samples=header["samples"],
            records=tuple(records),
            bgzf_blocks=block_count,
            input_hash=input_hash,
            content_address=content_hash(body),
        )

    @staticmethod
    def _decompress(data: bytes) -> tuple[bytes, int]:
        if data[:3] == b"BCF":
            return data, 0
        output = bytearray()
        offset = 0
        blocks = 0
        while offset < len(data):
            if data[offset : offset + 2] != b"\x1f\x8b":
                raise ValidationError("BCF input is neither raw BCF nor BGZF")
            if offset + 12 > len(data):
                raise ValidationError("truncated BGZF header")
            if data[offset + 3] & 4 == 0:
                raise ValidationError("gzip member lacks the BGZF extra field")
            extra_length = struct.unpack_from("<H", data, offset + 10)[0]
            extra_start = offset + 12
            extra_end = extra_start + extra_length
            if extra_end > len(data):
                raise ValidationError("truncated BGZF extra field")
            block_size: int | None = None
            cursor = extra_start
            while cursor + 4 <= extra_end:
                subfield = data[cursor : cursor + 2]
                length = struct.unpack_from("<H", data, cursor + 2)[0]
                value_start = cursor + 4
                value_end = value_start + length
                if value_end > extra_end:
                    raise ValidationError("invalid BGZF subfield length")
                if subfield == b"BC" and length == 2:
                    block_size = struct.unpack_from("<H", data, value_start)[0] + 1
                cursor = value_end
            if block_size is None or offset + block_size > len(data):
                raise ValidationError("BGZF BC subfield or block size is missing")
            block = data[offset : offset + block_size]
            try:
                output.extend(zlib.decompress(block, wbits=31))
            except zlib.error as exc:
                raise ValidationError(f"invalid BGZF compressed block: {exc}") from exc
            blocks += 1
            offset += block_size
        return bytes(output), blocks

    @staticmethod
    def _parse_header(text: str) -> dict[str, Any]:
        contigs: list[str] = []
        filters: list[str] = ["PASS"]
        infos: list[str] = []
        formats: list[str] = []
        samples: tuple[str, ...] = ()
        for line in text.splitlines():
            if line.startswith("##contig=<"):
                match = _HEADER_ID.search(line)
                if match:
                    contigs.append(match.group(1))
            elif line.startswith("##FILTER=<"):
                match = _HEADER_ID.search(line)
                if match and match.group(1) not in filters:
                    filters.append(match.group(1))
            elif line.startswith("##INFO=<"):
                match = _HEADER_ID.search(line)
                if match:
                    infos.append(match.group(1))
            elif line.startswith("##FORMAT=<"):
                match = _HEADER_ID.search(line)
                if match:
                    formats.append(match.group(1))
            elif line.startswith("#CHROM"):
                columns = line.split("\t")
                samples = tuple(columns[9:])
        if not contigs:
            raise ValidationError("BCF header must declare at least one contig")
        return {
            "contigs": tuple(contigs),
            "filters": tuple(filters),
            "infos": tuple(infos),
            "formats": tuple(formats),
            "samples": samples,
        }

    def _record(
        self,
        index: int,
        shared_data: bytes,
        individual_data: bytes,
        header: Mapping[str, Any],
    ) -> BcfRecord:
        shared = _Cursor(shared_data)
        chrom_index = shared.i32("CHROM")
        position = shared.i32("POS") + 1
        shared.i32("rlen")
        quality = shared.f32("QUAL")
        n_allele_info = shared.u32("n_allele_info")
        n_fmt_sample = shared.u32("n_fmt_sample")
        n_alleles = n_allele_info & 0xFFFF
        n_info = n_allele_info >> 16
        n_formats = n_fmt_sample >> 24
        n_samples = n_fmt_sample & 0xFFFFFF
        contigs = header["contigs"]
        if chrom_index < 0 or chrom_index >= len(contigs):
            raise ValidationError(f"BCF record references unknown contig index {chrom_index}")
        record_id = self._typed_string(shared, "ID")
        alleles = tuple(self._typed_string(shared, "allele") for _ in range(n_alleles))
        if len(alleles) < 1 or not alleles[0]:
            raise ValidationError(f"BCF record {index} has no REF allele")
        filters = self._filters(shared, header["filters"])
        info: dict[str, Any] = {}
        for _ in range(n_info):
            key_index = self._typed_scalar_int(shared, "INFO key")
            if key_index < 0 or key_index >= len(header["infos"]):
                raise ValidationError(f"BCF record {index} references unknown INFO key {key_index}")
            info[header["infos"][key_index]] = self._typed(shared, "INFO value").value
        individual = _Cursor(individual_data)
        sample_names = tuple(header["samples"])
        if n_samples != len(sample_names):
            raise ValidationError(
                f"BCF record {index} declares {n_samples} samples but header "
                f"has {len(sample_names)}"
            )
        samples: dict[str, dict[str, Any]] = {name: {} for name in sample_names}
        for _ in range(n_formats):
            key_index = self._typed_scalar_int(individual, "FORMAT key")
            if key_index < 0 or key_index >= len(header["formats"]):
                raise ValidationError(
                    f"BCF record {index} references unknown FORMAT key {key_index}"
                )
            key = header["formats"][key_index]
            value = self._typed(individual, f"FORMAT {key}")
            values = value.value if isinstance(value.value, list) else [value.value]
            if n_samples:
                width = len(values) // n_samples
                if width * n_samples != len(values):
                    raise ValidationError(
                        f"BCF FORMAT {key} vector is not divisible by sample count"
                    )
                for sample_index, name in enumerate(sample_names):
                    sample_values = values[sample_index * width : (sample_index + 1) * width]
                    samples[name][key] = self._format_sample_value(key, sample_values)
        if shared.offset != len(shared_data) or individual.offset != len(individual_data):
            raise ValidationError(f"BCF record {index} has unconsumed field bytes")
        if quality is not None and (
            isnan(quality) or quality == struct.unpack("<f", struct.pack("<I", _MISSING_FLOAT))[0]
        ):
            quality = None
        return BcfRecord(
            record_index=index,
            chromosome=str(contigs[chrom_index]),
            position=position,
            reference=alleles[0],
            alternates=tuple(alleles[1:]),
            record_id=record_id or f"bcf:{index + 1}",
            quality=quality,
            filters=filters,
            info=info,
            samples=samples,
            raw_hash=content_hash(
                {"shared": shared_data.hex(), "individual": individual_data.hex()}
            ),
        )

    def _typed_string(self, cursor: _Cursor, field: str) -> str:
        value = self._typed(cursor, field)
        if value.type_code != 7:
            raise ValidationError(f"BCF {field} is not a typed string")
        if value.value is None:
            return ""
        return str(value.value)

    def _typed_scalar_int(self, cursor: _Cursor, field: str) -> int:
        value = self._typed(cursor, field)
        if value.type_code not in {1, 2, 3}:
            raise ValidationError(f"BCF {field} is not an integer")
        if isinstance(value.value, list):
            if len(value.value) != 1:
                raise ValidationError(f"BCF {field} must contain one integer")
            scalar = value.value[0]
        else:
            scalar = value.value
        if scalar is None:
            raise ValidationError(f"BCF {field} is missing")
        return int(scalar)

    def _filters(self, cursor: _Cursor, names: tuple[str, ...]) -> tuple[str, ...]:
        value = self._typed(cursor, "FILTER")
        values = value.value if isinstance(value.value, list) else [value.value]
        output: list[str] = []
        for raw in values:
            if raw is None:
                continue
            index = int(raw)
            if index < 0 or index >= len(names):
                raise ValidationError(f"BCF FILTER index is unknown: {index}")
            output.append(names[index])
        return tuple(output or ["PASS"])

    def _typed(self, cursor: _Cursor, field: str) -> _TypedValue:
        typing = cursor.u8(f"{field} typing byte")
        length = typing >> 4
        type_code = typing & 0x0F
        if type_code == 0:
            if length != 0:
                raise ValidationError(f"BCF {field} has invalid missing type")
            return _TypedValue(None, type_code, 0)
        if type_code not in self._supported_types:
            raise ValidationError(f"BCF {field} uses unsupported type code {type_code}")
        if length == 15:
            length_value = self._typed(cursor, f"{field} length")
            if length_value.type_code not in {1, 2, 3}:
                raise ValidationError(f"BCF {field} length is not integer encoded")
            length = int(
                length_value.value[0]
                if isinstance(length_value.value, list)
                else length_value.value
            )
        if length < 0:
            raise ValidationError(f"BCF {field} has negative vector length")
        if type_code == 1:
            raw_values = [cursor.i8(field) for _ in range(length)]
            missing = _MISSING_INT8
        elif type_code == 2:
            raw_values = [cursor.i16(field) for _ in range(length)]
            missing = _MISSING_INT16
        elif type_code == 3:
            raw_values = [cursor.i32(field) for _ in range(length)]
            missing = _MISSING_INT32
        elif type_code == 5:
            raw_values = [cursor.f32(field) for _ in range(length)]
            missing = None
        else:
            raw_bytes = cursor.take(length, field)
            value = raw_bytes.rstrip(b"\x00").decode("utf-8", errors="strict")
            return _TypedValue(value, type_code, length)
        values: list[Any] = []
        for raw in raw_values:
            if type_code in {1, 2, 3} and raw == missing:
                values.append(None)
            elif (
                type_code == 5 and struct.unpack("<I", struct.pack("<f", raw))[0] == _MISSING_FLOAT
            ):
                values.append(None)
            else:
                values.append(raw)
        if length == 0:
            return _TypedValue([], type_code, length)
        return _TypedValue(values[0] if length == 1 else values, type_code, length)

    @staticmethod
    def _format_sample_value(key: str, values: list[Any]) -> Any:
        if key == "GT":
            alleles: list[str] = []
            separators: list[str] = []
            for index, raw in enumerate(values):
                if raw is None:
                    alleles.append(".")
                    separators.append("/")
                    continue
                encoded = int(raw)
                phased = bool(encoded & 1)
                allele = (encoded >> 1) - 1
                alleles.append("." if allele < 0 else str(allele))
                if index:
                    separators.append("|" if phased else "/")
            if not alleles:
                return "."
            return alleles[0] + "".join(
                separators[index - 1] + allele for index, allele in enumerate(alleles[1:], start=1)
            )
        if len(values) == 1:
            return values[0]
        return values
