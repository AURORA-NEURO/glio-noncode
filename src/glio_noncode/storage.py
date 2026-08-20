"""Local content-addressed storage for replayable case artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import StoreError
from .serialization import canonical_json, content_hash


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
        if not path.exists():
            temporary = path.with_suffix(".tmp")
            temporary.write_text(canonical_json(value), encoding="utf-8")
            temporary.replace(path)
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
        return (self.objects / f"{digest}.json").exists()


class RunStore:
    """Small index over immutable run artifacts."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.store = ObjectStore(self.root)
        self.runs = self.root / "runs"
        self.runs.mkdir(parents=True, exist_ok=True)

    def save_run(self, run_id: str, *, input_address: str, event_address: str, dossier_address: str) -> Path:
        record = {
            "run_id": run_id,
            "input_address": input_address,
            "event_address": event_address,
            "dossier_address": dossier_address,
        }
        path = self.runs / f"{run_id}.json"
        path.write_text(canonical_json(record), encoding="utf-8")
        return path

    def get_run(self, run_id: str) -> dict[str, Any]:
        path = self.runs / f"{run_id}.json"
        if not path.exists():
            raise StoreError(f"run not found: {run_id}")
        return json.loads(path.read_text(encoding="utf-8"))
