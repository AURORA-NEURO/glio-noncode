"""Local content-addressed storage for replayable case artifacts."""

from __future__ import annotations

import os
import re
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from errno import EACCES, EAGAIN
from pathlib import Path
from threading import Lock, RLock
from typing import Any, cast

from .errors import StoreError
from .serialization import _strict_json_loads, canonical_json, content_hash

_RUN_ID_RE = re.compile(r"run-[A-Za-z0-9][A-Za-z0-9._-]{0,123}\Z")
_RUN_LOCKS: dict[str, RLock] = {}
_RUN_LOCKS_GUARD = Lock()
_FILESYSTEM_LOCK_TIMEOUT_SECONDS = 30.0
_FILESYSTEM_LOCK_POLL_SECONDS = 0.01
MAX_RUN_HISTORY_ENTRIES = 1_000
_MAX_RUN_INDEX_BYTES = 1 << 20
_MAX_VERIFIED_OBJECT_BYTES = 128 * 1024 * 1024
_RUN_RECORD_FIELDS = frozenset(
    {
        "run_id",
        "input_address",
        "event_address",
        "event_history",
        "dossier_address",
        "dossier_history",
    }
)
_LEGACY_RUN_RECORD_FIELDS = frozenset(
    {"run_id", "input_address", "event_address", "dossier_address"}
)
_LEGACY_DOSSIER_HISTORY_FIELDS = _LEGACY_RUN_RECORD_FIELDS | {"dossier_history"}


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

            fcntl.flock(  # type: ignore[attr-defined]
                handle.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,  # type: ignore[attr-defined]
            )
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

            fcntl.flock(  # type: ignore[attr-defined]
                handle.fileno(),
                fcntl.LOCK_UN,  # type: ignore[attr-defined]
            )
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
    if type(address) is not str:
        raise StoreError(f"{label} must be a string")
    if not address.startswith("sha256:"):
        raise StoreError(f"unsupported {label}: {address}")
    digest = address.split(":", 1)[1]
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise StoreError(f"invalid {label}: {address}")
    return digest


def _history_values(value: object, label: str) -> tuple[str, ...]:
    if type(value) is list:
        items = tuple(cast(list[object], value))
    elif type(value) is tuple:
        items = cast(tuple[object, ...], value)
    else:
        raise StoreError(f"{label} must be an array")
    if len(items) > MAX_RUN_HISTORY_ENTRIES:
        raise StoreError(f"{label} exceeds {MAX_RUN_HISTORY_ENTRIES} entries")
    for item in items:
        _address_digest(item, label=f"{label} address")
    if len(items) != len(set(items)):
        raise StoreError(f"{label} must contain unique addresses")
    return cast(tuple[str, ...], items)


def _validated_run_record(
    value: object,
    *,
    expected_run_id: str,
) -> dict[str, Any]:
    """Validate one current or legacy run index without scalar coercion."""

    if type(value) is not dict:
        raise StoreError(f"run record must be an object: {expected_run_id}.json")
    if any(type(field) is not str for field in value):
        raise StoreError("run record field names must be strings")
    fields = frozenset(value)
    if fields not in {
        _RUN_RECORD_FIELDS,
        _LEGACY_RUN_RECORD_FIELDS,
        _LEGACY_DOSSIER_HISTORY_FIELDS,
    }:
        missing = sorted(_LEGACY_RUN_RECORD_FIELDS - fields)
        unexpected = sorted(str(field) for field in fields - _RUN_RECORD_FIELDS)
        raise StoreError(
            "run record fields are invalid "
            f"(missing: {missing or ['none']}; unexpected: {unexpected or ['none']})"
        )
    run_id = value.get("run_id")
    if type(run_id) is not str or run_id != expected_run_id:
        raise StoreError("stored run_id does not match its index filename")
    input_address = value.get("input_address")
    event_address = value.get("event_address")
    dossier_address = value.get("dossier_address")
    _address_digest(input_address, label="stored input address")
    _address_digest(event_address, label="stored event address")
    _address_digest(dossier_address, label="stored dossier address")
    input_address = cast(str, input_address)
    event_address = cast(str, event_address)
    dossier_address = cast(str, dossier_address)
    if "event_history" in fields:
        event_history = _history_values(value.get("event_history"), "stored event_history")
        if event_address not in event_history:
            raise StoreError("stored event_address is absent from event_history")
    else:
        event_history = (event_address,)
    if "dossier_history" in fields:
        dossier_history = _history_values(
            value.get("dossier_history"),
            "stored dossier_history",
        )
        if dossier_address not in dossier_history:
            raise StoreError("stored dossier_address is absent from dossier_history")
    else:
        dossier_history = (dossier_address,)
    return {
        "run_id": run_id,
        "input_address": input_address,
        "event_address": event_address,
        "event_history": list(event_history),
        "dossier_address": dossier_address,
        "dossier_history": list(dossier_history),
    }


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object field: {key}")
        value[key] = item
    return value


def _invalid_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def _decode_run_record(
    payload: bytes,
    *,
    path: Path,
    expected_run_id: str,
) -> dict[str, Any]:
    """Decode one exact JSON snapshot before applying the typed record contract."""

    try:
        value = _strict_json_loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_invalid_json_constant,
        )
    except (UnicodeDecodeError, RecursionError, ValueError) as exc:
        raise StoreError(f"invalid run record: {path.name}") from exc
    return _validated_run_record(value, expected_run_id=expected_run_id)


def _decode_stored_object(payload: bytes, *, address: str) -> Any:
    """Decode stored object bytes without accepting ambiguous JSON spellings."""

    try:
        return _strict_json_loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_invalid_json_constant,
        )
    except (UnicodeDecodeError, RecursionError, ValueError) as exc:
        raise StoreError(f"invalid stored object: {address}") from exc


def _read_run_index_bytes(path: Path) -> bytes:
    """Read at most one complete bounded run-index payload."""

    try:
        if path.is_symlink():
            raise StoreError(f"run record path is unsafe: {path.name}")
        with path.open("rb") as handle:
            payload = handle.read(_MAX_RUN_INDEX_BYTES + 1)
    except StoreError:
        raise
    except OSError as exc:
        raise StoreError(f"run record could not be read: {path.name}") from exc
    if len(payload) > _MAX_RUN_INDEX_BYTES:
        raise StoreError(f"run record exceeds {_MAX_RUN_INDEX_BYTES} bytes: {path.name}")
    return payload


class ObjectStore:
    """Store immutable JSON objects under a hash-derived path."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.objects = self.root / "objects"
        try:
            if self.root.is_symlink():
                raise StoreError("object store root must contain regular directories")
            self.root.mkdir(parents=True, exist_ok=True)
            if not self.root.is_dir():
                raise StoreError("object store root must contain regular directories")
            if self.objects.is_symlink():
                raise StoreError("object store root must contain regular directories")
            self.objects.mkdir(parents=True, exist_ok=True)
            if not self.objects.is_dir():
                raise StoreError("object store root must contain regular directories")
        except StoreError:
            raise
        except OSError as exc:
            raise StoreError("object store root could not be inspected") from exc
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
        with _run_lock(path), _filesystem_lock(self._locks / f"{digest}.lock"):
            try:
                existing = path.is_symlink()
                present = path.exists()
            except OSError as exc:
                raise StoreError(f"stored object path could not be inspected: {address}") from exc
            if existing:
                raise StoreError(f"stored object path is unsafe: {address}")
            if present:
                try:
                    payload = path.read_bytes()
                except OSError as exc:
                    raise StoreError(f"stored object could not be read: {address}") from exc
                existing = _decode_stored_object(payload, address=address)
                if canonical_json(existing) != serialized:
                    raise StoreError(f"stored object differs at immutable address: {address}")
            else:
                _atomic_write_text(path, serialized)
        return address

    def get(self, address: str) -> Any:
        digest = _address_digest(address)
        path = self.objects / f"{digest}.json"
        try:
            unsafe = path.is_symlink()
            present = path.exists()
        except OSError as exc:
            raise StoreError(f"stored object path could not be inspected: {address}") from exc
        if unsafe:
            raise StoreError(f"stored object path is unsafe: {address}")
        if not present:
            raise StoreError(f"object not found: {address}")
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise StoreError(f"stored object could not be read: {address}") from exc
        return _decode_stored_object(payload, address=address)

    def _read_bounded_payload(self, address: str, *, max_bytes: int) -> bytes:
        """Read one object payload without allocating beyond a declared ceiling."""

        digest = _address_digest(address)
        if type(max_bytes) is not int or max_bytes <= 0:
            raise StoreError("verified object max_bytes must be a positive integer")
        if max_bytes > _MAX_VERIFIED_OBJECT_BYTES:
            raise StoreError(
                "verified object max_bytes exceeds the hard ceiling of "
                f"{_MAX_VERIFIED_OBJECT_BYTES} bytes"
            )
        path = self.objects / f"{digest}.json"
        try:
            unsafe = path.is_symlink()
            present = path.exists()
        except OSError as exc:
            raise StoreError(f"stored object path could not be inspected: {address}") from exc
        if unsafe:
            raise StoreError(f"stored object path is unsafe: {address}")
        if not present:
            raise StoreError(f"object not found: {address}")
        try:
            with path.open("rb") as handle:
                payload = handle.read(max_bytes + 1)
        except OSError as exc:
            raise StoreError(f"stored object could not be read: {address}") from exc
        if len(payload) > max_bytes:
            raise StoreError(f"stored object exceeds {max_bytes} bytes: {address}")
        return payload

    def get_bounded(self, address: str, *, max_bytes: int) -> Any:
        """Decode one bounded object for integrity diagnostics.

        This deliberately does not assert canonical spelling or content-address
        identity.  It exists so diagnostic surfaces can classify corruption
        without an unbounded read; callers must validate the returned value
        before exposing it as trusted content.
        """

        payload = self._read_bounded_payload(address, max_bytes=max_bytes)
        return _decode_stored_object(payload, address=address)

    def get_canonical(self, address: str, *, max_bytes: int) -> Any:
        """Read one canonical JSON object within an explicit byte ceiling."""

        payload = self._read_bounded_payload(address, max_bytes=max_bytes)
        value = _decode_stored_object(payload, address=address)
        try:
            canonical_payload = canonical_json(value).encode("utf-8")
        except (RecursionError, TypeError, ValueError) as exc:
            raise StoreError(f"invalid stored object: {address}") from exc
        if canonical_payload != payload:
            raise StoreError(f"stored object is not canonical JSON: {address}")
        return value

    def get_verified(self, address: str, *, max_bytes: int) -> Any:
        """Read one bounded generic object and verify its full content address."""

        value = self.get_canonical(address, max_bytes=max_bytes)
        if content_hash(value) != address:
            raise StoreError(f"stored object does not match its content address: {address}")
        return value

    def exists(self, address: str) -> bool:
        try:
            digest = _address_digest(address)
        except StoreError:
            return False
        path = self.objects / f"{digest}.json"
        try:
            return not path.is_symlink() and path.exists()
        except OSError:
            return False


class RunStore:
    """Small index over immutable run artifacts."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.store = ObjectStore(self.root)
        self.runs = self.root / "runs"
        try:
            if self.runs.is_symlink():
                raise StoreError("run store root must contain a regular runs directory")
            self.runs.mkdir(parents=True, exist_ok=True)
            if not self.runs.is_dir():
                raise StoreError("run store root must contain a regular runs directory")
        except StoreError:
            raise
        except OSError as exc:
            raise StoreError("run store root could not be inspected") from exc
        self._locks = self.root / ".locks" / "runs"
        self._locks.mkdir(parents=True, exist_ok=True)
        self._lock = _run_lock(self.runs)

    def _run_path(self, run_id: str) -> Path:
        if type(run_id) is not str or not _RUN_ID_RE.fullmatch(run_id) or ".." in run_id:
            raise StoreError("invalid run_id")
        return self.runs / f"{run_id}.json"

    def _load_run_record_locked(
        self,
        path: Path,
        run_id: str,
        *,
        required: bool,
    ) -> dict[str, Any] | None:
        """Load a record while the caller holds this run's two locks."""

        try:
            unsafe = path.is_symlink()
            present = path.exists()
        except OSError as exc:
            raise StoreError(f"run record path could not be inspected: {run_id}") from exc
        if unsafe:
            raise StoreError(f"run record path is unsafe: {run_id}")
        if not present:
            if required:
                raise StoreError(f"run not found: {run_id}")
            return None
        payload = _read_run_index_bytes(path)
        return _decode_run_record(
            payload,
            path=path,
            expected_run_id=run_id,
        )

    @staticmethod
    def _next_run_record(
        run_id: str,
        *,
        input_address: str,
        event_address: str,
        dossier_address: str,
        previous: dict[str, Any] | None,
        declared_dossier_history: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        """Build one bounded successor from an already locked, validated record."""

        _address_digest(input_address, label="input address")
        _address_digest(event_address, label="event address")
        _address_digest(dossier_address, label="dossier address")
        declared_history = _history_values(
            declared_dossier_history,
            "dossier_history",
        )
        current = {} if previous is None else previous
        if current and current.get("input_address") != input_address:
            raise StoreError("run input_address is immutable")

        previous_history = _history_values(
            current.get("dossier_history", ()),
            "stored dossier_history",
        )
        previous_event_history = _history_values(
            current.get("event_history", ()),
            "stored event_history",
        )
        history = list(dict.fromkeys((*previous_history, *declared_history)))
        previous_address = current.get("dossier_address")
        if previous_address is not None:
            _address_digest(previous_address, label="stored dossier address")
            if previous_address not in history:
                history.append(previous_address)
        if dossier_address not in history:
            history.append(dossier_address)

        event_history = list(previous_event_history)
        previous_event_address = current.get("event_address")
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
        return {
            "run_id": run_id,
            "input_address": input_address,
            "event_address": event_address,
            "event_history": event_history,
            "dossier_address": dossier_address,
            "dossier_history": history,
        }

    def _read_run_bytes(self, run_id: str) -> bytes:
        """Return one stable run-index snapshot under its writer lock."""

        path = self._run_path(run_id)
        with _run_lock(path), _filesystem_lock(self._locks / f"{run_id}.lock"):
            try:
                unsafe = path.is_symlink()
                present = path.exists()
            except OSError as exc:
                raise StoreError(f"run record path could not be inspected: {run_id}") from exc
            if unsafe:
                raise StoreError(f"run record path is unsafe: {run_id}")
            if not present:
                raise StoreError(f"run not found: {run_id}")
            return _read_run_index_bytes(path)

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

        Older run records may omit one or both history arrays. They are upgraded
        deterministically on the next write by retaining their current pointers
        before appending the new snapshot addresses.
        """

        path = self._run_path(run_id)
        _address_digest(input_address, label="input address")
        _address_digest(event_address, label="event address")
        _address_digest(dossier_address, label="dossier address")
        declared_history = (
            () if dossier_history is None else _history_values(dossier_history, "dossier_history")
        )
        with _run_lock(path), _filesystem_lock(self._locks / f"{run_id}.lock"):
            previous = self._load_run_record_locked(
                path,
                run_id,
                required=False,
            )
            record = self._next_run_record(
                run_id,
                input_address=input_address,
                event_address=event_address,
                dossier_address=dossier_address,
                previous=previous,
                declared_dossier_history=declared_history,
            )
            _atomic_write_text(path, canonical_json(record))
        return path

    def create_run(
        self,
        run_id: str,
        *,
        input_address: str,
        event_address: str,
        dossier_address: str,
        dossier_history: tuple[str, ...] | None = None,
    ) -> Path:
        """Atomically create a run index without replacing an existing run."""

        path = self._run_path(run_id)
        _address_digest(input_address, label="input address")
        _address_digest(event_address, label="event address")
        _address_digest(dossier_address, label="dossier address")
        if dossier_history is not None and type(dossier_history) is not tuple:
            raise StoreError("dossier_history must be a tuple")
        declared_history = (
            () if dossier_history is None else _history_values(dossier_history, "dossier_history")
        )
        with _run_lock(path), _filesystem_lock(self._locks / f"{run_id}.lock"):
            try:
                unsafe = path.is_symlink()
                present = path.exists()
            except OSError as exc:
                raise StoreError(f"run record path could not be inspected: {run_id}") from exc
            if unsafe:
                raise StoreError(f"run record path is unsafe: {run_id}")
            if present:
                raise StoreError(f"run already exists: {run_id}")
            record = self._next_run_record(
                run_id,
                input_address=input_address,
                event_address=event_address,
                dossier_address=dossier_address,
                previous=None,
                declared_dossier_history=declared_history,
            )
            _atomic_write_text(path, canonical_json(record))
        return path

    def advance_run(
        self,
        run_id: str,
        *,
        expected_run: dict[str, Any],
        event_address: str,
        dossier_address: str,
        dossier_history: tuple[str, ...] | None = None,
    ) -> Path:
        """Atomically advance an existing run when its complete snapshot matches.

        The normalized expected record is the compare-and-swap token. A missing,
        malformed, rewound, or concurrently advanced record fails without
        rewriting the index. Immutable artifacts written before this call are not
        removed when the comparison fails.
        """

        path = self._run_path(run_id)
        expected = _validated_run_record(expected_run, expected_run_id=run_id)
        _address_digest(event_address, label="event address")
        _address_digest(dossier_address, label="dossier address")
        if dossier_history is not None and type(dossier_history) is not tuple:
            raise StoreError("dossier_history must be a tuple")
        declared_history = (
            () if dossier_history is None else _history_values(dossier_history, "dossier_history")
        )
        with _run_lock(path), _filesystem_lock(self._locks / f"{run_id}.lock"):
            previous = self._load_run_record_locked(
                path,
                run_id,
                required=True,
            )
            if previous is None:  # pragma: no cover - required=True closes this branch
                raise StoreError(f"run not found: {run_id}")
            if canonical_json(previous) != canonical_json(expected):
                raise StoreError("run record does not match the expected current state")
            record = self._next_run_record(
                run_id,
                input_address=previous["input_address"],
                event_address=event_address,
                dossier_address=dossier_address,
                previous=previous,
                declared_dossier_history=declared_history,
            )
            _atomic_write_text(path, canonical_json(record))
        return path

    def get_run(self, run_id: str) -> dict[str, Any]:
        path = self._run_path(run_id)
        return _decode_run_record(
            self._read_run_bytes(run_id),
            path=path,
            expected_run_id=run_id,
        )

    def list_runs(self) -> tuple[dict[str, Any], ...]:
        """Return every persisted run record in deterministic run-id order."""

        records: list[dict[str, Any]] = []
        for path in sorted(self.runs.glob("run-*.json"), key=lambda item: item.name):
            records.append(
                _decode_run_record(
                    self._read_run_bytes(path.stem),
                    path=path,
                    expected_run_id=path.stem,
                )
            )
        return tuple(records)
