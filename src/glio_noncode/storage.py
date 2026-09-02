"""Local content-addressed storage for replayable case artifacts."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from threading import Lock, RLock
from typing import Any

from .errors import StoreError
from .serialization import canonical_json, content_hash

_RUN_ID_RE = re.compile(r"run-[A-Za-z0-9][A-Za-z0-9._-]{0,123}\Z")
_RUN_LOCKS: dict[str, RLock] = {}
_RUN_LOCKS_GUARD = Lock()


def _atomic_write_text(path: Path, text: str) -> None:
    """Atomically replace one file using a flushed unique sibling temporary."""

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _run_lock(root: Path) -> RLock:
    key = os.path.normcase(str(root.resolve()))
    with _RUN_LOCKS_GUARD:
        return _RUN_LOCKS.setdefault(key, RLock())


class ObjectStore:
    """Store immutable JSON objects under a hash-derived path."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.objects = self.root / "objects"
        self.objects.mkdir(parents=True, exist_ok=True)

    def put(self, value: Any) -> str:
        address = content_hash(value)
        self.put_at(address, value)
        return address

    def put_at(self, address: str, value: Any) -> str:
        """Write an object at a previously computed canonical address."""

        if not address.startswith("sha256:"):
            raise StoreError(f"unsupported object address: {address}")
        digest = address.split(":", 1)[1]
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise StoreError(f"invalid object address: {address}")
        path = self.objects / f"{digest}.json"
        serialized = canonical_json(value)
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise StoreError(f"invalid stored object: {address}") from exc
            if canonical_json(existing) != serialized:
                raise StoreError(f"stored object differs at immutable address: {address}")
        else:
            _atomic_write_text(path, serialized)
        return address

    def get(self, address: str) -> Any:
        if not address.startswith("sha256:"):
            raise StoreError(f"unsupported object address: {address}")
        digest = address.split(":", 1)[1]
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise StoreError(f"invalid object address: {address}")
        path = self.objects / f"{digest}.json"
        if not path.exists():
            raise StoreError(f"object not found: {address}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StoreError(f"invalid stored object: {address}") from exc

    def exists(self, address: str) -> bool:
        if not address.startswith("sha256:"):
            return False
        digest = address.split(":", 1)[1]
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            return False
        return (self.objects / f"{digest}.json").exists()


class RunStore:
    """Small index over immutable run artifacts."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.store = ObjectStore(self.root)
        self.runs = self.root / "runs"
        self.runs.mkdir(parents=True, exist_ok=True)
        self._lock = _run_lock(self.runs)

    def _run_path(self, run_id: str) -> Path:
        if (
            not isinstance(run_id, str)
            or not _RUN_ID_RE.fullmatch(run_id)
            or ".." in run_id
        ):
            raise StoreError("invalid run_id")
        return self.runs / f"{run_id}.json"

    def save_run(
        self,
        run_id: str,
        *,
        input_address: str,
        event_address: str,
        dossier_address: str,
        dossier_history: tuple[str, ...] | None = None,
    ) -> Path:
        """Persist the current run pointers and retain every dossier address.

        Older run records do not contain ``dossier_history``.  They are upgraded
        deterministically on the next write by retaining their current pointer
        before appending the new snapshot address.
        """

        path = self._run_path(run_id)
        with self._lock:
            previous: dict[str, Any] = {}
            if path.exists():
                try:
                    stored = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    raise StoreError(f"invalid run record: {path.name}") from exc
                if not isinstance(stored, dict):
                    raise StoreError(f"run record must be an object: {path.name}")
                previous = stored

            history = list(dossier_history or previous.get("dossier_history", ()))
            previous_address = str(previous.get("dossier_address", ""))
            if previous_address and previous_address not in history:
                history.append(previous_address)
            if dossier_address not in history:
                history.append(dossier_address)
            event_history_raw = previous.get("event_history", ())
            event_history = (
                list(event_history_raw)
                if isinstance(event_history_raw, (list, tuple))
                else []
            )
            previous_event_address = str(previous.get("event_address", ""))
            if previous_event_address and previous_event_address not in event_history:
                event_history.append(previous_event_address)
            if event_address not in event_history:
                event_history.append(event_address)
            record = {
                "run_id": run_id,
                "input_address": input_address,
                "event_address": event_address,
                "event_history": event_history,
                "dossier_address": dossier_address,
                "dossier_history": history,
            }
            _atomic_write_text(path, canonical_json(record))
        return path

    def get_run(self, run_id: str) -> dict[str, Any]:
        path = self._run_path(run_id)
        if not path.exists():
            raise StoreError(f"run not found: {run_id}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StoreError(f"invalid run record: {path.name}") from exc
        if not isinstance(value, dict):
            raise StoreError(f"run record must be an object: {path.name}")
        return value

    def list_runs(self) -> tuple[dict[str, Any], ...]:
        """Return every persisted run record in deterministic run-id order."""

        records: list[dict[str, Any]] = []
        for path in sorted(self.runs.glob("run-*.json"), key=lambda item: item.name):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise StoreError(f"invalid run record: {path.name}") from exc
            if not isinstance(value, dict):
                raise StoreError(f"run record must be an object: {path.name}")
            records.append(value)
        return tuple(records)
