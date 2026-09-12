from __future__ import annotations

import builtins
import contextvars
import unittest
from contextlib import ExitStack
from types import FunctionType

import glio_noncode._callback_isolation as callback_isolation_module
from glio_noncode._callback_isolation import (
    atlas_callback_scope,
    detached_callback_guard,
    runtime_callback_scope,
    source_callback_scope,
    source_manifest_callback_scope,
)
from glio_noncode.errors import ValidationError


class CallbackIsolationTests(unittest.TestCase):
    def test_detached_guard_has_stable_globals_and_builtins(self) -> None:
        expected_dependency = object()
        replacement_dependency = object()
        builtin_namespace = dict(vars(builtins))

        def template():
            return dict(value=detached_dependency)  # type: ignore[name-defined]  # noqa: F821

        live_globals = {
            "__builtins__": builtin_namespace,
            "detached_dependency": expected_dependency,
        }
        live_function = FunctionType(template.__code__, live_globals)
        detached = detached_callback_guard(live_function)

        live_globals["detached_dependency"] = replacement_dependency
        live_globals["dict"] = None
        builtin_namespace["dict"] = None

        self.assertEqual(detached(), {"value": expected_dependency})

    def test_scope_exit_survives_callback_module_builtin_shadows(self) -> None:
        namespace = vars(callback_isolation_module)
        names = ("dict", "Exception", "len", "str", "tuple", "type", "vars")
        missing = object()
        originals = {name: namespace.get(name, missing) for name in names}
        try:
            with runtime_callback_scope():
                namespace.update(dict.fromkeys(names))
            with runtime_callback_scope():
                pass
        finally:
            for name, original in originals.items():
                if original is missing:
                    namespace.pop(name, None)
                else:
                    namespace[name] = original

    def test_exact_transition_table(self) -> None:
        scopes = {
            "runtime": runtime_callback_scope,
            "atlas": atlas_callback_scope,
            "source_manifest": source_manifest_callback_scope,
            "source": source_callback_scope,
        }
        valid_stacks = (
            (),
            ("runtime",),
            ("atlas",),
            ("source_manifest",),
            ("source",),
            ("runtime", "atlas"),
            ("runtime", "source_manifest"),
            ("runtime", "source"),
            ("atlas", "source"),
            ("source_manifest", "source"),
            ("runtime", "atlas", "source"),
            ("runtime", "source_manifest", "source"),
        )
        allowed_entries = {
            ("runtime", ()),
            ("atlas", ()),
            ("atlas", ("runtime",)),
            ("source_manifest", ()),
            ("source_manifest", ("runtime",)),
            ("source", ()),
            ("source", ("runtime",)),
            ("source", ("atlas",)),
            ("source", ("runtime", "atlas")),
            ("source", ("source_manifest",)),
            ("source", ("runtime", "source_manifest")),
        }
        messages = {
            "runtime": "recursive runtime evaluation",
            "atlas": "nested atlas retrieval",
            "source_manifest": "nested public reference enrichment",
            "source": "nested public reference retrieval",
        }

        for stack in valid_stacks:
            for boundary, scope in scopes.items():
                with self.subTest(stack=stack, boundary=boundary), ExitStack() as entered:
                    for active in stack:
                        entered.enter_context(scopes[active]())
                    if (boundary, stack) in allowed_entries:
                        entered.enter_context(scope())
                    else:
                        with self.assertRaisesRegex(ValidationError, messages[boundary]):
                            with scope():
                                pass

    def test_fresh_context_cannot_hide_same_thread_outer_scope(self) -> None:
        nested_errors: list[ValidationError] = []

        def enter_runtime_again() -> None:
            try:
                with runtime_callback_scope():
                    pass
            except ValidationError as exc:
                nested_errors.append(exc)

        with runtime_callback_scope():
            contextvars.Context().run(enter_runtime_again)

        self.assertEqual(len(nested_errors), 1)
        self.assertRegex(str(nested_errors[0]), "recursive runtime evaluation")
        with runtime_callback_scope():
            pass

    def test_exception_exit_restores_a_clean_stack(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "callback failed"):
            with atlas_callback_scope(), source_callback_scope():
                raise RuntimeError("callback failed")

        with runtime_callback_scope(), source_manifest_callback_scope():
            with source_callback_scope():
                pass


if __name__ == "__main__":
    unittest.main()
