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
from .run_portfolio import (
    RUN_PORTFOLIO_DEFAULT_LIMIT,
    build_run_portfolio,
    build_run_portfolio_closure,
)
from .portfolio_release import build_portfolio_release
from .portfolio_release_lineage import build_portfolio_release_lineage, lineage_for_run
from .portfolio_release_observability import build_portfolio_release_observability
from .portfolio_release_schema import portfolio_release_schema
from .module_fabric_bundle import build_module_fabric_bundle
from .module_fabric_bundle_audit import audit_module_fabric_bundle
from .module_fabric_bundle_observability import build_module_fabric_bundle_observability
from .module_fabric_bundle_query import query_module_fabric_bundle
from .module_fabric_bundle_runtime import run_module_fabric_bundle_runtime
from .module_fabric_bundle_schema import module_fabric_bundle_schema
from .capability_certification_bundle import build_capability_certification_bundle
from .capability_certification_bundle_audit import audit_capability_certification_bundle
from .capability_certification_bundle_observability import certification_bundle_observability_from_dict
from .capability_certification_bundle_query import query_capability_certification_bundle
from .capability_certification_bundle_runtime import run_capability_certification_bundle_runtime
from .capability_certification_bundle_schema import capability_certification_bundle_schema
from .public_surface_audit import build_default_public_surface_audit
from .validation_design_frontier_bundle_audit import audit_validation_design_offline_bundle
from .validation_design_frontier_bundle_query import query_validation_design_offline_bundle
from .validation_design_frontier_bundle_schema import validation_design_bundle_schema
from .validation_design_frontier_offline_bundle import build_validation_design_offline_bundle
from .validation_design_frontier_bundle_runtime import build_validation_design_bundle_observability, run_validation_design_bundle_runtime
from .validation_design_frontier_bundle_closure_boundary import validate_validation_design_closure_boundary
from .validation_design_frontier_bundle_closure_certification import certify_validation_design_closure
from .validation_design_frontier_bundle_closure_indexes import audit_validation_design_closure_indexes, build_validation_design_closure_indexes
from .validation_design_frontier_bundle_closure_observability import build_validation_design_closure_observability
from .validation_design_frontier_bundle_closure_query import query_validation_design_closure
from .validation_design_frontier_bundle_closure_reconciliation import reconcile_validation_design_closure
from .validation_design_frontier_bundle_closure_runtime import run_validation_design_closure_runtime
from .validation_design_frontier_bundle_closure_schema import validation_design_closure_schema
from .validation_design_frontier_bundle_closure_summary import audit_validation_design_closure_summary, build_validation_design_closure_summary
from .validation_design_frontier_bundle_closure_failure_injection import rehearse_validation_design_closure_failures
from .evidence_lifecycle_frontier_offline_audit import audit_evidence_lifecycle_offline_bundle
from .evidence_lifecycle_frontier_offline_bundle import build_evidence_lifecycle_offline_bundle
from .evidence_lifecycle_frontier_offline_query import query_evidence_lifecycle_offline_bundle
from .evidence_lifecycle_frontier_offline_runtime import build_evidence_lifecycle_offline_observability, run_evidence_lifecycle_offline_bundle_runtime
from .evidence_lifecycle_frontier_offline_schema import evidence_lifecycle_offline_bundle_schema
from .evidence_lifecycle_frontier_offline_boundary import audit_evidence_lifecycle_offline_boundary
from .evidence_lifecycle_frontier_offline_indexes import audit_evidence_lifecycle_offline_indexes, build_evidence_lifecycle_offline_indexes
from .evidence_lifecycle_frontier_offline_reconciliation import reconcile_evidence_lifecycle_offline_bundle
from .evidence_lifecycle_frontier_offline_summary import audit_evidence_lifecycle_offline_summary, build_evidence_lifecycle_offline_summary
from .evidence_lifecycle_frontier_offline_closure_boundary import audit_evidence_lifecycle_closure_boundary
from .evidence_lifecycle_frontier_offline_closure_certification import certify_evidence_lifecycle_closure
from .evidence_lifecycle_frontier_offline_closure_failure_injection import run_evidence_lifecycle_closure_failure_injection
from .evidence_lifecycle_frontier_offline_closure_graph import build_evidence_lifecycle_closure_graph
from .evidence_lifecycle_frontier_offline_closure_indexes import audit_evidence_lifecycle_closure_indexes, build_evidence_lifecycle_closure_indexes
from .evidence_lifecycle_frontier_offline_closure_observability import build_evidence_lifecycle_closure_observability
from .evidence_lifecycle_frontier_offline_closure_query import query_evidence_lifecycle_closure
from .evidence_lifecycle_frontier_offline_closure_reconciliation import reconcile_evidence_lifecycle_closure
from .evidence_lifecycle_frontier_offline_closure_runtime import run_evidence_lifecycle_closure_runtime
from .evidence_lifecycle_frontier_offline_closure_schema import evidence_lifecycle_closure_schema
from .evidence_lifecycle_frontier_offline_closure_summary import audit_evidence_lifecycle_closure_summary, build_evidence_lifecycle_closure_summary
from .workbench_release_frontier_offline_audit import audit_workbench_release_offline_bundle
from .workbench_release_frontier_offline_boundary import audit_workbench_release_offline_boundary
from .workbench_release_frontier_offline_bundle import build_workbench_release_offline_bundle
from .workbench_release_frontier_offline_indexes import audit_workbench_release_offline_indexes, build_workbench_release_offline_indexes
from .workbench_release_frontier_offline_query import query_workbench_release_offline_bundle
from .workbench_release_frontier_offline_reconciliation import reconcile_workbench_release_offline_bundle
from .workbench_release_frontier_offline_runtime import build_workbench_release_offline_observability, run_workbench_release_offline_bundle_runtime
from .workbench_release_frontier_offline_schema import workbench_release_offline_bundle_schema
from .workbench_release_frontier_offline_summary import audit_workbench_release_offline_summary, build_workbench_release_offline_summary
from .workbench_release_frontier_offline_certification import audit_workbench_release_offline_certification, certify_workbench_release_offline_bundle
from .workbench_release_frontier_offline_closure_boundary import audit_workbench_release_closure_boundary
from .workbench_release_frontier_offline_closure_certification import certify_workbench_release_closure
from .workbench_release_frontier_offline_closure_export import build_workbench_release_closure_export
from .workbench_release_frontier_offline_closure_failure_injection import build_workbench_release_closure_failure_report
from .workbench_release_frontier_offline_closure_graph import build_workbench_release_closure_graph
from .workbench_release_frontier_offline_closure_indexes import audit_workbench_release_closure_indexes, build_workbench_release_closure_indexes
from .workbench_release_frontier_offline_closure_observability import build_workbench_release_closure_observability
from .workbench_release_frontier_offline_closure_query import query_workbench_release_closure
from .workbench_release_frontier_offline_closure_reconciliation import reconcile_workbench_release_closure
from .workbench_release_frontier_offline_closure_runtime import run_workbench_release_closure_runtime
from .workbench_release_frontier_offline_closure_schema import build_workbench_release_closure_schema
from .workbench_release_frontier_offline_closure_summary import audit_workbench_release_closure_summary, build_workbench_release_closure_summary
from .deployment_frontier_offline_audit import audit_deployment_frontier_offline_bundle
from .deployment_frontier_offline_boundary import audit_deployment_frontier_offline_boundary
from .deployment_frontier_offline_bundle import build_deployment_frontier_offline_bundle
from .deployment_frontier_offline_certification import audit_deployment_frontier_offline_certification, certify_deployment_frontier_offline_bundle
from .deployment_frontier_offline_indexes import audit_deployment_frontier_offline_indexes, build_deployment_frontier_offline_indexes
from .deployment_frontier_offline_query import query_deployment_frontier_offline_bundle
from .deployment_frontier_offline_reconciliation import reconcile_deployment_frontier_offline_bundle
from .deployment_frontier_offline_runtime import build_deployment_frontier_offline_observability, run_deployment_frontier_offline_runtime
from .deployment_frontier_offline_schema import deployment_frontier_offline_bundle_schema
from .deployment_frontier_offline_summary import audit_deployment_frontier_offline_summary, build_deployment_frontier_offline_summary
from .deployment_frontier_offline_closure_boundary import audit_deployment_frontier_closure_boundary
from .deployment_frontier_offline_closure_certification import certify_deployment_frontier_closure
from .deployment_frontier_offline_closure_export import build_deployment_frontier_closure_export
from .deployment_frontier_offline_closure_failure_injection import build_deployment_frontier_closure_failure_report
from .deployment_frontier_offline_closure_graph import build_deployment_frontier_closure_graph
from .deployment_frontier_offline_closure_indexes import audit_deployment_frontier_closure_indexes, build_deployment_frontier_closure_indexes
from .deployment_frontier_offline_closure_observability import build_deployment_frontier_closure_observability
from .deployment_frontier_offline_closure_query import query_deployment_frontier_closure
from .deployment_frontier_offline_closure_reconciliation import reconcile_deployment_frontier_closure
from .deployment_frontier_offline_closure_runtime import run_deployment_frontier_closure_runtime
from .deployment_frontier_offline_closure_schema import build_deployment_frontier_closure_schema
from .deployment_frontier_offline_closure_summary import audit_deployment_frontier_closure_summary, build_deployment_frontier_closure_summary
from .frontier_release_closure_boundary import audit_frontier_release_boundary
from .frontier_release_closure_bundle import build_frontier_release_snapshot
from .frontier_release_closure_certification import certify_frontier_release
from .frontier_release_closure_export import build_frontier_release_export
from .frontier_release_closure_failure_injection import build_frontier_release_failure_report
from .frontier_release_closure_graph import build_frontier_release_graph
from .frontier_release_closure_indexes import audit_frontier_release_indexes, build_frontier_release_indexes
from .frontier_release_closure_observability import build_frontier_release_observability
from .frontier_release_closure_plan import audit_frontier_release_plan, build_frontier_release_plan
from .frontier_release_closure_query import query_frontier_release
from .frontier_release_closure_reconciliation import reconcile_frontier_release
from .frontier_release_closure_runtime import run_frontier_release_closure_runtime
from .frontier_release_closure_schema import audit_frontier_release_schema, build_frontier_release_schema
from .frontier_release_closure_summary import audit_frontier_release_summary, build_frontier_release_summary
from .program_release_closure_boundary import validate_program_release_closure_boundary
from .program_release_closure_bundle import build_program_release_snapshot
from .program_release_closure_certification import certify_program_release_closure
from .program_release_closure_export import build_program_release_export
from .program_release_closure_failure_injection import run_program_release_failure_injections
from .program_release_closure_graph import build_program_release_graph
from .program_release_closure_indexes import audit_program_release_closure_indexes, build_program_release_closure_indexes
from .program_release_closure_observability import build_program_release_observability
from .program_release_closure_operations import audit_program_release_operational_matrix, build_program_release_operational_matrix
from .program_release_closure_plan import audit_program_release_closure_plan, build_program_release_closure_plan
from .program_release_closure_query import query_program_release_closure
from .program_release_closure_reconciliation import reconcile_program_release_closure
from .program_release_closure_runtime import run_program_release_closure
from .program_release_closure_schema import program_release_closure_schema, validate_program_release_closure_schema
from .program_release_closure_summary import audit_program_release_closure_summary, build_program_release_closure_summary
from .program_release_closure_views import audit_program_release_review_views, build_program_release_review_views
from .program_runtime_offline_audit import audit_program_runtime_offline_bundle
from .program_runtime_offline_boundary import audit_program_runtime_offline_boundary
from .program_runtime_offline_bundle import build_program_runtime_offline_bundle
from .program_runtime_offline_certification import certify_program_runtime_offline_bundle
from .program_runtime_offline_indexes import audit_program_runtime_offline_indexes, build_program_runtime_offline_indexes
from .program_runtime_offline_query import query_program_runtime_offline_bundle
from .program_runtime_offline_reconciliation import reconcile_program_runtime_offline_bundle
from .program_runtime_offline_observability import (
    audit_program_runtime_offline_observability,
    build_program_runtime_offline_observability,
)
from .program_runtime_offline_runtime import run_program_runtime_offline_runtime
from .program_runtime_offline_schema import program_runtime_offline_bundle_schema
from .program_runtime_offline_summary import audit_program_runtime_offline_summary, build_program_runtime_offline_summary
from .storage_audit import build_storage_audit
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
from .service_release_bundle import build_service_release_snapshot
from .service_release_certification import certify_service_release
from .service_release_export import build_service_release_export
from .service_release_failure_injection import run_service_release_failure_injections
from .service_release_graph import build_service_release_graph
from .service_release_indexes import audit_service_release_indexes, build_service_release_indexes
from .service_release_observability import build_service_release_observability
from .service_release_plan import audit_service_release_plan, build_service_release_plan
from .service_release_query import query_service_release
from .service_release_reconciliation import (
    audit_service_release_summary,
    build_service_release_summary,
    reconcile_service_release,
)
from .service_release_runtime import run_service_release
from .service_release_schema import service_release_schema, validate_service_release_schema
from .service_release_views import audit_service_release_views, build_service_release_views
from .release_assurance_bundle import build_release_assurance_snapshot
from .release_assurance_catalog import build_release_assurance_catalog
from .release_assurance_checkpoint import audit_release_assurance_checkpoint, build_release_assurance_checkpoint
from .release_assurance_compliance import audit_release_assurance_compliance, compliance_summary
from .release_assurance_diff import audit_release_assurance_diff, build_release_assurance_diff
from .release_assurance_export import build_release_assurance_export
from .release_assurance_failure_injection import run_release_assurance_failure_injections
from .release_assurance_graph import build_release_assurance_graph
from .release_assurance_history import audit_release_assurance_history, build_release_assurance_history, query_release_assurance_history
from .release_assurance_handoff import (
    build_release_assurance_handoff,
    diff_release_assurance_handoffs,
    inspect_release_assurance_handoff,
    query_release_assurance_handoff,
    release_assurance_handoff_status,
    replay_release_assurance_handoff,
    verify_release_assurance_handoff,
)
from .release_assurance_indexes import audit_release_assurance_indexes, build_release_assurance_indexes
from .release_assurance_observability import build_release_assurance_observability
from .release_assurance_operations import audit_release_assurance_operations, build_release_assurance_operations
from .release_assurance_plan import audit_release_assurance_plan, build_release_assurance_plan
from .release_assurance_performance import audit_release_assurance_performance, release_assurance_budget_status
from .release_assurance_query import query_release_assurance
from .release_assurance_reconciliation import audit_release_assurance_reconciliation, reconcile_release_assurance
from .release_assurance_reports import render_release_assurance_report_markdown
from .release_assurance_review import audit_release_assurance_review_queue, build_release_assurance_review_queue
from .release_assurance_runtime import run_release_assurance
from .release_assurance_schema import release_assurance_schema, validate_release_assurance_schema
from .release_assurance_summary import audit_release_assurance_summary, build_release_assurance_summary, release_assurance_status
from .release_assurance_thresholds import evaluate_release_assurance_thresholds, release_assurance_threshold_status
from .release_assurance_views import audit_release_assurance_views, build_release_assurance_views


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

    def _program_offline_bundle(self, bundle_id: str, run_id: str):
        """Reuse one immutable offline build across related GET projections."""

        cache = getattr(self.server, "glio_program_offline_bundles", None)
        if cache is None:
            cache = {}
            setattr(self.server, "glio_program_offline_bundles", cache)
        key = (bundle_id, run_id)
        bundle = cache.get(key)
        if bundle is None:
            bundle = build_program_runtime_offline_bundle(bundle_id=bundle_id, run_id=run_id)
            cache[key] = bundle
        return bundle

    def _program_release_closure_source(self, bundle_id: str, run_id: str):
        """Cache the expensive sixteen-domain source handoff for closure routes."""

        cache = getattr(self.server, "glio_program_release_closure_sources", None)
        if cache is None:
            cache = {}
            setattr(self.server, "glio_program_release_closure_sources", cache)
        key = (bundle_id, run_id)
        bundle = cache.get(key)
        if bundle is None:
            bundle = self._program_offline_bundle(bundle_id, run_id)
            cache[key] = bundle
        return bundle

    def _service_surface(self):
        snapshot = getattr(self.server, "glio_service_surface", None)
        if snapshot is None:
            snapshot = build_service_surface_snapshot()
            setattr(self.server, "glio_service_surface", snapshot)  # noqa: B010 - lazy server-local cache
        return snapshot

    def _service_release(self, bundle_id: str):
        """Cache one service-release registry per requested bundle identifier."""

        cache = getattr(self.server, "glio_service_release_snapshots", None)
        if cache is None:
            cache = {}
            setattr(self.server, "glio_service_release_snapshots", cache)
        snapshot = cache.get(bundle_id)
        if snapshot is None:
            snapshot = build_service_release_snapshot(self._service_surface(), bundle_id=bundle_id)
            cache[bundle_id] = snapshot
        return snapshot

    def _release_assurance(self, bundle_id: str, run_id: str):
        """Cache one aggregate release-assurance snapshot per request identity."""

        cache = getattr(self.server, "glio_release_assurance_snapshots", None)
        if cache is None:
            cache = {}
            setattr(self.server, "glio_release_assurance_snapshots", cache)
        key = (bundle_id, run_id)
        snapshot = cache.get(key)
        if snapshot is None:
            snapshot = build_release_assurance_snapshot(
                self._service_surface(), bundle_id=bundle_id, run_id=run_id
            )
            cache[key] = snapshot
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
        if path == "/v1/public-surface/audit":
            try:
                self._write(HTTPStatus.OK, build_default_public_surface_audit().to_dict())
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path == "/v1/storage/audit":
            try:
                self._write(HTTPStatus.OK, build_storage_audit(self._runtime()).to_dict())
            except StoreError:
                self._write(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": "storage root not found"})
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path in {
            "/v1/service-release",
            "/v1/service-release/query",
            "/v1/service-release/schema",
            "/v1/service-release/indexes",
            "/v1/service-release/reconciliation",
            "/v1/service-release/summary",
            "/v1/service-release/certification",
            "/v1/service-release/observability",
            "/v1/service-release/graph",
            "/v1/service-release/failures",
            "/v1/service-release/plan",
            "/v1/service-release/views",
            "/v1/service-release/runtime",
            "/v1/service-release/export",
        }:
            try:
                query = parse_qs(parsed.query, keep_blank_values=False)
                bundle_id = self._query_value(query, "bundle_id") or "glio-noncode-service-release"
                run_id = self._query_value(query, "run_id") or "glio-noncode-service-release-run"
                source = self._service_surface()
                snapshot = self._service_release(bundle_id)
                if path.endswith("/schema"):
                    schema = service_release_schema()
                    self._write(HTTPStatus.OK, {"schema": schema, "audit": [item.to_dict() for item in validate_service_release_schema(snapshot, schema)]})
                    return
                if path.endswith("/runtime"):
                    self._write(HTTPStatus.OK, run_service_release(source, bundle_id=bundle_id, run_id=run_id).to_dict())
                    return
                if path.endswith("/export"):
                    runtime = run_service_release(source, bundle_id=bundle_id, run_id=run_id)
                    self._write(HTTPStatus.OK, build_service_release_export(runtime, source).to_dict())
                    return
                if path == "/v1/service-release":
                    payload = snapshot.to_dict()
                elif path.endswith("/query"):
                    payload = query_service_release(
                        snapshot,
                        resource=self._query_value(query, "resource") or "surfaces",
                        surface_id=self._query_value(query, "surface_id"),
                        state=self._query_value(query, "state"),
                        relation=self._query_value(query, "relation"),
                        accepted_only=self._query_bool(query, "accepted"),
                        text=self._query_value(query, "q") or self._query_value(query, "text"),
                        offset=self._query_int(query, "offset", 0),
                        limit=self._query_int(query, "limit", 50),
                    ).to_dict()
                elif path.endswith("/indexes"):
                    indexes = build_service_release_indexes(snapshot)
                    payload = {"indexes": indexes.to_dict(), "audit": audit_service_release_indexes(snapshot, indexes).to_dict()}
                elif path.endswith("/reconciliation"):
                    payload = reconcile_service_release(snapshot, source).to_dict()
                elif path.endswith("/summary"):
                    summary = build_service_release_summary(snapshot, source)
                    payload = {"summary": summary.to_dict(), "audit": audit_service_release_summary(summary, source).to_dict()}
                elif path.endswith("/certification"):
                    payload = certify_service_release(snapshot).to_dict()
                elif path.endswith("/observability"):
                    payload = build_service_release_observability(snapshot).to_dict()
                elif path.endswith("/graph"):
                    payload = build_service_release_graph(snapshot).to_dict()
                elif path.endswith("/failures"):
                    payload = run_service_release_failure_injections(snapshot).to_dict()
                elif path.endswith("/plan"):
                    plan = build_service_release_plan(snapshot)
                    payload = {"plan": plan.to_dict(), "audit": [item.to_dict() for item in audit_service_release_plan(plan)]}
                elif path.endswith("/views"):
                    views = build_service_release_views(snapshot)
                    payload = {"views": views.to_dict(), "audit": [item.to_dict() for item in audit_service_release_views(views, snapshot)]}
                else:
                    payload = {"error": "unknown_service_release_path"}
                self._write(HTTPStatus.OK, payload)
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path in {
            "/v1/release-assurance",
            "/v1/release-assurance/query",
            "/v1/release-assurance/schema",
            "/v1/release-assurance/status",
            "/v1/release-assurance/reconciliation",
            "/v1/release-assurance/diff",
            "/v1/release-assurance/catalog",
            "/v1/release-assurance/compliance",
            "/v1/release-assurance/performance",
            "/v1/release-assurance/operations",
            "/v1/release-assurance/report",
            "/v1/release-assurance/checkpoint",
            "/v1/release-assurance/review",
            "/v1/release-assurance/history",
            "/v1/release-assurance/thresholds",
            "/v1/release-assurance/handoff",
            "/v1/release-assurance/handoff/status",
            "/v1/release-assurance/handoff/inspect",
            "/v1/release-assurance/handoff/verify",
            "/v1/release-assurance/handoff/query",
            "/v1/release-assurance/handoff/diff",
            "/v1/release-assurance/handoff/replay",
            "/v1/release-assurance/indexes",
            "/v1/release-assurance/summary",
            "/v1/release-assurance/observability",
            "/v1/release-assurance/graph",
            "/v1/release-assurance/failures",
            "/v1/release-assurance/plan",
            "/v1/release-assurance/views",
            "/v1/release-assurance/runtime",
            "/v1/release-assurance/export",
        }:
            try:
                query = parse_qs(parsed.query, keep_blank_values=False)
                bundle_id = self._query_value(query, "bundle_id") or "glio-noncode-release-assurance"
                run_id = self._query_value(query, "run_id") or "glio-noncode-release-assurance-run"
                source = self._service_surface()
                snapshot = self._release_assurance(bundle_id, run_id)
                if path.endswith("/schema"):
                    schema = release_assurance_schema()
                    payload = {"schema": schema, "audit": [item.to_dict() for item in validate_release_assurance_schema(snapshot, schema)]}
                elif path.endswith("/runtime"):
                    payload = run_release_assurance(source, bundle_id=bundle_id, run_id=run_id).to_dict()
                elif path.endswith("/export"):
                    runtime = run_release_assurance(source, bundle_id=bundle_id, run_id=run_id)
                    payload = build_release_assurance_export(runtime).to_dict()
                elif path == "/v1/release-assurance/status":
                    payload = release_assurance_status(snapshot)
                elif path.endswith("/reconciliation"):
                    report = reconcile_release_assurance(snapshot, source_snapshot=source)
                    payload = {"report": report.to_dict(), "audit": [item.to_dict() for item in audit_release_assurance_reconciliation(report, snapshot)]}
                elif path == "/v1/release-assurance/diff":
                    compare_bundle_id = self._query_value(query, "compare_bundle_id") or f"{bundle_id}-comparison"
                    compare_run_id = self._query_value(query, "compare_run_id") or f"{run_id}-comparison"
                    comparison = build_release_assurance_snapshot(source, bundle_id=compare_bundle_id, run_id=compare_run_id)
                    diff = build_release_assurance_diff(snapshot, comparison)
                    payload = {"diff": diff.to_dict(), "audit": [item.to_dict() for item in audit_release_assurance_diff(diff, snapshot, comparison)]}
                elif path.endswith("/catalog"):
                    payload = build_release_assurance_catalog(snapshot).to_dict()
                elif path.endswith("/compliance"):
                    report = audit_release_assurance_compliance(snapshot)
                    payload = {"report": report.to_dict(), "summary": compliance_summary(report)}
                elif path.endswith("/performance"):
                    report = audit_release_assurance_performance(snapshot)
                    payload = {"report": report.to_dict(), "status": release_assurance_budget_status(report)}
                elif path.endswith("/operations"):
                    operations = build_release_assurance_operations(snapshot)
                    payload = {"operations": operations.to_dict(), "audit": [item.to_dict() for item in audit_release_assurance_operations(operations, snapshot)]}
                elif path.endswith("/report"):
                    runtime = run_release_assurance(source, bundle_id=bundle_id, run_id=run_id)
                    payload = {"markdown": render_release_assurance_report_markdown(runtime).decode("utf-8"), "runtime": runtime.to_dict()}
                elif path.endswith("/checkpoint"):
                    runtime = run_release_assurance(source, bundle_id=bundle_id, run_id=run_id)
                    checkpoint = build_release_assurance_checkpoint(runtime)
                    payload = {"checkpoint": checkpoint.to_dict(), "audit": [item.to_dict() for item in audit_release_assurance_checkpoint(checkpoint, runtime)]}
                elif path.endswith("/review"):
                    runtime = run_release_assurance(source, bundle_id=bundle_id, run_id=run_id)
                    queue = build_release_assurance_review_queue(runtime)
                    payload = {"review": queue.to_dict(), "audit": [item.to_dict() for item in audit_release_assurance_review_queue(queue, runtime)]}
                elif path.endswith("/history"):
                    runtime = run_release_assurance(source, bundle_id=bundle_id, run_id=run_id)
                    history = build_release_assurance_history(runtime)
                    if self._query_value(query, "event_type") or self._query_value(query, "state") or self._query_value(query, "text"):
                        payload = {
                            "history": history.to_dict(),
                            "items": [item.to_dict() for item in query_release_assurance_history(
                                history,
                                event_type=self._query_value(query, "event_type"),
                                state=self._query_value(query, "state"),
                                text=self._query_value(query, "text"),
                                offset=self._query_int(query, "offset", 0),
                                limit=self._query_int(query, "limit", 50),
                            )],
                        }
                    else:
                        payload = history.to_dict()
                elif path.endswith("/thresholds"):
                    report = evaluate_release_assurance_thresholds(snapshot)
                    payload = {"report": report.to_dict(), "status": release_assurance_threshold_status(report)}
                elif path == "/v1/release-assurance/handoff":
                    runtime = run_release_assurance(source, bundle_id=bundle_id, run_id=run_id)
                    payload = build_release_assurance_handoff(runtime).to_dict()
                elif path.endswith("/handoff/status"):
                    directory = self._query_value(query, "directory")
                    if not directory:
                        raise ValueError("directory is required for handoff status")
                    payload = release_assurance_handoff_status(directory)
                elif path.endswith("/handoff/inspect"):
                    directory = self._query_value(query, "directory")
                    if not directory:
                        raise ValueError("directory is required for handoff inspection")
                    payload = inspect_release_assurance_handoff(directory).to_dict()
                elif path.endswith("/handoff/verify"):
                    directory = self._query_value(query, "directory")
                    if not directory:
                        raise ValueError("directory is required for handoff verification")
                    payload = verify_release_assurance_handoff(directory).to_dict()
                elif path.endswith("/handoff/query"):
                    directory = self._query_value(query, "directory")
                    if not directory:
                        raise ValueError("directory is required for handoff query")
                    payload = query_release_assurance_handoff(
                        directory,
                        resource=self._query_value(query, "resource") or "artifacts",
                        artifact_id=self._query_value(query, "artifact_id"),
                        role=self._query_value(query, "role"),
                        media_type=self._query_value(query, "media_type"),
                        required_only=self._query_bool(query, "required_only"),
                        text=self._query_value(query, "q") or self._query_value(query, "text"),
                        offset=self._query_int(query, "offset", 0),
                        limit=self._query_int(query, "limit", 50),
                    ).to_dict()
                elif path.endswith("/handoff/diff"):
                    left_directory = self._query_value(query, "left_directory")
                    right_directory = self._query_value(query, "right_directory")
                    if not left_directory or not right_directory:
                        raise ValueError("left_directory and right_directory are required for handoff diff")
                    payload = diff_release_assurance_handoffs(left_directory, right_directory).to_dict()
                elif path.endswith("/handoff/replay"):
                    directory = self._query_value(query, "directory")
                    if not directory:
                        raise ValueError("directory is required for handoff replay")
                    payload = replay_release_assurance_handoff(directory)
                elif path == "/v1/release-assurance":
                    payload = snapshot.to_dict()
                elif path.endswith("/query"):
                    payload = query_release_assurance(
                        snapshot,
                        resource=self._query_value(query, "resource") or "domains",
                        domain_id=self._query_value(query, "domain_id"),
                        plane=self._query_value(query, "assurance_plane"),
                        state=self._query_value(query, "state"),
                        passed_only=self._query_bool(query, "passed_only"),
                        text=self._query_value(query, "q") or self._query_value(query, "text"),
                        offset=self._query_int(query, "offset", 0),
                        limit=self._query_int(query, "limit", 50),
                    ).to_dict()
                elif path.endswith("/indexes"):
                    indexes = build_release_assurance_indexes(snapshot)
                    payload = {"indexes": indexes.to_dict(), "audit": audit_release_assurance_indexes(snapshot, indexes).to_dict()}
                elif path.endswith("/summary"):
                    summary = build_release_assurance_summary(snapshot)
                    payload = {"summary": summary.to_dict(), "audit": audit_release_assurance_summary(summary, snapshot).to_dict()}
                elif path.endswith("/observability"):
                    payload = build_release_assurance_observability(snapshot).to_dict()
                elif path.endswith("/graph"):
                    payload = build_release_assurance_graph(snapshot).to_dict()
                elif path.endswith("/failures"):
                    payload = run_release_assurance_failure_injections(snapshot).to_dict()
                elif path.endswith("/plan"):
                    plan = build_release_assurance_plan(snapshot)
                    payload = {"plan": plan.to_dict(), "audit": [item.to_dict() for item in audit_release_assurance_plan(plan)]}
                elif path.endswith("/views"):
                    views = build_release_assurance_views(snapshot)
                    payload = {"views": views.to_dict(), "audit": [item.to_dict() for item in audit_release_assurance_views(views, snapshot)]}
                else:
                    payload = {"error": "unknown_release_assurance_path"}
                self._write(HTTPStatus.OK, payload)
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path in {
            "/v1/program-release/closure",
            "/v1/program-release/closure/query",
            "/v1/program-release/closure/schema",
            "/v1/program-release/closure/boundary",
            "/v1/program-release/closure/indexes",
            "/v1/program-release/closure/reconciliation",
            "/v1/program-release/closure/summary",
            "/v1/program-release/closure/certification",
            "/v1/program-release/closure/observability",
            "/v1/program-release/closure/operations",
            "/v1/program-release/closure/views",
            "/v1/program-release/closure/graph",
            "/v1/program-release/closure/failures",
            "/v1/program-release/closure/plan",
            "/v1/program-release/closure/runtime",
            "/v1/program-release/closure/export",
        }:
            try:
                query = parse_qs(parsed.query, keep_blank_values=False)
                bundle_id = self._query_value(query, "bundle_id") or "glio-noncode-program-release-closure"
                run_id = self._query_value(query, "run_id") or "glio-noncode-program-release-closure-run"
                source = self._program_release_closure_source(bundle_id, run_id)
                if path.endswith("/schema"):
                    snapshot = build_program_release_snapshot(source, bundle_id=bundle_id, run_id=run_id)
                    schema = program_release_closure_schema()
                    self._write(HTTPStatus.OK, {"schema": schema, "audit": validate_program_release_closure_schema(snapshot, schema)})
                    return
                if path.endswith("/runtime"):
                    self._write(HTTPStatus.OK, run_program_release_closure(source, bundle_id=bundle_id, run_id=run_id).to_dict())
                    return
                if path.endswith("/export"):
                    runtime = run_program_release_closure(source, bundle_id=bundle_id, run_id=run_id)
                    self._write(HTTPStatus.OK, build_program_release_export(runtime).to_dict())
                    return
                snapshot = build_program_release_snapshot(source, bundle_id=bundle_id, run_id=run_id)
                if path == "/v1/program-release/closure":
                    payload = snapshot.to_dict()
                elif path.endswith("/query"):
                    payload = query_program_release_closure(snapshot, resource=self._query_value(query, "resource") or "domains", domain_id=self._query_value(query, "domain_id"), gate_type=self._query_value(query, "gate_type"), state=self._query_value(query, "state"), relation=self._query_value(query, "relation"), accepted_only=self._query_bool(query, "accepted"), text=self._query_value(query, "q") or self._query_value(query, "text"), offset=self._query_int(query, "offset", 0), limit=self._query_int(query, "limit", 50)).to_dict()
                elif path.endswith("/boundary"):
                    payload = validate_program_release_closure_boundary(snapshot)
                elif path.endswith("/indexes"):
                    indexes = build_program_release_closure_indexes(snapshot)
                    payload = {"indexes": indexes.to_dict(), "audit": audit_program_release_closure_indexes(snapshot, indexes).to_dict()}
                elif path.endswith("/reconciliation"):
                    payload = reconcile_program_release_closure(snapshot, source).to_dict()
                elif path.endswith("/summary"):
                    summary = build_program_release_closure_summary(snapshot, source)
                    payload = {"summary": summary.to_dict(), "audit": audit_program_release_closure_summary(summary, source).to_dict()}
                elif path.endswith("/certification"):
                    payload = certify_program_release_closure(snapshot).to_dict()
                elif path.endswith("/observability"):
                    payload = build_program_release_observability(snapshot).to_dict()
                elif path.endswith("/operations"):
                    operations = build_program_release_operational_matrix(snapshot)
                    payload = {"operations": operations.to_dict(), "audit": audit_program_release_operational_matrix(operations).to_dict()}
                elif path.endswith("/views"):
                    views = build_program_release_review_views(snapshot)
                    payload = {"views": views.to_dict(), "audit": [item.to_dict() for item in audit_program_release_review_views(views, snapshot)]}
                elif path.endswith("/graph"):
                    payload = build_program_release_graph(snapshot).to_dict()
                elif path.endswith("/failures"):
                    payload = run_program_release_failure_injections(snapshot).to_dict()
                elif path.endswith("/plan"):
                    plan = build_program_release_closure_plan(snapshot)
                    payload = {"plan": plan.to_dict(), "audit": [item.to_dict() for item in audit_program_release_closure_plan(plan)]}
                else:  # pragma: no cover - path set is exhaustive
                    payload = {"error": "unknown_program_release_closure_path"}
                self._write(HTTPStatus.OK, payload)
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path in {
            "/v1/frontier-release/closure",
            "/v1/frontier-release/closure/query",
            "/v1/frontier-release/closure/schema",
            "/v1/frontier-release/closure/boundary",
            "/v1/frontier-release/closure/indexes",
            "/v1/frontier-release/closure/reconciliation",
            "/v1/frontier-release/closure/summary",
            "/v1/frontier-release/closure/certification",
            "/v1/frontier-release/closure/observability",
            "/v1/frontier-release/closure/graph",
            "/v1/frontier-release/closure/failures",
            "/v1/frontier-release/closure/plan",
            "/v1/frontier-release/closure/runtime",
            "/v1/frontier-release/closure/export",
        }:
            try:
                query = parse_qs(parsed.query, keep_blank_values=False)
                bundle_id = self._query_value(query, "bundle_id") or "frontier-release-public-bundle"
                run_id = self._query_value(query, "run_id") or "frontier-release-closure-runtime"
                if path.endswith("/schema"):
                    schema = build_frontier_release_schema()
                    snapshot = build_frontier_release_snapshot(bundle_id=bundle_id, run_id=run_id)
                    self._write(
                        HTTPStatus.OK,
                        {
                            "schema": schema,
                            "schema_audit": [item.to_dict() for item in audit_frontier_release_schema(snapshot, schema)],
                        },
                    )
                    return
                if path.endswith("/runtime"):
                    self._write(
                        HTTPStatus.OK,
                        run_frontier_release_closure_runtime(bundle_id=bundle_id, run_id=run_id).to_dict(),
                    )
                    return
                if path.endswith("/export"):
                    runtime = run_frontier_release_closure_runtime(bundle_id=bundle_id, run_id=run_id)
                    self._write(HTTPStatus.OK, build_frontier_release_export(runtime).to_dict())
                    return
                snapshot = build_frontier_release_snapshot(bundle_id=bundle_id, run_id=run_id)
                if path == "/v1/frontier-release/closure":
                    payload = snapshot.to_dict()
                elif path.endswith("/query"):
                    payload = query_frontier_release(
                        snapshot,
                        resource=self._query_value(query, "resource") or "domains",
                        domain_id=self._query_value(query, "domain_id"),
                        gate_type=self._query_value(query, "gate_type"),
                        state=self._query_value(query, "state"),
                        relation=self._query_value(query, "relation"),
                        accepted=self._query_value(query, "accepted"),
                        text=self._query_value(query, "q") or self._query_value(query, "text"),
                        offset=self._query_int(query, "offset", 0),
                        limit=self._query_int(query, "limit", 50),
                    ).to_dict()
                elif path.endswith("/boundary"):
                    payload = audit_frontier_release_boundary(snapshot).to_dict()
                elif path.endswith("/indexes"):
                    indexes = build_frontier_release_indexes(snapshot)
                    payload = {
                        "indexes": indexes.to_dict(),
                        "audit": audit_frontier_release_indexes(snapshot, indexes).to_dict(),
                    }
                elif path.endswith("/reconciliation"):
                    payload = reconcile_frontier_release(snapshot).to_dict()
                elif path.endswith("/summary"):
                    summary = build_frontier_release_summary(snapshot)
                    payload = {
                        "summary": summary.to_dict(),
                        "audit": audit_frontier_release_summary(summary).to_dict(),
                    }
                elif path.endswith("/certification"):
                    payload = certify_frontier_release(snapshot).to_dict()
                elif path.endswith("/observability"):
                    payload = build_frontier_release_observability(snapshot).to_dict()
                elif path.endswith("/graph"):
                    payload = build_frontier_release_graph(snapshot).to_dict()
                elif path.endswith("/failures"):
                    payload = build_frontier_release_failure_report(snapshot).to_dict()
                elif path.endswith("/plan"):
                    plan = build_frontier_release_plan(snapshot)
                    payload = {"plan": plan.to_dict(), "audit": audit_frontier_release_plan(plan)}
                else:  # pragma: no cover - path set is exhaustive
                    payload = {"error": "unknown_frontier_release_path"}
                self._write(HTTPStatus.OK, payload)
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path in {
            "/v1/deployment-frontier/bundle/closure-query",
            "/v1/deployment-frontier/bundle/closure-schema",
            "/v1/deployment-frontier/bundle/closure-boundary",
            "/v1/deployment-frontier/bundle/closure-indexes",
            "/v1/deployment-frontier/bundle/closure-reconciliation",
            "/v1/deployment-frontier/bundle/closure-summary",
            "/v1/deployment-frontier/bundle/closure-certification",
            "/v1/deployment-frontier/bundle/closure-observability",
            "/v1/deployment-frontier/bundle/closure-runtime",
            "/v1/deployment-frontier/bundle/closure-failures",
            "/v1/deployment-frontier/bundle/closure-graph",
            "/v1/deployment-frontier/bundle/closure-export",
        }:
            try:
                query = parse_qs(parsed.query, keep_blank_values=False)
                bundle_id = self._query_value(query, "bundle_id") or "deployment-frontier-public-bundle"
                run_id = self._query_value(query, "run_id") or "deployment-frontier-offline-runtime"
                if path.endswith("/closure-schema"):
                    self._write(HTTPStatus.OK, build_deployment_frontier_closure_schema())
                    return
                bundle = build_deployment_frontier_offline_bundle(bundle_id=bundle_id, run_id=run_id)
                if path.endswith("/closure-query"):
                    payload = query_deployment_frontier_closure(
                        bundle,
                        resource=self._query_value(query, "resource") or "records",
                        operation=self._query_value(query, "operation"),
                        role=self._query_value(query, "role"),
                        state=self._query_value(query, "state"),
                        capability=self._query_value(query, "capability"),
                        priority=self._query_value(query, "priority"),
                        severity=self._query_value(query, "severity"),
                        stage_id=self._query_value(query, "stage_id"),
                        text=self._query_value(query, "q") or self._query_value(query, "text"),
                        offset=self._query_int(query, "offset", 0),
                        limit=self._query_int(query, "limit", 50),
                    ).to_dict()
                elif path.endswith("/closure-boundary"):
                    payload = audit_deployment_frontier_closure_boundary(bundle).to_dict()
                elif path.endswith("/closure-indexes"):
                    indexes = build_deployment_frontier_closure_indexes(bundle)
                    payload = {"indexes": indexes.to_dict(), "audit": audit_deployment_frontier_closure_indexes(bundle, indexes).to_dict()}
                elif path.endswith("/closure-reconciliation"):
                    payload = reconcile_deployment_frontier_closure(bundle).to_dict()
                elif path.endswith("/closure-summary"):
                    summary = build_deployment_frontier_closure_summary(bundle)
                    payload = {"summary": summary.to_dict(), "audit": audit_deployment_frontier_closure_summary(summary).to_dict()}
                elif path.endswith("/closure-certification"):
                    payload = certify_deployment_frontier_closure(bundle).to_dict()
                elif path.endswith("/closure-observability"):
                    payload = build_deployment_frontier_closure_observability(bundle).to_dict()
                elif path.endswith("/closure-runtime"):
                    payload = run_deployment_frontier_closure_runtime(bundle_id=bundle_id, run_id=run_id).to_dict()
                elif path.endswith("/closure-failures"):
                    payload = build_deployment_frontier_closure_failure_report(bundle).to_dict()
                elif path.endswith("/closure-graph"):
                    payload = build_deployment_frontier_closure_graph(bundle).to_dict()
                elif path.endswith("/closure-export"):
                    payload = build_deployment_frontier_closure_export(bundle).to_dict()
                else:  # pragma: no cover - path set is exhaustive
                    payload = {"error": "unknown_closure_path"}
                self._write(HTTPStatus.OK, payload)
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path in {
            "/v1/architecture/offline/bundle",
            "/v1/architecture/offline/query",
            "/v1/architecture/offline/schema",
            "/v1/architecture/offline/audit",
            "/v1/architecture/offline/boundary",
            "/v1/architecture/offline/indexes",
            "/v1/architecture/offline/reconciliation",
            "/v1/architecture/offline/summary",
            "/v1/architecture/offline/runtime",
            "/v1/architecture/offline/certification",
            "/v1/architecture/offline/observability",
        }:
            try:
                query = parse_qs(parsed.query, keep_blank_values=False)
                if path.endswith("/schema"):
                    self._write(HTTPStatus.OK, program_runtime_offline_bundle_schema())
                    return
                if path.endswith("/runtime"):
                    report = run_program_runtime_offline_runtime(
                        bundle_id=self._query_value(query, "bundle_id") or "architecture-program-public-bundle",
                        run_id=self._query_value(query, "run_id") or "architecture-program-offline-runtime",
                    )
                    self._write(HTTPStatus.OK, report.to_dict())
                    return
                bundle = self._program_offline_bundle(
                    self._query_value(query, "bundle_id") or "architecture-program-public-bundle",
                    self._query_value(query, "run_id") or "architecture-program-offline-runtime",
                )
                if path.endswith("/query"):
                    result = query_program_runtime_offline_bundle(
                        bundle,
                        resource=self._query_value(query, "resource") or "artifacts",
                        domain_id=self._query_value(query, "domain_id"),
                        state=self._query_value(query, "state"),
                        accepted_only=self._query_bool(query, "accepted_only"),
                        text=self._query_value(query, "text") or self._query_value(query, "q"),
                        offset=self._query_int(query, "offset", 0),
                        limit=self._query_int(query, "limit", 50),
                    )
                    self._write(HTTPStatus.OK, result.to_dict())
                elif path.endswith("/audit"):
                    self._write(HTTPStatus.OK, audit_program_runtime_offline_bundle(bundle).to_dict())
                elif path.endswith("/boundary"):
                    self._write(HTTPStatus.OK, audit_program_runtime_offline_boundary(bundle))
                elif path.endswith("/indexes"):
                    indexes = build_program_runtime_offline_indexes(bundle)
                    audit = audit_program_runtime_offline_indexes(bundle, indexes)
                    self._write(HTTPStatus.OK, {"indexes": indexes.to_dict(), "audit": audit.to_dict()})
                elif path.endswith("/reconciliation"):
                    self._write(HTTPStatus.OK, reconcile_program_runtime_offline_bundle(bundle).to_dict())
                elif path.endswith("/summary"):
                    summary = build_program_runtime_offline_summary(bundle)
                    audit = audit_program_runtime_offline_summary(summary)
                    self._write(HTTPStatus.OK, {"summary": summary.to_dict(), "audit": audit.to_dict()})
                elif path.endswith("/certification"):
                    self._write(HTTPStatus.OK, certify_program_runtime_offline_bundle(bundle).to_dict())
                elif path.endswith("/observability"):
                    report = build_program_runtime_offline_observability(bundle)
                    self._write(
                        HTTPStatus.OK,
                        {"observability": report.to_dict(), "audit": audit_program_runtime_offline_observability(report)},
                    )
                else:
                    self._write(HTTPStatus.OK, bundle.to_dict(include_payloads=self._query_bool(query, "include_payloads")))
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path in {
            "/v1/workbench-release/bundle",
            "/v1/workbench-release/bundle/query",
            "/v1/workbench-release/bundle/schema",
            "/v1/workbench-release/bundle/audit",
            "/v1/workbench-release/bundle/observability",
            "/v1/workbench-release/bundle/runtime",
            "/v1/workbench-release/bundle/indexes",
            "/v1/workbench-release/bundle/boundary",
            "/v1/workbench-release/bundle/reconciliation",
            "/v1/workbench-release/bundle/summary",
            "/v1/workbench-release/bundle/certification",
            "/v1/workbench-release/bundle/closure-query",
            "/v1/workbench-release/bundle/closure-schema",
            "/v1/workbench-release/bundle/closure-boundary",
            "/v1/workbench-release/bundle/closure-indexes",
            "/v1/workbench-release/bundle/closure-reconciliation",
            "/v1/workbench-release/bundle/closure-summary",
            "/v1/workbench-release/bundle/closure-certification",
            "/v1/workbench-release/bundle/closure-observability",
            "/v1/workbench-release/bundle/closure-runtime",
            "/v1/workbench-release/bundle/closure-failures",
            "/v1/workbench-release/bundle/closure-graph",
            "/v1/workbench-release/bundle/closure-export",
        }:
            try:
                if path.endswith("/closure-schema"):
                    self._write(HTTPStatus.OK, build_workbench_release_closure_schema())
                    return
                if path.endswith("/schema"):
                    self._write(HTTPStatus.OK, workbench_release_offline_bundle_schema())
                    return
                query = parse_qs(parsed.query, keep_blank_values=False)
                bundle = build_workbench_release_offline_bundle(
                    bundle_id=self._query_value(query, "bundle_id") or "workbench-release-public-bundle",
                    run_id=self._query_value(query, "run_id") or "workbench-release-offline-runtime",
                )
                if path.endswith("/closure-query"):
                    payload = query_workbench_release_closure(
                        bundle,
                        resource=self._query_value(query, "resource") or "records",
                        offset=self._query_int(query, "offset", 0),
                        limit=self._query_int(query, "limit", 50),
                        filters={
                            "operation": self._query_value(query, "operation"),
                            "role": self._query_value(query, "role"),
                            "state": self._query_value(query, "state"),
                            "capability": self._query_value(query, "capability"),
                            "priority": self._query_value(query, "priority"),
                            "severity": self._query_value(query, "severity"),
                            "stage_id": self._query_value(query, "stage_id"),
                            "text": self._query_value(query, "q") or self._query_value(query, "text"),
                        },
                    ).to_dict()
                elif path.endswith("/closure-boundary"):
                    payload = audit_workbench_release_closure_boundary(bundle).to_dict()
                elif path.endswith("/closure-indexes"):
                    indexes = build_workbench_release_closure_indexes(bundle)
                    payload = {"indexes": indexes.to_dict(), "audit": audit_workbench_release_closure_indexes(bundle, indexes).to_dict()}
                elif path.endswith("/closure-reconciliation"):
                    payload = reconcile_workbench_release_closure(bundle).to_dict()
                elif path.endswith("/closure-summary"):
                    summary = build_workbench_release_closure_summary(bundle)
                    payload = {"summary": summary.to_dict(), "audit": audit_workbench_release_closure_summary(summary).to_dict()}
                elif path.endswith("/closure-certification"):
                    payload = certify_workbench_release_closure(bundle).to_dict()
                elif path.endswith("/closure-observability"):
                    payload = build_workbench_release_closure_observability(bundle).to_dict()
                elif path.endswith("/closure-runtime"):
                    payload = run_workbench_release_closure_runtime(bundle_id=bundle.bundle_id, run_id=bundle.run_id).to_dict()
                elif path.endswith("/closure-failures"):
                    payload = build_workbench_release_closure_failure_report(bundle).to_dict()
                elif path.endswith("/closure-graph"):
                    payload = build_workbench_release_closure_graph(bundle).to_dict()
                elif path.endswith("/closure-export"):
                    payload = build_workbench_release_closure_export(bundle).to_dict()
                elif path.endswith("/query"):
                    payload = query_workbench_release_offline_bundle(
                        bundle,
                        resource=self._query_value(query, "resource") or "artifacts",
                        offset=self._query_int(query, "offset", 0),
                        limit=self._query_int(query, "limit", 50),
                        filters={
                            "operation": self._query_value(query, "operation"),
                            "role": self._query_value(query, "role"),
                            "state": self._query_value(query, "state"),
                            "capability": self._query_value(query, "capability"),
                            "record_id": self._query_value(query, "record_id"),
                            "text": self._query_value(query, "q") or self._query_value(query, "text"),
                        },
                    ).to_dict()
                elif path.endswith("/audit"):
                    payload = audit_workbench_release_offline_bundle(bundle).to_dict()
                elif path.endswith("/observability"):
                    payload = build_workbench_release_offline_observability(bundle).to_dict()
                elif path.endswith("/runtime"):
                    payload = run_workbench_release_offline_bundle_runtime(bundle_id=bundle.bundle_id, run_id=bundle.run_id).to_dict()
                elif path.endswith("/indexes"):
                    indexes = build_workbench_release_offline_indexes(bundle)
                    payload = {"indexes": indexes.to_dict(), "audit": audit_workbench_release_offline_indexes(bundle, indexes).to_dict()}
                elif path.endswith("/boundary"):
                    payload = audit_workbench_release_offline_boundary(bundle).to_dict()
                elif path.endswith("/reconciliation"):
                    payload = reconcile_workbench_release_offline_bundle(bundle).to_dict()
                elif path.endswith("/summary"):
                    summary = build_workbench_release_offline_summary(bundle)
                    payload = {"summary": summary.to_dict(), "audit": audit_workbench_release_offline_summary(summary).to_dict()}
                elif path.endswith("/certification"):
                    certification = certify_workbench_release_offline_bundle(bundle)
                    payload = {"certification": certification.to_dict(), "audit": audit_workbench_release_offline_certification(bundle, certification).to_dict()}
                else:
                    payload = bundle.to_dict(include_payloads=self._query_bool(query, "include_payloads"))
                self._write(HTTPStatus.OK, payload)
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path in {
            "/v1/deployment-frontier/bundle",
            "/v1/deployment-frontier/bundle/query",
            "/v1/deployment-frontier/bundle/schema",
            "/v1/deployment-frontier/bundle/audit",
            "/v1/deployment-frontier/bundle/observability",
            "/v1/deployment-frontier/bundle/runtime",
            "/v1/deployment-frontier/bundle/indexes",
            "/v1/deployment-frontier/bundle/boundary",
            "/v1/deployment-frontier/bundle/reconciliation",
            "/v1/deployment-frontier/bundle/summary",
            "/v1/deployment-frontier/bundle/certification",
        }:
            try:
                if path.endswith("/schema"):
                    self._write(HTTPStatus.OK, deployment_frontier_offline_bundle_schema())
                    return
                query = parse_qs(parsed.query, keep_blank_values=False)
                bundle = build_deployment_frontier_offline_bundle(
                    bundle_id=self._query_value(query, "bundle_id") or "deployment-frontier-public-bundle",
                    run_id=self._query_value(query, "run_id") or "deployment-frontier-offline-runtime",
                )
                if path.endswith("/query"):
                    payload = query_deployment_frontier_offline_bundle(
                        bundle,
                        resource=self._query_value(query, "resource") or "artifacts",
                        offset=self._query_int(query, "offset", 0),
                        limit=self._query_int(query, "limit", 50),
                        filters={
                            "operation": self._query_value(query, "operation"),
                            "role": self._query_value(query, "role"),
                            "state": self._query_value(query, "state"),
                            "record_id": self._query_value(query, "record_id"),
                            "text": self._query_value(query, "q") or self._query_value(query, "text"),
                        },
                    ).to_dict()
                elif path.endswith("/audit"):
                    payload = audit_deployment_frontier_offline_bundle(bundle).to_dict()
                elif path.endswith("/observability"):
                    payload = build_deployment_frontier_offline_observability(bundle).to_dict()
                elif path.endswith("/runtime"):
                    payload = run_deployment_frontier_offline_runtime(bundle_id=bundle.bundle_id, run_id=bundle.run_id).to_dict()
                elif path.endswith("/indexes"):
                    indexes = build_deployment_frontier_offline_indexes(bundle)
                    payload = {"indexes": indexes.to_dict(), "audit": audit_deployment_frontier_offline_indexes(bundle, indexes).to_dict()}
                elif path.endswith("/boundary"):
                    payload = audit_deployment_frontier_offline_boundary(bundle).to_dict()
                elif path.endswith("/reconciliation"):
                    payload = reconcile_deployment_frontier_offline_bundle(bundle).to_dict()
                elif path.endswith("/summary"):
                    summary = build_deployment_frontier_offline_summary(bundle)
                    payload = {"summary": summary.to_dict(), "audit": audit_deployment_frontier_offline_summary(summary).to_dict()}
                elif path.endswith("/certification"):
                    certification = certify_deployment_frontier_offline_bundle(bundle)
                    payload = {"certification": certification.to_dict(), "audit": audit_deployment_frontier_offline_certification(bundle, certification).to_dict()}
                else:
                    payload = bundle.to_dict(include_payloads=self._query_bool(query, "include_payloads"))
                self._write(HTTPStatus.OK, payload)
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path in {
            "/v1/capability-certification/bundle",
            "/v1/capability-certification/bundle/query",
            "/v1/capability-certification/bundle/observability",
            "/v1/capability-certification/bundle/runtime",
            "/v1/capability-certification/bundle/schema",
            "/v1/capability-certification/bundle/audit",
        }:
            try:
                if path.endswith("/schema"):
                    self._write(HTTPStatus.OK, capability_certification_bundle_schema())
                    return
                query = parse_qs(parsed.query, keep_blank_values=False)
                bundle = build_capability_certification_bundle(
                    bundle_id=self._query_value(query, "bundle_id") or "capability-certification-public-bundle",
                    run_id=self._query_value(query, "run_id"),
                )
                if path.endswith("/query"):
                    payload = query_capability_certification_bundle(
                        bundle,
                        resource=self._query_value(query, "resource") or "certificates",
                        capability_id=self._query_value(query, "capability_id"),
                        domain_id=self._query_value(query, "domain_id"),
                        mvp_only=self._query_bool(query, "mvp_only"),
                        state=self._query_value(query, "state"),
                        artifact_kind=self._query_value(query, "artifact_kind"),
                        text=self._query_value(query, "q") or self._query_value(query, "text"),
                        offset=self._query_int(query, "offset", 0),
                        limit=self._query_int(query, "limit", 50),
                        include_payloads=self._query_bool(query, "include_payloads"),
                    ).to_dict()
                elif path.endswith("/observability"):
                    artifact = next(item for item in bundle.artifacts if item.artifact_id == "observability")
                    payload = certification_bundle_observability_from_dict(json.loads(artifact.payload or "{}")).to_dict()
                elif path.endswith("/runtime"):
                    payload = run_capability_certification_bundle_runtime(
                        bundle_id=bundle.bundle_id,
                        run_id=bundle.run_id,
                    ).to_dict()
                elif path.endswith("/audit"):
                    payload = audit_capability_certification_bundle(bundle).to_dict()
                else:
                    payload = bundle.to_dict(include_payloads=self._query_bool(query, "include_payloads"))
                self._write(HTTPStatus.OK, payload)
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path in {
            "/v1/module-fabric/bundle",
            "/v1/module-fabric/bundle/query",
            "/v1/module-fabric/bundle/observability",
            "/v1/module-fabric/bundle/runtime",
            "/v1/module-fabric/bundle/schema",
            "/v1/module-fabric/bundle/audit",
        }:
            try:
                if path.endswith("/schema"):
                    self._write(HTTPStatus.OK, module_fabric_bundle_schema())
                    return
                query = parse_qs(parsed.query, keep_blank_values=False)
                bundle = build_module_fabric_bundle(
                    bundle_id=self._query_value(query, "bundle_id") or "module-fabric-public-bundle",
                    run_id=self._query_value(query, "run_id") or "module-fabric-bundle-runtime",
                )
                if path.endswith("/query"):
                    payload = query_module_fabric_bundle(
                        bundle,
                        resource=self._query_value(query, "resource") or "artifacts",
                        domain_id=self._query_value(query, "domain_id"),
                        capability_id=self._query_value(query, "capability_id"),
                        role=self._query_value(query, "role"),
                        state=self._query_value(query, "state"),
                        artifact_kind=self._query_value(query, "artifact_kind"),
                        text=self._query_value(query, "q") or self._query_value(query, "text"),
                        offset=self._query_int(query, "offset", 0),
                        limit=self._query_int(query, "limit", 50),
                        include_payloads=self._query_bool(query, "include_payloads"),
                    ).to_dict()
                elif path.endswith("/observability"):
                    payload = build_module_fabric_bundle_observability(bundle).to_dict()
                elif path.endswith("/runtime"):
                    payload = run_module_fabric_bundle_runtime(
                        bundle_id=bundle.bundle_id,
                        run_id=bundle.run_id,
                    ).to_dict()
                elif path.endswith("/audit"):
                    payload = audit_module_fabric_bundle(bundle).to_dict()
                else:
                    payload = bundle.to_dict(include_payloads=self._query_bool(query, "include_payloads"))
                self._write(HTTPStatus.OK, payload)
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path in {
            "/v1/validation-design/bundle",
            "/v1/validation-design/bundle/query",
            "/v1/validation-design/bundle/schema",
            "/v1/validation-design/bundle/audit",
            "/v1/validation-design/bundle/observability",
            "/v1/validation-design/bundle/runtime",
            "/v1/validation-design/bundle/closure-query",
            "/v1/validation-design/bundle/boundary",
            "/v1/validation-design/bundle/indexes",
            "/v1/validation-design/bundle/reconciliation",
            "/v1/validation-design/bundle/summary",
            "/v1/validation-design/bundle/certification",
            "/v1/validation-design/bundle/closure-observability",
            "/v1/validation-design/bundle/closure-runtime",
            "/v1/validation-design/bundle/closure-schema",
            "/v1/validation-design/bundle/closure-failures",
        }:
            try:
                if path.endswith("/closure-schema"):
                    self._write(HTTPStatus.OK, validation_design_closure_schema())
                    return
                if path.endswith("/schema"):
                    self._write(HTTPStatus.OK, validation_design_bundle_schema())
                    return
                query = parse_qs(parsed.query, keep_blank_values=False)
                bundle = build_validation_design_offline_bundle(
                    bundle_id=self._query_value(query, "bundle_id") or "validation-design-public-bundle",
                    run_id=self._query_value(query, "run_id") or "validation-design-bundle-runtime",
                )
                if path.endswith("/closure-query"):
                    payload = query_validation_design_closure(
                        bundle,
                        resource=self._query_value(query, "resource") or "artifacts",
                        operation=self._query_value(query, "operation"),
                        role=self._query_value(query, "role"),
                        state=self._query_value(query, "state"),
                        artifact_kind=self._query_value(query, "artifact_kind"),
                        plane_id=self._query_value(query, "plane_id"),
                        stage_id=self._query_value(query, "stage_id"),
                        issue_code=self._query_value(query, "issue_code"),
                        text=self._query_value(query, "q") or self._query_value(query, "text"),
                        offset=self._query_int(query, "offset", 0),
                        limit=self._query_int(query, "limit", 50),
                    ).to_dict()
                elif path.endswith("/query"):
                    payload = query_validation_design_offline_bundle(
                        bundle,
                        resource=self._query_value(query, "resource") or "artifacts",
                        operation=self._query_value(query, "operation"),
                        capability=self._query_value(query, "capability"),
                        role=self._query_value(query, "role"),
                        state=self._query_value(query, "state"),
                        artifact_kind=self._query_value(query, "artifact_kind"),
                        text=self._query_value(query, "q") or self._query_value(query, "text"),
                        offset=self._query_int(query, "offset", 0),
                        limit=self._query_int(query, "limit", 50),
                        include_payloads=self._query_bool(query, "include_payloads"),
                    ).to_dict()
                elif path.endswith("/audit"):
                    payload = audit_validation_design_offline_bundle(bundle).to_dict()
                elif path.endswith("/observability"):
                    payload = build_validation_design_bundle_observability(bundle).to_dict()
                elif path.endswith("/runtime"):
                    payload = run_validation_design_bundle_runtime(
                        bundle_id=bundle.bundle_id,
                        run_id=bundle.run_id,
                    ).to_dict()
                elif path.endswith("/boundary"):
                    payload = validate_validation_design_closure_boundary(bundle).to_dict()
                elif path.endswith("/indexes"):
                    indexes = build_validation_design_closure_indexes(bundle)
                    payload = {"indexes": indexes.to_dict(), "audit": audit_validation_design_closure_indexes(bundle, indexes).to_dict()}
                elif path.endswith("/reconciliation"):
                    payload = reconcile_validation_design_closure(bundle).to_dict()
                elif path.endswith("/summary"):
                    summary = build_validation_design_closure_summary(bundle)
                    payload = {"summary": summary.to_dict(), "audit": audit_validation_design_closure_summary(bundle, summary).to_dict()}
                elif path.endswith("/certification"):
                    payload = certify_validation_design_closure(bundle).to_dict()
                elif path.endswith("/closure-observability"):
                    payload = build_validation_design_closure_observability(bundle).to_dict()
                elif path.endswith("/closure-runtime"):
                    payload = run_validation_design_closure_runtime(
                        bundle_id=bundle.bundle_id,
                        run_id=self._query_value(query, "run_id") or "validation-design-closure-runtime",
                    ).to_dict()
                elif path.endswith("/closure-failures"):
                    payload = rehearse_validation_design_closure_failures(bundle).to_dict()
                else:
                    payload = bundle.to_dict(include_payloads=self._query_bool(query, "include_payloads"))
                self._write(HTTPStatus.OK, payload)
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path in {
            "/v1/evidence-lifecycle/bundle",
            "/v1/evidence-lifecycle/bundle/query",
            "/v1/evidence-lifecycle/bundle/schema",
            "/v1/evidence-lifecycle/bundle/audit",
            "/v1/evidence-lifecycle/bundle/observability",
            "/v1/evidence-lifecycle/bundle/runtime",
            "/v1/evidence-lifecycle/bundle/indexes",
            "/v1/evidence-lifecycle/bundle/boundary",
            "/v1/evidence-lifecycle/bundle/reconciliation",
            "/v1/evidence-lifecycle/bundle/summary",
            "/v1/evidence-lifecycle/bundle/closure-query",
            "/v1/evidence-lifecycle/bundle/closure-schema",
            "/v1/evidence-lifecycle/bundle/closure-boundary",
            "/v1/evidence-lifecycle/bundle/closure-indexes",
            "/v1/evidence-lifecycle/bundle/closure-reconciliation",
            "/v1/evidence-lifecycle/bundle/closure-summary",
            "/v1/evidence-lifecycle/bundle/closure-certification",
            "/v1/evidence-lifecycle/bundle/closure-observability",
            "/v1/evidence-lifecycle/bundle/closure-runtime",
            "/v1/evidence-lifecycle/bundle/closure-failures",
            "/v1/evidence-lifecycle/bundle/closure-graph",
        }:
            try:
                if path.endswith("/closure-schema"):
                    self._write(HTTPStatus.OK, evidence_lifecycle_closure_schema())
                    return
                if path.endswith("/schema"):
                    self._write(HTTPStatus.OK, evidence_lifecycle_offline_bundle_schema())
                    return
                query = parse_qs(parsed.query, keep_blank_values=False)
                bundle = build_evidence_lifecycle_offline_bundle(
                    bundle_id=self._query_value(query, "bundle_id") or "evidence-lifecycle-public-bundle",
                    run_id=self._query_value(query, "run_id") or "evidence-lifecycle-offline-runtime",
                )
                if path.endswith("/closure-query"):
                    payload = query_evidence_lifecycle_closure(
                        bundle,
                        resource=self._query_value(query, "resource") or "artifacts",
                        operation=self._query_value(query, "operation"),
                        role=self._query_value(query, "role"),
                        state=self._query_value(query, "state"),
                        artifact_kind=self._query_value(query, "artifact_kind"),
                        event_type=self._query_value(query, "event_type"),
                        disposition=self._query_value(query, "disposition"),
                        scenario_id=self._query_value(query, "scenario_id"),
                        text=self._query_value(query, "q") or self._query_value(query, "text"),
                        offset=self._query_int(query, "offset", 0),
                        limit=self._query_int(query, "limit", 50),
                    ).to_dict()
                elif path.endswith("/query"):
                    payload = query_evidence_lifecycle_offline_bundle(
                        bundle,
                        resource=self._query_value(query, "resource") or "artifacts",
                        operation=self._query_value(query, "operation"),
                        role=self._query_value(query, "role"),
                        state=self._query_value(query, "state"),
                        artifact_kind=self._query_value(query, "artifact_kind"),
                        text=self._query_value(query, "q") or self._query_value(query, "text"),
                        offset=self._query_int(query, "offset", 0),
                        limit=self._query_int(query, "limit", 50),
                        include_payloads=self._query_bool(query, "include_payloads"),
                    ).to_dict()
                elif path.endswith("/audit"):
                    payload = audit_evidence_lifecycle_offline_bundle(bundle).to_dict()
                elif path.endswith("/observability"):
                    payload = build_evidence_lifecycle_offline_observability(bundle).to_dict()
                elif path.endswith("/runtime"):
                    payload = run_evidence_lifecycle_offline_bundle_runtime(
                        bundle_id=bundle.bundle_id,
                        run_id=bundle.run_id,
                    ).to_dict()
                elif path.endswith("/indexes"):
                    catalog = build_evidence_lifecycle_offline_indexes(bundle)
                    payload = {"catalog": catalog.to_dict(), "audit": audit_evidence_lifecycle_offline_indexes(bundle, catalog).to_dict()}
                elif path.endswith("/boundary"):
                    payload = audit_evidence_lifecycle_offline_boundary(bundle).to_dict()
                elif path.endswith("/reconciliation"):
                    payload = reconcile_evidence_lifecycle_offline_bundle(bundle).to_dict()
                elif path.endswith("/summary"):
                    summary = build_evidence_lifecycle_offline_summary(bundle)
                    payload = {"summary": summary.to_dict(), "audit": audit_evidence_lifecycle_offline_summary(summary).to_dict()}
                elif path.endswith("/closure-boundary"):
                    payload = audit_evidence_lifecycle_closure_boundary(bundle).to_dict()
                elif path.endswith("/closure-indexes"):
                    indexes = build_evidence_lifecycle_closure_indexes(bundle)
                    payload = {"indexes": indexes.to_dict(), "audit": audit_evidence_lifecycle_closure_indexes(bundle, indexes).to_dict()}
                elif path.endswith("/closure-reconciliation"):
                    payload = reconcile_evidence_lifecycle_closure(bundle).to_dict()
                elif path.endswith("/closure-summary"):
                    summary = build_evidence_lifecycle_closure_summary(bundle)
                    payload = {"summary": summary.to_dict(), "audit": audit_evidence_lifecycle_closure_summary(summary).to_dict()}
                elif path.endswith("/closure-certification"):
                    payload = certify_evidence_lifecycle_closure(bundle).to_dict()
                elif path.endswith("/closure-observability"):
                    payload = build_evidence_lifecycle_closure_observability(bundle).to_dict()
                elif path.endswith("/closure-runtime"):
                    payload = run_evidence_lifecycle_closure_runtime(
                        bundle_id=bundle.bundle_id,
                        run_id=self._query_value(query, "run_id") or "evidence-lifecycle-closure-runtime",
                    ).to_dict()
                elif path.endswith("/closure-failures"):
                    payload = run_evidence_lifecycle_closure_failure_injection(bundle).to_dict()
                elif path.endswith("/closure-graph"):
                    payload = build_evidence_lifecycle_closure_graph(bundle).to_dict()
                else:
                    payload = bundle.to_dict(include_payloads=self._query_bool(query, "include_payloads"))
                self._write(HTTPStatus.OK, payload)
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path in {
            "/v1/portfolio/release",
            "/v1/portfolio/release/lineage",
            "/v1/portfolio/release/observability",
            "/v1/portfolio/release/schema",
        }:
            try:
                if path.endswith("/schema"):
                    self._write(HTTPStatus.OK, portfolio_release_schema())
                    return
                query = parse_qs(parsed.query, keep_blank_values=False)
                bundle = build_portfolio_release(
                    self._runtime(),
                    run_ids=self._query_values(query, "run_id"),
                    case_id=self._query_value(query, "case_id"),
                    status=self._query_value(query, "status"),
                    reviewer=self._query_value(query, "reviewer"),
                    due_state=self._query_value(query, "due_state"),
                    release_state=self._query_value(query, "release_state"),
                    text=self._query_value(query, "q") or self._query_value(query, "text"),
                    release_ready_only=self._query_bool(query, "release_ready_only"),
                    include_blocked=self._query_bool(query, "include_blocked")
                    if "include_blocked" in query
                    else True,
                    as_of=self._query_value(query, "as_of"),
                    due_soon_hours=self._query_int(query, "due_soon_hours", 72),
                    max_runs=self._query_int(query, "max_runs", 25),
                )
                if path.endswith("/lineage"):
                    lineage = build_portfolio_release_lineage(
                        bundle,
                        run_id=self._query_value(query, "focus_run_id"),
                    )
                    payload = lineage.to_dict()
                    if self._query_value(query, "focus_run_id"):
                        payload = lineage_for_run(lineage, self._query_value(query, "focus_run_id") or "")
                elif path.endswith("/observability"):
                    payload = build_portfolio_release_observability(bundle).to_dict()
                else:
                    payload = bundle.to_dict(include_payloads=self._query_bool(query, "include_payloads"))
                self._write(HTTPStatus.OK, payload)
            except StoreError:
                self._write(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": "run not found"})
            except GlioError as exc:
                self._write(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.code, "message": str(exc)})
            except ValueError as exc:
                self._write(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "message": str(exc)})
            except Exception as exc:  # pragma: no cover - last-resort process boundary
                self._write(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})
            return
        if path == "/v1/portfolio" or path == "/v1/portfolio/closure":
            try:
                query = parse_qs(parsed.query, keep_blank_values=False)
                as_of = self._query_value(query, "as_of")
                due_soon_hours = self._query_int(query, "due_soon_hours", 48)
                if path.endswith("/closure"):
                    self._write(
                        HTTPStatus.OK,
                        build_run_portfolio_closure(
                            self._runtime(),
                            as_of=as_of,
                            due_soon_hours=due_soon_hours,
                        ),
                    )
                    return
                page = build_run_portfolio(
                    self._runtime(),
                    case_id=self._query_value(query, "case_id"),
                    status=self._query_value(query, "status"),
                    reviewer=self._query_value(query, "reviewer"),
                    due_state=self._query_value(query, "due_state"),
                    release_state=self._query_value(query, "release_state"),
                    text=self._query_value(query, "q") or self._query_value(query, "text"),
                    release_ready_only=self._query_bool(query, "release_ready_only"),
                    as_of=as_of,
                    due_soon_hours=due_soon_hours,
                    offset=self._query_int(query, "offset", 0),
                    limit=self._query_int(query, "limit", RUN_PORTFOLIO_DEFAULT_LIMIT),
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
