"""Hash-chained event log for reproducibility and replay."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import RLock
from typing import Any

from .errors import ValidationError
from .serialization import canonical_bytes, content_hash, freeze_json, jsonable, utc_now

MAX_EVENT_LOG_ENTRIES = 10_000
"""Hard ceiling for events retained in one append-only log."""

MAX_EVENT_PAYLOAD_BYTES = 16 * 1024 * 1024
"""Maximum canonical JSON size of one event payload."""

MAX_EVENT_RECORD_BYTES = 64 * 1024 * 1024
"""Maximum canonical JSON size of a complete event record."""

MAX_EVENT_IDENTIFIER_LENGTH = 1_024
MAX_EVENT_TYPE_LENGTH = 256
MAX_EVENT_TIMESTAMP_LENGTH = 128

_EVENT_FIELDS = frozenset(
    {
        "event_id",
        "run_id",
        "event_type",
        "payload",
        "created_at",
        "previous_hash",
        "event_hash",
    }
)
_RECORD_FIELDS = frozenset({"run_id", "events"})
_SHA256_ADDRESS = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _required_string(value: object, field_name: str, *, maximum: int) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    if len(value) > maximum:
        raise ValueError(f"{field_name} exceeds the maximum length of {maximum}")
    return value


def _sha256_address(value: object, field_name: str) -> str:
    if type(value) is not str or _SHA256_ADDRESS.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a canonical sha256 address")
    return value


def _created_at(value: object) -> str:
    timestamp = _required_string(
        value,
        "event created_at",
        maximum=MAX_EVENT_TIMESTAMP_LENGTH,
    )
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise ValueError("event created_at must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("event created_at must use the UTC +00:00 offset")
    if parsed.isoformat() != timestamp:
        raise ValueError("event created_at must use canonical datetime.isoformat() spelling")
    return timestamp


def _frozen_payload(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("event payload must be an object")
    try:
        frozen = freeze_json(value, field="event payload")
        payload_size = len(canonical_bytes(frozen))
    except (RecursionError, TypeError, ValidationError, ValueError) as exc:
        raise ValueError(f"event payload is not canonical JSON: {exc}") from exc
    if payload_size > MAX_EVENT_PAYLOAD_BYTES:
        raise ValueError(
            "event payload exceeds the maximum canonical size of "
            f"{MAX_EVENT_PAYLOAD_BYTES} bytes"
        )
    return frozen


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    """A hash-sealed event whose nested payload is recursively immutable."""

    event_id: str
    run_id: str
    event_type: str
    payload: Mapping[str, Any]
    created_at: str = field(default_factory=lambda: utc_now().isoformat())
    previous_hash: str | None = None
    event_hash: str = ""

    def __post_init__(self) -> None:
        _required_string(
            self.event_id,
            "event event_id",
            maximum=MAX_EVENT_IDENTIFIER_LENGTH,
        )
        _required_string(self.run_id, "event run_id", maximum=MAX_EVENT_IDENTIFIER_LENGTH)
        _required_string(
            self.event_type,
            "event event_type",
            maximum=MAX_EVENT_TYPE_LENGTH,
        )
        _created_at(self.created_at)
        if self.previous_hash is not None:
            _sha256_address(self.previous_hash, "event previous_hash")
        if self.event_hash:
            _sha256_address(self.event_hash, "event event_hash")
        elif type(self.event_hash) is not str:
            raise ValueError("event event_hash must be a string")
        object.__setattr__(self, "payload", _frozen_payload(self.payload))
        if self.event_hash and content_hash(self._unsigned_body()) != self.event_hash:
            raise ValueError("event hash does not match its canonical signed fields")

    def _unsigned_body(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "created_at": self.created_at,
            "previous_hash": self.previous_hash,
        }

    def seal(self) -> RuntimeEvent:
        body = self._unsigned_body()
        return RuntimeEvent(**body, event_hash=content_hash(body))

    def to_dict(self) -> dict[str, Any]:
        """Return a detached canonical JSON representation."""

        return jsonable(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> RuntimeEvent:
        """Strictly rehydrate one sealed v1 event without changing its identity."""

        if not isinstance(raw, Mapping):
            raise ValueError("event record entry must be an object")
        if any(type(key) is not str for key in raw):
            raise ValueError("event record entry field names must be strings")
        fields = frozenset(raw)
        if fields != _EVENT_FIELDS:
            missing = sorted(_EVENT_FIELDS - fields)
            unknown = sorted(fields - _EVENT_FIELDS)
            details = []
            if missing:
                details.append(f"missing fields: {missing}")
            if unknown:
                details.append(f"unknown fields: {unknown}")
            raise ValueError(f"event record entry has an invalid shape ({'; '.join(details)})")
        if type(raw["payload"]) is not dict:
            raise ValueError("event payload must be an object")
        event_hash = _sha256_address(raw["event_hash"], "event event_hash")
        previous_hash_raw = raw["previous_hash"]
        previous_hash = (
            None
            if previous_hash_raw is None
            else _sha256_address(previous_hash_raw, "event previous_hash")
        )
        return cls(
            event_id=_required_string(
                raw["event_id"],
                "event event_id",
                maximum=MAX_EVENT_IDENTIFIER_LENGTH,
            ),
            run_id=_required_string(
                raw["run_id"],
                "event run_id",
                maximum=MAX_EVENT_IDENTIFIER_LENGTH,
            ),
            event_type=_required_string(
                raw["event_type"],
                "event event_type",
                maximum=MAX_EVENT_TYPE_LENGTH,
            ),
            payload=raw["payload"],
            created_at=_created_at(raw["created_at"]),
            previous_hash=previous_hash,
            event_hash=event_hash,
        )


class EventLog:
    """Bounded ordered event collection with strict chain verification."""

    def __init__(self, run_id: str) -> None:
        self.run_id = _required_string(
            run_id,
            "event record run_id",
            maximum=MAX_EVENT_IDENTIFIER_LENGTH,
        )
        self._events: list[RuntimeEvent] = []
        self._event_ids: set[str] = set()
        self._lock = RLock()
        self._record_bytes = len(canonical_bytes({"run_id": self.run_id, "events": []}))
        if self._record_bytes > MAX_EVENT_RECORD_BYTES:
            raise ValueError(
                "event record exceeds the maximum canonical size of "
                f"{MAX_EVENT_RECORD_BYTES} bytes"
            )

    @property
    def head(self) -> str:
        with self._lock:
            return self._events[-1].event_hash if self._events else "genesis"

    @property
    def record_address(self) -> str:
        """Return the content address of the complete canonical v1 record."""

        return content_hash(self.to_record())

    def append(
        self,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        event_id: str,
    ) -> RuntimeEvent:
        """Append one sealed event atomically after all bounds and identity checks pass."""

        event_id = _required_string(
            event_id,
            "event event_id",
            maximum=MAX_EVENT_IDENTIFIER_LENGTH,
        )
        event_type = _required_string(
            event_type,
            "event event_type",
            maximum=MAX_EVENT_TYPE_LENGTH,
        )
        with self._lock:
            if len(self._events) >= MAX_EVENT_LOG_ENTRIES:
                raise ValueError(f"event log cannot exceed {MAX_EVENT_LOG_ENTRIES} entries")
            if event_id in self._event_ids:
                raise ValueError(f"event_id already exists in this log: {event_id!r}")
            event = RuntimeEvent(
                event_id=event_id,
                run_id=self.run_id,
                event_type=event_type,
                payload=payload,
                previous_hash=self._events[-1].event_hash if self._events else None,
            ).seal()
            self._append_validated(event)
            return event

    def _append_validated(self, event: RuntimeEvent) -> None:
        expected_previous = self._events[-1].event_hash if self._events else None
        if event.run_id != self.run_id:
            raise ValueError("event run_id does not match event record")
        if event.event_id in self._event_ids:
            raise ValueError(f"duplicate event_id in event record: {event.event_id!r}")
        if event.previous_hash != expected_previous:
            raise ValueError("event previous_hash does not close over the preceding event")
        if not event.event_hash or event.seal().event_hash != event.event_hash:
            raise ValueError("event hash does not match its canonical signed fields")
        event_size = len(canonical_bytes(event.to_dict()))
        projected_size = self._record_bytes + event_size + (1 if self._events else 0)
        if projected_size > MAX_EVENT_RECORD_BYTES:
            raise ValueError(
                "event record exceeds the maximum canonical size of "
                f"{MAX_EVENT_RECORD_BYTES} bytes"
            )
        self._events.append(event)
        self._event_ids.add(event.event_id)
        self._record_bytes = projected_size

    def all(self) -> tuple[RuntimeEvent, ...]:
        with self._lock:
            return tuple(self._events)

    @classmethod
    def from_record(
        cls,
        raw: Mapping[str, Any],
        *,
        expected_address: str | None = None,
    ) -> EventLog:
        """Strictly hydrate and verify a canonical generated-v1 event record.

        ``expected_address`` closes the stored JSON object over its external
        content-addressed pointer when the caller has that pointer available.
        """

        if not isinstance(raw, Mapping):
            raise ValueError("event record must be an object")
        if any(type(key) is not str for key in raw):
            raise ValueError("event record field names must be strings")
        fields = frozenset(raw)
        if fields != _RECORD_FIELDS:
            missing = sorted(_RECORD_FIELDS - fields)
            unknown = sorted(fields - _RECORD_FIELDS)
            details = []
            if missing:
                details.append(f"missing fields: {missing}")
            if unknown:
                details.append(f"unknown fields: {unknown}")
            raise ValueError(f"event record has an invalid shape ({'; '.join(details)})")
        run_id = _required_string(
            raw["run_id"],
            "event record run_id",
            maximum=MAX_EVENT_IDENTIFIER_LENGTH,
        )
        event_rows = raw["events"]
        if type(event_rows) is not list:
            raise ValueError("event record events must be an array")
        if len(event_rows) > MAX_EVENT_LOG_ENTRIES:
            raise ValueError(f"event record cannot exceed {MAX_EVENT_LOG_ENTRIES} entries")
        log = cls(run_id)
        for event_raw in event_rows:
            if type(event_raw) is not dict:
                raise ValueError("event record entries must be objects")
            log._append_validated(RuntimeEvent.from_dict(event_raw))
        if expected_address is not None:
            address = _sha256_address(expected_address, "expected event record address")
            if log.record_address != address:
                raise ValueError("event record does not match its expected content address")
        return log

    def to_record(self) -> dict[str, Any]:
        """Return a detached canonical persisted event record."""

        with self._lock:
            return {"run_id": self.run_id, "events": [event.to_dict() for event in self._events]}

    def verify(self) -> bool:
        """Verify run closure, unique IDs, links, hashes, and configured bounds."""

        with self._lock:
            if len(self._events) > MAX_EVENT_LOG_ENTRIES:
                return False
            previous: str | None = None
            event_ids: set[str] = set()
            record_bytes = len(canonical_bytes({"run_id": self.run_id, "events": []}))
            try:
                for event in self._events:
                    if not isinstance(event, RuntimeEvent):
                        return False
                    if event.run_id != self.run_id or event.event_id in event_ids:
                        return False
                    if event.previous_hash != previous:
                        return False
                    if not event.event_hash or event.seal().event_hash != event.event_hash:
                        return False
                    record_bytes += len(canonical_bytes(event.to_dict()))
                    if event_ids:
                        record_bytes += 1
                    if record_bytes > MAX_EVENT_RECORD_BYTES:
                        return False
                    event_ids.add(event.event_id)
                    previous = event.event_hash
            except (RecursionError, TypeError, ValidationError, ValueError):
                return False
            return event_ids == self._event_ids and record_bytes == self._record_bytes
