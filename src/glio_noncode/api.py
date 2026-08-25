"""Dependency-free JSON HTTP API for local deployments."""

from __future__ import annotations

import json
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from .batch_runtime import BatchRuntime
from .batch_release import build_persisted_batch_release
from .comparison_release import build_persisted_comparison_release
from .dossier_query import (
    DOSSIER_QUERY_DEFAULT_LIMIT,
    build_persisted_dossier_query_closure,
    lineage_persisted_dossier,
    query_persisted_dossier,
    summarize_persisted_dossier,
)
from .dossier_release import build_persisted_dossier_release
from .errors import GlioError, StoreError
from .models import CaseManifest, ReviewDecision
from .program_runtime_diff import PROGRAM_RUNTIME_DIFF_CONTROLS
from .run_comparison import build_run_history, compare_persisted_runs
from .run_catalog import (
    RUN_CATALOG_DEFAULT_LIMIT,
    build_run_catalog_page,
    get_run_dossier,
    get_run_events,
    inspect_run,
)
from .run_search import build_run_search_closure, search_persisted_runs
from .run_workspace import (
    RUN_WORKSPACE_DEFAULT_LIMIT,
    build_persisted_run_workspace,
    build_persisted_run_workspace_closure,
    workspace_query_from_filters,
)
from .workspace_history import (
    WORKSPACE_HISTORY_MAX_CHANGES,
    build_persisted_workspace_history,
    compare_persisted_workspace_snapshots,
)
from .workspace_release import build_persisted_workspace_release
from .review_queue import build_review_queue_closure, build_review_queue_page
from .review_operations import (
    REVIEW_OPERATIONS_DEFAULT_DUE_SOON_HOURS,
    build_review_operations_closure,
    build_review_operations_report,
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

    @staticmethod
    def _query_values(query: dict[str, list[str]], name: str) -> tuple[str, ...]:
        values = query.get(name, [])
        selected: list[str] = []
        for value in values:
            for item in value.split(","):
                normalized = item.strip()
                if normalized and normalized not in selected:
                    selected.append(normalized)
        return tuple(selected)

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

    @classmethod
    def _query_optional_int(cls, query: dict[str, list[str]], name: str) -> int | None:
        value = cls._query_value(query, name)
        if value is None:
            return None
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"query parameter {name} must be an integer") from exc

    @classmethod
    def _query_float(cls, query: dict[str, list[str]], name: str) -> float | None:
        value = cls._query_value(query, name)
        if value is None:
            return None
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"query parameter {name} must be a number") from exc

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
        if path == "/v1/search" or path == "/v1/search/closure":
            try:
                query = parse_qs(parsed.query, keep_blank_values=False)
                search_filters = {
                    "query": self._query_value(query, "q") or self._query_value(query, "text"),
                    "resource": self._query_value(query, "resource") or "all",
                    "case_id": self._query_value(query, "case_id"),
                    "status": self._query_value(query, "status"),
                    "reviewer": self._query_value(query, "reviewer"),
                    "review_state": self._query_value(query, "review_state"),
                    "state": self._query_value(query, "state"),
                    "tier": self._query_value(query, "tier"),
                    "channel": self._query_value(query, "channel"),
                    "min_support": self._query_float(query, "min_support"),
                    "max_uncertainty": self._query_float(query, "max_uncertainty"),
                    "assay": self._query_value(query, "assay"),
                    "accepted_only": self._query_bool(query, "accepted_only"),
                }
                if path.endswith("/closure"):
                    self._write(
                        HTTPStatus.OK,
                        build_run_search_closure(self._runtime(), **search_filters),
                    )
                    return
                page = search_persisted_runs(
                    self._runtime(),
                    **search_filters,
                    offset=self._query_int(query, "offset", 0),
                    limit=self._query_int(query, "limit", 25),
                )
                self._write(HTTPStatus.OK, page.to_dict())
            except StoreError:
                self._write(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": "run not found"})
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path == "/v1/batches" or path.startswith("/v1/batches/"):
            try:
                batch_runtime = BatchRuntime(runtime=self._runtime())
                if path == "/v1/batches":
                    query = parse_qs(parsed.query, keep_blank_values=False)
                    page = batch_runtime.catalog(
                        offset=self._query_int(query, "offset", 0),
                        limit=self._query_int(query, "limit", 25),
                        text=self._query_value(query, "text"),
                    )
                    self._write(HTTPStatus.OK, page.to_dict())
                    return
                segments = [unquote(item) for item in path.split("/") if item]
                if len(segments) == 4 and segments[0:2] == ["v1", "batches"] and segments[3] == "release":
                    self._write(
                        HTTPStatus.OK,
                        build_persisted_batch_release(batch_runtime.runtime, segments[2]).to_dict(),
                    )
                    return
                if len(segments) != 3 or segments[0:2] != ["v1", "batches"]:
                    self._write(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})
                    return
                self._write(HTTPStatus.OK, batch_runtime.get(segments[2]).to_dict())
            except StoreError:
                self._write(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": "batch not found"})
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path == "/v1/review-queue" or path == "/v1/review-queue/closure":
            try:
                query = parse_qs(parsed.query, keep_blank_values=False)
                if path.endswith("/closure"):
                    self._write(HTTPStatus.OK, build_review_queue_closure(self._runtime()))
                    return
                page = build_review_queue_page(
                    self._runtime(),
                    scope=self._query_value(query, "scope") or "open",
                    case_id=self._query_value(query, "case_id"),
                    status=self._query_value(query, "status"),
                    reviewer=self._query_value(query, "reviewer"),
                    queue_id=self._query_value(query, "queue_id"),
                    priority_band=self._query_value(query, "priority_band"),
                    text=self._query_value(query, "text"),
                    offset=self._query_int(query, "offset", 0),
                    limit=self._query_int(query, "limit", 25),
                )
                self._write(HTTPStatus.OK, page.to_dict())
            except StoreError:
                self._write(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": "run not found"})
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path == "/v1/review-operations" or path == "/v1/review-operations/closure":
            try:
                query = parse_qs(parsed.query, keep_blank_values=False)
                as_of = self._query_value(query, "as_of")
                due_soon_hours = self._query_int(
                    query,
                    "due_soon_hours",
                    REVIEW_OPERATIONS_DEFAULT_DUE_SOON_HOURS,
                )
                if path.endswith("/closure"):
                    self._write(
                        HTTPStatus.OK,
                        build_review_operations_closure(
                            self._runtime(),
                            as_of=as_of,
                            due_soon_hours=due_soon_hours,
                        ),
                    )
                    return
                report = build_review_operations_report(
                    self._runtime(),
                    scope=self._query_value(query, "scope") or "open",
                    reviewer=self._query_value(query, "reviewer"),
                    queue_id=self._query_value(query, "queue_id"),
                    due_state=self._query_value(query, "due_state"),
                    priority_band=self._query_value(query, "priority_band"),
                    text=self._query_value(query, "text"),
                    as_of=as_of,
                    due_soon_hours=due_soon_hours,
                    offset=self._query_int(query, "offset", 0),
                    limit=self._query_int(query, "limit", 50),
                )
                self._write(HTTPStatus.OK, report.to_dict())
            except StoreError:
                self._write(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": "run not found"})
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
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
                if len(segments) == 4 and segments[3] == "summary":
                    self._write(HTTPStatus.OK, summarize_persisted_dossier(runtime, run_id).to_dict())
                    return
                if len(segments) == 4 and segments[3] == "history":
                    self._write(HTTPStatus.OK, build_run_history(runtime, run_id).to_dict())
                    return
                is_workspace = len(segments) == 4 and segments[3] == "workspace"
                is_workspace_closure = (
                    len(segments) == 5
                    and segments[3] == "workspace"
                    and segments[4] == "closure"
                )
                is_workspace_history = (
                    len(segments) == 5
                    and segments[3] == "workspace"
                    and segments[4] == "history"
                )
                is_workspace_compare = (
                    len(segments) == 5
                    and segments[3] == "workspace"
                    and segments[4] == "compare"
                )
                is_workspace_release = (
                    len(segments) == 5
                    and segments[3] == "workspace"
                    and segments[4] == "release"
                )
                if is_workspace_release:
                    self._write(
                        HTTPStatus.OK,
                        build_persisted_workspace_release(runtime, run_id).to_dict(),
                    )
                    return
                if is_workspace_history:
                    query = parse_qs(parsed.query, keep_blank_values=False)
                    history = build_persisted_workspace_history(
                        runtime,
                        run_id,
                        change_limit=self._query_int(
                            query,
                            "change_limit",
                            WORKSPACE_HISTORY_MAX_CHANGES,
                        ),
                    )
                    self._write(HTTPStatus.OK, history.to_dict())
                    return
                if is_workspace_compare:
                    query = parse_qs(parsed.query, keep_blank_values=False)
                    source_snapshot = self._query_optional_int(query, "source_snapshot")
                    target_snapshot = self._query_optional_int(query, "target_snapshot")
                    if source_snapshot is None or target_snapshot is None:
                        raise ValueError(
                            "workspace compare requires source_snapshot and target_snapshot"
                        )
                    transition = compare_persisted_workspace_snapshots(
                        runtime,
                        run_id,
                        source_snapshot,
                        target_snapshot,
                        change_limit=self._query_int(
                            query,
                            "change_limit",
                            WORKSPACE_HISTORY_MAX_CHANGES,
                        ),
                    )
                    self._write(HTTPStatus.OK, transition.to_dict())
                    return
                if is_workspace or is_workspace_closure:
                    query = parse_qs(parsed.query, keep_blank_values=False)
                    workspace_query = workspace_query_from_filters(
                        text=self._query_value(query, "q") or self._query_value(query, "text"),
                        context_key=self._query_value(query, "context_key"),
                        record_types=self._query_values(query, "record_type"),
                        states=self._query_values(query, "state"),
                        chromosome=self._query_value(query, "chromosome"),
                        start=self._query_optional_int(query, "start"),
                        end=self._query_optional_int(query, "end"),
                        source_ids=self._query_values(query, "source_id"),
                        tags_all=self._query_values(query, "tag"),
                        offset=self._query_int(query, "offset", 0),
                        limit=self._query_int(query, "limit", RUN_WORKSPACE_DEFAULT_LIMIT),
                    )
                    variant_id = self._query_value(query, "variant_id")
                    if is_workspace_closure:
                        self._write(
                            HTTPStatus.OK,
                            build_persisted_run_workspace_closure(
                                runtime,
                                run_id,
                                query=workspace_query,
                                variant_id=variant_id,
                            ),
                        )
                    else:
                        self._write(
                            HTTPStatus.OK,
                            build_persisted_run_workspace(
                                runtime,
                                run_id,
                                query=workspace_query,
                                variant_id=variant_id,
                            ).to_dict(),
                        )
                    return
                if len(segments) == 5 and segments[3] == "compare":
                    query = parse_qs(parsed.query, keep_blank_values=False)
                    comparison = compare_persisted_runs(
                        runtime,
                        run_id,
                        segments[4],
                        source_snapshot=self._query_optional_int(query, "source_snapshot"),
                        target_snapshot=self._query_optional_int(query, "target_snapshot"),
                    )
                    self._write(HTTPStatus.OK, comparison.to_dict())
                    return
                if len(segments) == 6 and segments[3] == "compare" and segments[5] == "release":
                    query = parse_qs(parsed.query, keep_blank_values=False)
                    bundle = build_persisted_comparison_release(
                        runtime,
                        run_id,
                        segments[4],
                        source_snapshot=self._query_optional_int(query, "source_snapshot"),
                        target_snapshot=self._query_optional_int(query, "target_snapshot"),
                    )
                    self._write(HTTPStatus.OK, bundle.to_dict())
                    return
                if len(segments) == 4 and segments[3] == "query-closure":
                    self._write(HTTPStatus.OK, build_persisted_dossier_query_closure(runtime, run_id))
                    return
                if len(segments) == 4 and segments[3] == "release":
                    self._write(HTTPStatus.OK, build_persisted_dossier_release(runtime, run_id).to_dict())
                    return
                if len(segments) == 4 and segments[3] in {"hypotheses", "evidence", "experiments"}:
                    query = parse_qs(parsed.query, keep_blank_values=False)
                    resource = segments[3]
                    page = query_persisted_dossier(
                        runtime,
                        run_id,
                        resource,
                        offset=self._query_int(query, "offset", 0),
                        limit=self._query_int(query, "limit", DOSSIER_QUERY_DEFAULT_LIMIT),
                        text=self._query_value(query, "text"),
                        hypothesis_id=self._query_value(query, "hypothesis_id"),
                        status=self._query_value(query, "status"),
                        min_support=self._query_float(query, "min_support"),
                        max_uncertainty=self._query_float(query, "max_uncertainty"),
                        evidence_id=self._query_value(query, "evidence_id"),
                        edge_id=self._query_value(query, "edge_id"),
                        state=self._query_value(query, "state"),
                        tier=self._query_value(query, "tier"),
                        channel=self._query_value(query, "channel"),
                        source_id=self._query_value(query, "source_id"),
                        option_id=self._query_value(query, "option_id"),
                        assay=self._query_value(query, "assay"),
                    )
                    self._write(HTTPStatus.OK, page.to_dict())
                    return
                if len(segments) == 4 and segments[3] == "lineage":
                    query = parse_qs(parsed.query, keep_blank_values=False)
                    lineage = lineage_persisted_dossier(
                        runtime,
                        run_id,
                        hypothesis_id=self._query_value(query, "hypothesis_id"),
                    )
                    self._write(HTTPStatus.OK, lineage.to_dict())
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
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
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
        if path == "/v1/evaluate-batch":
            try:
                result = BatchRuntime(runtime=self._runtime()).evaluate(self._read_json())
                self._write(HTTPStatus.OK, result.to_dict())
            except StoreError:
                self._write(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": "batch object not found"})
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except (ValueError, json.JSONDecodeError) as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_json", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path.startswith("/v1/runs/"):
            segments = [unquote(item) for item in path.split("/") if item]
            if len(segments) != 4 or segments[0:2] != ["v1", "runs"] or segments[3] not in {"review", "assignment"}:
                self._write(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})
                return
            try:
                payload = self._read_json()
                if segments[3] == "assignment":
                    result = self._runtime().assign_review(
                        segments[2],
                        assignment_id=str(payload.get("assignment_id", "")),
                        reviewer=str(payload.get("reviewer", "")),
                        queue_id=str(payload.get("queue_id", "default-review")),
                        due_at=None if payload.get("due_at") is None else str(payload.get("due_at")),
                        note=str(payload.get("note", "")),
                    )
                    self._write(HTTPStatus.OK, result)
                    return
                review = ReviewDecision.from_dict(payload)
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
