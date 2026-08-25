"""Dependency-free JSON HTTP API for local deployments."""

from __future__ import annotations

import json
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from .errors import GlioError, StoreError
from .models import CaseManifest, ReviewDecision
from .program_runtime_diff import PROGRAM_RUNTIME_DIFF_CONTROLS
from .run_catalog import (
    RUN_CATALOG_DEFAULT_LIMIT,
    build_run_catalog_page,
    get_run_dossier,
    get_run_events,
    inspect_run,
)
from .runtime import CaseRuntime
from .schema import schema_document
from .service_surface import (
    SERVICE_API_VERSION,
    SERVICE_NAME,
    build_service_surface_snapshot,
    service_capability_projection,
    service_diff_projection,
    service_operational_projection,
    service_program_projection,
    service_surface_status,
)


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
            setattr(self.server, "glio_runtime", runtime)  # noqa: B010 - the HTTP server is intentionally extended
        return runtime

    def _service_surface(self):
        snapshot = getattr(self.server, "glio_service_surface", None)
        if snapshot is None:
            snapshot = build_service_surface_snapshot()
            setattr(self.server, "glio_service_surface", snapshot)  # noqa: B010 - lazy server-local cache
        return snapshot

    @staticmethod
    def _query_value(query: dict[str, list[str]], name: str) -> str | None:
        values = query.get(name, [])
        if len(values) > 1:
            raise ValueError(f"query parameter {name} may only be supplied once")
        return values[0] if values else None

    @classmethod
    def _query_bool(cls, query: dict[str, list[str]], name: str) -> bool:
        value = cls._query_value(query, name)
        if value is None:
            return False
        normalized = value.lower()
        if normalized in {"1", "true", "yes"}:
            return True
        if normalized in {"0", "false", "no"}:
            return False
        raise ValueError(f"query parameter {name} must be true or false")

    @classmethod
    def _query_int(cls, query: dict[str, list[str]], name: str, default: int) -> int:
        value = cls._query_value(query, name)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"query parameter {name} must be an integer") from exc

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
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/healthz":
            self._write(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "service": SERVICE_NAME,
                    "version": "0.1.0",
                    "api_version": SERVICE_API_VERSION,
                },
            )
            return
        if path == "/v1/schema":
            self._write(HTTPStatus.OK, schema_document())
            return
        if path == "/v1/runs" or path.startswith("/v1/runs/"):
            try:
                runtime = self._runtime()
                if path == "/v1/runs":
                    query = parse_qs(parsed.query, keep_blank_values=False)
                    page = build_run_catalog_page(
                        runtime,
                        case_id=self._query_value(query, "case_id"),
                        status=self._query_value(query, "status"),
                        text=self._query_value(query, "text"),
                        offset=self._query_int(query, "offset", 0),
                        limit=self._query_int(query, "limit", RUN_CATALOG_DEFAULT_LIMIT),
                    )
                    self._write(HTTPStatus.OK, page.to_dict())
                    return
                segments = [unquote(item) for item in path.split("/") if item]
                if len(segments) < 3 or segments[0:2] != ["v1", "runs"]:
                    self._write(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})
                    return
                run_id = segments[2]
                if len(segments) == 3:
                    self._write(HTTPStatus.OK, inspect_run(runtime, run_id).summary.to_dict())
                    return
                if len(segments) == 4 and segments[3] == "dossier":
                    self._write(HTTPStatus.OK, get_run_dossier(runtime, run_id))
                    return
                if len(segments) == 4 and segments[3] == "events":
                    self._write(HTTPStatus.OK, get_run_events(runtime, run_id))
                    return
                if len(segments) == 4 and segments[3] == "replay":
                    inspection = inspect_run(runtime, run_id)
                    self._write(
                        HTTPStatus.OK,
                        {
                            "run_id": inspection.summary.run_id,
                            "replay": inspection.replay.to_dict(),
                            "accepted": inspection.accepted,
                            "content_address": inspection.content_address,
                        },
                    )
                    return
                if len(segments) == 4 and segments[3] == "inspection":
                    self._write(HTTPStatus.OK, inspect_run(runtime, run_id).to_dict())
                    return
                self._write(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})
            except StoreError:
                self._write(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": "run not found"})
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path in {
            "/v1/status",
            "/v1/capabilities",
            "/v1/architecture/program",
            "/v1/architecture/operational",
            "/v1/architecture/diff",
        }:
            try:
                query = parse_qs(parsed.query, keep_blank_values=False)
                snapshot = self._service_surface()
                if path == "/v1/status":
                    payload = service_surface_status(snapshot)
                elif path == "/v1/capabilities":
                    payload = service_capability_projection(
                        snapshot,
                        capability_id=self._query_value(query, "capability_id"),
                        domain_id=self._query_value(query, "domain_id"),
                        mvp_only=self._query_bool(query, "mvp_only"),
                        state=self._query_value(query, "state"),
                        text=self._query_value(query, "text"),
                    )
                elif path == "/v1/architecture/program":
                    payload = service_program_projection(
                        snapshot,
                        domain_id=self._query_value(query, "domain_id"),
                        accepted_only=self._query_bool(query, "accepted_only"),
                        text=self._query_value(query, "text"),
                    )
                elif path == "/v1/architecture/operational":
                    payload = service_operational_projection(snapshot)
                else:
                    control = self._query_value(query, "control") or "none"
                    if control not in PROGRAM_RUNTIME_DIFF_CONTROLS:
                        allowed = ", ".join(PROGRAM_RUNTIME_DIFF_CONTROLS)
                        raise ValueError(f"query parameter control must be one of: {allowed}")
                    payload = service_diff_projection(snapshot, control)
                self._write(HTTPStatus.OK, payload)
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        self._write(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        path = parsed.path
        if path.startswith("/v1/runs/"):
            segments = [unquote(item) for item in path.split("/") if item]
            if len(segments) != 4 or segments[0:2] != ["v1", "runs"] or segments[3] != "review":
                self._write(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})
                return
            try:
                review = ReviewDecision.from_dict(self._read_json())
                dossier = self._runtime().review_run(segments[2], review)
                self._write(HTTPStatus.OK, dossier.to_dict())
            except StoreError:
                self._write(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": "run not found"})
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except (ValueError, json.JSONDecodeError) as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_json", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path != "/v1/evaluate":
            self._write(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})
            return
        try:
            manifest = CaseManifest.from_dict(self._read_json())
            live_reference = parsed.query.lower() in {"live_reference=1", "live_reference=true", "live_reference=yes"}
            dossier = self._runtime().evaluate(manifest, live_reference=live_reference)
            self._write(HTTPStatus.OK, dossier.to_dict())
        except StoreError:
            self._write(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": "stored object not found"})
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
    setattr(server, "glio_runtime", CaseRuntime(data_root))  # noqa: B010 - server-local runtime attachment
    return server
