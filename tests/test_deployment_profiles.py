"""Deep contract coverage for authenticated deployment boundaries."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.deployment_profiles import (
    DEPLOYMENT_PROFILE_VERSION,
    DeploymentAuthentication,
    DeploymentDecision,
    DeploymentExposure,
    DeploymentGuard,
    build_deployment_principal,
    build_deployment_profile,
    deployment_audit_csv,
    deployment_audit_log_from_dict,
    deployment_audit_markdown,
    deployment_profile_from_dict,
    deployment_profile_schema,
    verify_deployment_audit_log,
)
from glio_noncode.errors import ValidationError


class DeploymentProfileTests(unittest.TestCase):
    def _profile(self, *, rate_limit: int = 60):
        principal = build_deployment_principal(
            "operator-1",
            role="operator",
            scopes=("read", "write", "review", "audit"),
        )
        return build_deployment_profile(
            profile_id="institutional-test",
            host="10.0.0.12",
            exposure=DeploymentExposure.PRIVATE_NETWORK,
            authentication=DeploymentAuthentication.API_KEY,
            tls_required=True,
            rate_limit_per_minute=rate_limit,
            principals=(principal,),
        )

    def test_loopback_default_is_accepted_and_non_loopback_defaults_fail_closed(self) -> None:
        local = build_deployment_profile()
        self.assertTrue(local.accepted)
        self.assertEqual(local.authentication, DeploymentAuthentication.NONE)
        self.assertEqual(local.exposure, DeploymentExposure.LOOPBACK)
        with self.assertRaises(ValidationError):
            build_deployment_profile(host="10.0.0.12")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValidationError):
                create_server("0.0.0.0", 0, directory)

    def test_non_loopback_profile_requires_all_boundary_controls(self) -> None:
        principal = build_deployment_principal("operator-1")
        with self.assertRaises(ValidationError):
            build_deployment_profile(
                host="10.0.0.12",
                exposure=DeploymentExposure.PRIVATE_NETWORK,
                authentication=DeploymentAuthentication.API_KEY,
                tls_required=False,
                principals=(principal,),
            )
        with self.assertRaises(ValidationError):
            build_deployment_profile(
                host="10.0.0.12",
                exposure=DeploymentExposure.PRIVATE_NETWORK,
                authentication=DeploymentAuthentication.NONE,
                tls_required=True,
                principals=(principal,),
            )

    def test_profile_round_trip_and_schema_are_addressed(self) -> None:
        profile = self._profile()
        reopened = deployment_profile_from_dict(profile.to_dict())
        self.assertEqual(reopened, profile)
        self.assertEqual(profile.version, DEPLOYMENT_PROFILE_VERSION)
        schema = deployment_profile_schema()
        self.assertEqual(schema["properties"]["version"]["const"], DEPLOYMENT_PROFILE_VERSION)
        encoded = json.dumps(profile.to_dict(), sort_keys=True)
        self.assertNotIn("credential_value", encoded)
        self.assertNotIn("secret-key", encoded)

    def test_guard_authenticates_scopes_and_never_exports_credentials(self) -> None:
        profile = self._profile()
        guard = DeploymentGuard(profile, {"operator-1": "a-random-secret-key-12345"})
        observed = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        allowed = guard.authorize("GET", "/v1/status", token="a-random-secret-key-12345", observed_at=observed)
        denied = guard.authorize("GET", "/v1/status", token="wrong-secret-key-12345", observed_at=observed)
        self.assertEqual(allowed.decision, DeploymentDecision.ALLOWED)
        self.assertEqual(denied.decision, DeploymentDecision.DENIED)
        self.assertEqual(denied.reason, "missing_or_invalid_credential")
        payload = json.dumps(guard.audit_log.to_dict(), sort_keys=True)
        self.assertNotIn("a-random-secret-key-12345", payload)
        self.assertNotIn("wrong-secret-key-12345", payload)
        self.assertEqual(verify_deployment_audit_log(guard.audit_log), ())

    def test_rate_limit_is_deterministic_and_audited(self) -> None:
        guard = DeploymentGuard(self._profile(rate_limit=2), {"operator-1": "a-random-secret-key-12345"})
        observed = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        decisions = tuple(
            guard.authorize("GET", "/v1/status", token="a-random-secret-key-12345", observed_at=observed)
            for _ in range(3)
        )
        self.assertEqual(tuple(item.decision for item in decisions), (
            DeploymentDecision.ALLOWED,
            DeploymentDecision.ALLOWED,
            DeploymentDecision.DENIED,
        ))
        self.assertEqual(decisions[-1].reason, "rate_limit_exceeded")
        self.assertEqual(guard.audit_log.denied_count, 1)

    def test_scope_denial_distinguishes_authenticated_principal(self) -> None:
        principal = build_deployment_principal("reader-1", role="auditor", scopes=("read",))
        profile = build_deployment_profile(
            profile_id="reader-profile",
            host="10.0.0.12",
            exposure=DeploymentExposure.PRIVATE_NETWORK,
            authentication=DeploymentAuthentication.API_KEY,
            tls_required=True,
            principals=(principal,),
        )
        guard = DeploymentGuard(profile, {"reader-1": "a-random-secret-key-12345"})
        decision = guard.authorize(
            "POST",
            "/v1/evaluate",
            token="a-random-secret-key-12345",
            observed_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
        )
        self.assertEqual(decision.decision, DeploymentDecision.DENIED)
        self.assertEqual(decision.reason, "scope_denied")
        self.assertEqual(decision.principal_id, "reader-1")

    def test_audit_exports_round_trip_and_detect_tampering(self) -> None:
        guard = DeploymentGuard(self._profile(), {"operator-1": "a-random-secret-key-12345"})
        guard.authorize("GET", "/v1/status", token="a-random-secret-key-12345", observed_at=datetime(2026, 8, 25, tzinfo=timezone.utc))
        log = guard.audit_log
        reopened = deployment_audit_log_from_dict(log.to_dict())
        self.assertEqual(reopened, log)
        self.assertIn("sequence", deployment_audit_csv(log).splitlines()[0])
        self.assertIn("# Deployment Audit", deployment_audit_markdown(log))
        tampered = dict(log.to_dict())
        tampered["events"][0]["reason"] = "credential=leaked"
        with self.assertRaises(ValidationError):
            deployment_audit_log_from_dict(tampered)

    def test_api_enforces_profile_and_exposes_redacted_audit(self) -> None:
        profile = self._profile()
        with tempfile.TemporaryDirectory() as directory:
            server = create_server(
                "127.0.0.1",
                0,
                directory,
                deployment_profile=profile,
                credentials={"operator-1": "a-random-secret-key-12345"},
            )
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=60)
                connection.request("GET", "/v1/status")
                response = connection.getresponse()
                self.assertEqual(response.status, 401)
                self.assertEqual(response.getheader("WWW-Authenticate"), "Bearer")
                response.read()
                connection.request(
                    "GET",
                    "/v1/status",
                    headers={"Authorization": "Bearer a-random-secret-key-12345"},
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                response.read()
                connection.request("GET", "/v1/deployment/profile")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                profile_payload = json.loads(response.read())
                self.assertEqual(profile_payload["profile_id"], profile.profile_id)
                connection.request(
                    "GET",
                    "/v1/deployment/audit",
                    headers={"Authorization": "Bearer a-random-secret-key-12345"},
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                audit_payload = json.loads(response.read())
                self.assertGreaterEqual(audit_payload["event_count"], 3)
                self.assertNotIn("a-random-secret-key-12345", json.dumps(audit_payload))
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_cli_profile_and_audit_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile_path = Path(directory) / "profile.json"
            self.assertEqual(
                main(
                    [
                        "deployment-profile",
                        "--profile-id",
                        "cli-profile",
                        "--host",
                        "10.0.0.12",
                        "--exposure",
                        "private_network",
                        "--authentication",
                        "api_key",
                        "--principal-id",
                        "operator-1",
                        "--tls-required",
                        "--output",
                        str(profile_path),
                    ]
                ),
                0,
            )
            self.assertEqual(json.loads(profile_path.read_text(encoding="utf-8"))["profile_id"], "cli-profile")
            audit_path = Path(directory) / "audit.json"
            profile = build_deployment_profile()
            guard = DeploymentGuard(profile)
            audit_path.write_text(json.dumps(guard.audit_log.to_dict()), encoding="utf-8")
            output = Path(directory) / "audit.md"
            self.assertEqual(
                main(["deployment-audit", str(audit_path), "--format", "markdown", "--output", str(output)]),
                0,
            )
            self.assertIn("# Deployment Audit", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
