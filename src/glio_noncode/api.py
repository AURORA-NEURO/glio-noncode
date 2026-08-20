"""Dependency-free JSON HTTP API for local deployments."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlsplit

from .errors import GlioError
from .models import CaseManifest
from .runtime import CaseRuntime
from .schema import schema_document


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


class ApiHandler(BaseHTTPRequestHandler):
    """Small API handler with explicit endpoints and bounded error bodies."""

    server_version = "glio-noncode/0.1"
    runtime_factory: Callable[[], CaseRuntime] | None = None

    def _runtime(self) -> CaseRuntime:
        factory = self.runtime_factory or (lambda: CaseRuntime())
        runtime = getattr(self.server, "glio_runtime", None)
        if runtime is None:
            runtime = factory()
            setattr(self.server, "glio_runtime", runtime)
        return runtime

    def _write(self, status: int, payload: Any) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if length < 1 or length > 5_000_000:
            raise ValueError("request body must be between 1 byte and 5 MB")
        body = self.rfile.read(length)
        value = json.loads(body.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object")
        return value

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path == "/healthz":
            self._write(HTTPStatus.OK, {"status": "ok", "service": "glio-noncode", "version": "0.1.0"})
            return
        if path == "/v1/schema":
            self._write(HTTPStatus.OK, schema_document())
            return
        self._write(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path != "/v1/evaluate":
            self._write(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})
            return
        try:
            manifest = CaseManifest.from_dict(self._read_json())
            dossier = self._runtime().evaluate(manifest)
            self._write(HTTPStatus.OK, dossier.to_dict())
        except GlioError as exc:
            self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
        except (ValueError, json.JSONDecodeError) as exc:
            self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_json", "message": str(exc)})
        except Exception as exc:  # pragma: no cover - last-resort process boundary
            self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})

    def log_message(self, format: str, *args: object) -> None:
        return


def create_server(host: str = "127.0.0.1", port: int = 8765, data_root: str = ".glio") -> ThreadingHTTPServer:
    """Create a local threaded HTTP server with an isolated runtime."""

    server = ThreadingHTTPServer((host, port), ApiHandler)
    setattr(server, "glio_runtime", CaseRuntime(data_root))
    return server
