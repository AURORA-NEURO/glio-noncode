from __future__ import annotations

import unittest

from glio_noncode.adapters import AdapterMetadata, AdapterRegistry, StaticElementAdapter
from glio_noncode.monitoring import MonitorRegistry, SignalStatus

from .helpers import fixture_manifest


class AdapterMonitoringTests(unittest.TestCase):
    def test_registry_requires_unique_metadata(self) -> None:
        manifest = fixture_manifest()
        metadata = AdapterMetadata(
            adapter_id="fixture",
            display_name="Fixture source",
            version="0.1",
            license="MIT",
            data_access="synthetic",
            supported_contexts=(manifest.context.key,),
            channels=("accessibility",),
            failure_modes=("missing_context",),
        )
        registry = AdapterRegistry()
        registry.register(StaticElementAdapter(metadata, manifest.candidate_elements))
        with self.assertRaises(Exception):
            registry.register(StaticElementAdapter(metadata, manifest.candidate_elements))
        self.assertEqual(registry.health()["count"], 1)

    def test_monitoring_classifies_watch_and_alert(self) -> None:
        registry = MonitorRegistry()
        watch = registry.observe("abstention_fraction", 0.3)
        alert = registry.observe("abstention_fraction", 0.8)
        unknown = registry.observe("abstention_fraction", None)
        self.assertEqual(watch.status, SignalStatus.WATCH)
        self.assertEqual(alert.status, SignalStatus.ALERT)
        self.assertEqual(unknown.status, SignalStatus.UNKNOWN)
