"""Hash-chained event log for reproducibility and replay."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .serialization import content_hash, jsonable, utc_now


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    """A signed-by-hash event with no destructive updates."""

    event_id: str
    run_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: str = field(default_factory=lambda: utc_now().isoformat())
    previous_hash: str | None = None
    event_hash: str = ""

    def seal(self) -> RuntimeEvent:
        body = {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "created_at": self.created_at,
            "previous_hash": self.previous_hash,
        }
        return RuntimeEvent(**body, event_hash=content_hash(body))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> RuntimeEvent:
        """Rehydrate one sealed event without changing its stored hash."""

        return cls(
            event_id=str(raw.get("event_id", "")),
            run_id=str(raw.get("run_id", "")),
            event_type=str(raw.get("event_type", "")),
            payload=dict(raw.get("payload", {})),
            created_at=str(raw.get("created_at", "")),
            previous_hash=raw.get("previous_hash"),
            event_hash=str(raw.get("event_hash", "")),
        )


class EventLog:
    """Ordered event collection with chain verification."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._events: list[RuntimeEvent] = []

    @property
    def head(self) -> str:
        return self._events[-1].event_hash if self._events else "genesis"

    def append(self, event_type: str, payload: dict[str, Any], *, event_id: str) -> RuntimeEvent:
        event = RuntimeEvent(
            event_id=event_id,
            run_id=self.run_id,
            event_type=event_type,
            payload=payload,
            previous_hash=self._events[-1].event_hash if self._events else None,
        ).seal()
        self._events.append(event)
        return event

    def all(self) -> tuple[RuntimeEvent, ...]:
        return tuple(self._events)

    @classmethod
    def from_record(cls, raw: Mapping[str, Any]) -> EventLog:
        """Hydrate an event record for append-only continuation."""

        run_id = str(raw.get("run_id", ""))
        if not run_id:
            raise ValueError("event record requires a run_id")
        log = cls(run_id)
        for event_raw in raw.get("events", ()):
            if not isinstance(event_raw, Mapping):
                raise ValueError("event record entries must be objects")
            event = RuntimeEvent.from_dict(event_raw)
            if event.run_id != run_id:
                raise ValueError("event run_id does not match event record")
            log._events.append(event)
        return log

    def to_record(self) -> dict[str, Any]:
        """Return the canonical persisted event record."""

        return {"run_id": self.run_id, "events": [event.to_dict() for event in self.all()]}

    def verify(self) -> bool:
        previous: str | None = None
        for event in self._events:
            if event.previous_hash != previous:
                return False
            if event.seal().event_hash != event.event_hash:
                return False
            previous = event.event_hash
        return True
