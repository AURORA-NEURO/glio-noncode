"""Local content-addressed storage for replayable case artifacts."""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from errno import EACCES, EAGAIN
from pathlib import Path
from threading import Lock, RLock
from typing import Any

from .errors import StoreError
from .serialization import canonical_json, content_hash

_RUN_ID_RE = re.compile(r"run-[A-Za-z0-9][A-Za-z0-9._-]{0,123}\Z")
_RUN_LOCKS: dict[str, RLock] = {}
_RUN_LOCKS_GUARD = Lock()
_FILESYSTEM_LOCK_TIMEOUT_SECONDS = 30.0
_FILESYSTEM_LOCK_POLL_SECONDS = 0.01
MAX_RUN_HISTORY_ENTRIES = 1_000


def _sync_directory(path: Path) -> None:
    """Best-effort metadata durability after a same-directory rename."""

    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


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
        _sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _run_lock(root: Path) -> RLock:
    key = os.path.normcase(str(root.resolve()))
    with _RUN_LOCKS_GUARD:
        return _RUN_LOCKS.setdefault(key, RLock())


def _try_filesystem_lock(handle: Any) -> bool:
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno in {EACCES, EAGAIN} or getattr(exc, "winerror", None) in {33, 36}:
            return False
        raise StoreError("filesystem lock acquisition failed") from exc
    return True


def _release_filesystem_lock(handle: Any) -> None:
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError as exc:
        raise StoreError("filesystem lock release failed") from exc


@contextmanager
def _filesystem_lock(path: Path) -> Iterator[None]:
    """Hold one crash-released advisory lock across processes."""

    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + _FILESYSTEM_LOCK_TIMEOUT_SECONDS
    with path.open("a+b", buffering=0) as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        acquired = False
        while not acquired:
            acquired = _try_filesystem_lock(handle)
            if acquired:
                break
            if time.monotonic() >= deadline:
                raise StoreError(f"timed out acquiring filesystem lock: {path.name}")
            time.sleep(_FILESYSTEM_LOCK_POLL_SECONDS)
        try:
            yield
        finally:
            _release_filesystem_lock(handle)


def _address_digest(address: object, *, label: str = "object address") -> str:
    if not isinstance(address, str) or not address.startswith("sha256:"):
        raise StoreError(f"unsupported {label}: {address}")
    digest = address.split(":", 1)[1]
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise StoreError(f"invalid {label}: {address}")
    return digest


def _history_values(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise StoreError(f"{label} must be an array")
    if len(value) > MAX_RUN_HISTORY_ENTRIES:
        raise StoreError(f"{label} exceeds {MAX_RUN_HISTORY_ENTRIES} entries")
    items = tuple(value)
    for item in items:
        _address_digest(item, label=f"{label} address")
    if len(items) != len(set(items)):
        raise StoreError(f"{label} must contain unique addresses")
    return items


class ObjectStore:
    """Store immutable JSON objects under a hash-derived path."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.objects = self.root / "objects"
        self.objects.mkdir(parents=True, exist_ok=True)
        self._locks = self.root / ".locks" / "objects"
        self._locks.mkdir(parents=True, exist_ok=True)
        self._lock = _run_lock(self.objects)

    def put(self, value: Any) -> str:
        address = content_hash(value)
        self.put_at(address, value)
        return address

    def put_at(self, address: str, value: Any) -> str:
        """Write an object at a previously computed canonical address."""

        digest = _address_digest(address)
        path = self.objects / f"{digest}.json"
        serialized = canonical_json(value)
        with self._lock, _filesystem_lock(self._locks / f"{digest}.lock"):
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
        digest = _address_digest(address)
        path = self.objects / f"{digest}.json"
        if not path.exists():
            raise StoreError(f"object not found: {address}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StoreError(f"invalid stored object: {address}") from exc

    def exists(self, address: str) -> bool:
        try:
            digest = _address_digest(address)
        except StoreError:
            return False
        return (self.objects / f"{digest}.json").exists()


class RunStore:
    """Small index over immutable run artifacts."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.store = ObjectStore(self.root)
        self.runs = self.root / "runs"
        self.runs.mkdir(parents=True, exist_ok=True)
        self._locks = self.root / ".locks" / "runs"
        self._locks.mkdir(parents=True, exist_ok=True)
        self._lock = _run_lock(self.runs)

    def _run_path(self, run_id: str) -> Path:
        if not isinstance(run_id, str) or not _RUN_ID_RE.fullmatch(run_id) or ".." in run_id:
            raise StoreError("invalid run_id")
        return self.runs / f"{run_id}.json"

    def _read_run_bytes(self, run_id: str) -> bytes:
        """Return one stable run-index snapshot under its writer lock."""

        path = self._run_path(run_id)
        with self._lock, _filesystem_lock(self._locks / f"{run_id}.lock"):
            if not path.exists():
                raise StoreError(f"run not found: {run_id}")
            try:
                return path.read_bytes()
            except OSError as exc:
                raise StoreError(f"run record could not be read: {path.name}") from exc

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
        _address_digest(input_address, label="input address")
        _address_digest(event_address, label="event address")
        _address_digest(dossier_address, label="dossier address")
        declared_history = (
            () if dossier_history is None else _history_values(dossier_history, "dossier_history")
        )
        with self._lock, _filesystem_lock(self._locks / f"{run_id}.lock"):
            previous: dict[str, Any] = {}
            if path.exists():
                try:
                    stored = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    raise StoreError(f"invalid run record: {path.name}") from exc
                if not isinstance(stored, dict):
                    raise StoreError(f"run record must be an object: {path.name}")
                previous = stored

            if previous:
                if previous.get("run_id") != run_id:
                    raise StoreError("stored run_id does not match its index filename")
                if previous.get("input_address") != input_address:
                    raise StoreError("run input_address is immutable")
            previous_history = _history_values(
                previous.get("dossier_history", ()),
                "stored dossier_history",
            )
            previous_event_history = _history_values(
                previous.get("event_history", ()),
                "stored event_history",
            )
            history = list(dict.fromkeys((*previous_history, *declared_history)))
            previous_address = previous.get("dossier_address")
            if previous_address is not None:
                _address_digest(previous_address, label="stored dossier address")
                if previous_address not in history:
                    history.append(previous_address)
            if dossier_address not in history:
                history.append(dossier_address)
            event_history = list(previous_event_history)
            previous_event_address = previous.get("event_address")
            if previous_event_address is not None:
                _address_digest(previous_event_address, label="stored event address")
                if previous_event_address not in event_history:
                    event_history.append(previous_event_address)
            if event_address not in event_history:
                event_history.append(event_address)
            if len(history) > MAX_RUN_HISTORY_ENTRIES:
                raise StoreError(f"dossier_history exceeds {MAX_RUN_HISTORY_ENTRIES} entries")
            if len(event_history) > MAX_RUN_HISTORY_ENTRIES:
                raise StoreError(f"event_history exceeds {MAX_RUN_HISTORY_ENTRIES} entries")
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
        try:
            value = json.loads(self._read_run_bytes(run_id).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StoreError(f"invalid run record: {path.name}") from exc
        if not isinstance(value, dict):
            raise StoreError(f"run record must be an object: {path.name}")
        return value

    def list_runs(self) -> tuple[dict[str, Any], ...]:
        """Return every persisted run record in deterministic run-id order."""

        records: list[dict[str, Any]] = []
        for path in sorted(self.runs.glob("run-*.json"), key=lambda item: item.name):
            try:
                value = json.loads(self._read_run_bytes(path.stem).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise StoreError(f"invalid run record: {path.name}") from exc
            if not isinstance(value, dict):
                raise StoreError(f"run record must be an object: {path.name}")
            records.append(value)
        return tuple(records)
