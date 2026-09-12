"""Process-local isolation for callback-driven semantic guard boundaries.

Runtime evaluation composes Atlas retrieval, and Atlas retrieval can compose
public-source retrieval. Those boundaries snapshot package-level executable
state while user-provided callbacks run, so independent locks would permit one
boundary to capture another boundary's transient mutation (and would introduce
cross-module lock-order inversions).

The active stack is thread-local rather than context-local.  A callback may run
code in a fresh :mod:`contextvars` context on the same thread, and that must not
erase an outer boundary.  Two independent thread-local stores carry the same
immutable marker and are checked at entry and exit so one-sided state drift
fails closed.  The stores and immutable policy remain closure-held to avoid
publishing a normal package-level mutation surface.

This coordinator is an in-process integrity mechanism, not a sandbox against
code that deliberately traverses private function closures or manipulates the
interpreter/native process.  Fully hostile extensions require process isolation.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from threading import RLock, local
from types import FunctionType, ModuleType
from typing import Any, Literal, cast

from .errors import ValidationError

CallbackBoundary = Literal["runtime", "atlas", "source_manifest", "source"]
CallbackStack = tuple[CallbackBoundary, ...]
CallbackState = tuple[object, CallbackStack]


CallbackScope = Callable[[], AbstractContextManager[None]]


def detached_callback_guard(function: Callable[..., Any]) -> Callable[..., Any]:
    """Clone a guard with invocation-stable globals and builtins.

    Semantic guard and restoration functions run after an untrusted callback.
    A callback may add package-module globals whose names shadow builtins (for
    example, ``dict`` or ``Exception``), or rebind another dependency used by
    the cleanup path.  A normal function continues to resolve those names in
    its live module dictionary, which can prevent the guard from restoring the
    mutation it was meant to detect.

    The clone retains the original closure objects, but resolves globals from a
    shallow snapshot and builtins from an independent dictionary.  Referenced
    mutable objects intentionally retain identity: the surrounding semantic
    guard is responsible for detecting and restoring their in-place mutation.
    This is an in-process integrity boundary, not protection against code that
    deliberately traverses private frames or closure cells.
    """

    error_type = ValidationError
    if type(function) is not FunctionType:
        raise error_type("callback guard must be an exact Python function")
    selected = cast(FunctionType, function)
    function_globals = selected.__globals__
    if type(function_globals) is not dict:
        raise error_type("callback guard globals are invalid")
    raw_builtins = function_globals.get("__builtins__")
    if type(raw_builtins) is dict:
        detached_builtins = dict(raw_builtins)
    elif type(raw_builtins) is ModuleType:
        detached_builtins = dict(vars(raw_builtins))
    else:
        raise error_type("callback guard builtins are invalid")
    detached_globals = dict(function_globals)
    detached_globals["__builtins__"] = detached_builtins
    clone = FunctionType(
        selected.__code__,
        detached_globals,
        selected.__name__,
        selected.__defaults__,
        selected.__closure__,
    )
    kwdefaults = selected.__kwdefaults__
    if kwdefaults is not None and type(kwdefaults) is not dict:
        raise error_type("callback guard keyword defaults are invalid")
    annotations = selected.__annotations__
    function_namespace = vars(selected)
    if type(annotations) is not dict or type(function_namespace) is not dict:
        raise error_type("callback guard function metadata is invalid")
    clone.__kwdefaults__ = None if kwdefaults is None else dict(kwdefaults)
    clone.__annotations__ = dict(annotations)
    clone.__dict__.update(dict(function_namespace))
    clone.__qualname__ = selected.__qualname__
    clone.__module__ = selected.__module__
    clone.__doc__ = selected.__doc__
    return clone


def _build_callback_isolation() -> tuple[
    CallbackScope,
    CallbackScope,
    CallbackScope,
    CallbackScope,
]:
    error_type = ValidationError
    exact_type = type
    exact_str_type = str
    exact_dict_type = dict
    exact_tuple_type = tuple
    value_len = len
    value_vars = vars
    exception_type = Exception
    lock = RLock()
    primary_state = local()
    witness_state = local()
    local_type = type(primary_state)
    state_key = "callback_state"
    state_sentinel = object()
    valid_boundaries = frozenset({"runtime", "atlas", "source_manifest", "source"})
    valid_stacks: frozenset[CallbackStack] = frozenset(
        {
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
        }
    )
    allowed_entries: frozenset[tuple[CallbackBoundary, CallbackStack]] = frozenset(
        {
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
    )
    nested_messages: tuple[tuple[CallbackBoundary, str], ...] = (
        ("runtime", "recursive runtime evaluation is not supported"),
        ("atlas", "nested atlas retrieval is not allowed"),
        ("source_manifest", "nested public reference enrichment is not allowed"),
        ("source", "nested public reference retrieval is not allowed"),
    )

    def state_namespace(store: object) -> dict[str, object]:
        if exact_type(store) is not local_type:
            raise error_type("callback isolation state store is invalid")
        namespace = value_vars(store)
        if exact_type(namespace) is not exact_dict_type:
            raise error_type("callback isolation state store is invalid")
        return namespace

    def read_state(namespace: dict[str, object]) -> CallbackState | None:
        if not namespace:
            return None
        if exact_tuple_type(namespace) != (state_key,):
            raise error_type("callback isolation state is invalid")
        state = namespace[state_key]
        if exact_type(state) is not exact_tuple_type:
            raise error_type("callback isolation state is invalid")
        tuple_state: tuple[object, ...] = state  # type: ignore[assignment]
        if (
            value_len(tuple_state) != 2
            or tuple_state[0] is not state_sentinel
            or exact_type(tuple_state[1]) is not exact_tuple_type
            or tuple_state[1] not in valid_stacks
        ):
            raise error_type("callback isolation state is invalid")
        return tuple_state  # type: ignore[return-value]

    def restore_state(
        namespace: dict[str, object],
        state: CallbackState | None,
    ) -> None:
        namespace.clear()
        if state is not None:
            namespace[state_key] = state

    def nested_message(boundary: CallbackBoundary) -> str:
        for candidate, message in nested_messages:
            if candidate == boundary:
                return message
        raise error_type("callback isolation boundary is invalid")

    @contextmanager
    def isolation_scope(boundary: CallbackBoundary) -> Iterator[None]:
        if exact_type(boundary) is not exact_str_type or boundary not in valid_boundaries:
            raise error_type("callback isolation boundary is invalid")
        selected: CallbackBoundary = boundary  # type: ignore[assignment]
        with lock:
            primary_namespace = state_namespace(primary_state)
            witness_namespace = state_namespace(witness_state)
            previous_state = read_state(primary_namespace)
            if read_state(witness_namespace) is not previous_state:
                raise error_type("callback isolation state witnesses disagree")
            stack: CallbackStack = () if previous_state is None else previous_state[1]
            if (selected, stack) not in allowed_entries:
                raise error_type(nested_message(selected))
            entered_state: CallbackState = (state_sentinel, (*stack, selected))
            primary_namespace[state_key] = entered_state
            witness_namespace[state_key] = entered_state
            try:
                yield
            finally:
                state_drifted = False
                try:
                    state_drifted = (
                        read_state(primary_namespace) is not entered_state
                        or read_state(witness_namespace) is not entered_state
                    )
                except exception_type:  # noqa: BLE001 - corrupted callback-visible state
                    state_drifted = True
                restore_state(primary_namespace, previous_state)
                restore_state(witness_namespace, previous_state)
                if state_drifted:
                    raise error_type("callback isolation state was mutated")

    @contextmanager
    def runtime_scope() -> Iterator[None]:
        with isolation_scope("runtime"):
            yield

    @contextmanager
    def atlas_scope() -> Iterator[None]:
        with isolation_scope("atlas"):
            yield

    @contextmanager
    def source_manifest_scope() -> Iterator[None]:
        with isolation_scope("source_manifest"):
            yield

    @contextmanager
    def source_scope() -> Iterator[None]:
        with isolation_scope("source"):
            yield

    return runtime_scope, atlas_scope, source_manifest_scope, source_scope


(
    runtime_callback_scope,
    atlas_callback_scope,
    source_manifest_callback_scope,
    source_callback_scope,
) = _build_callback_isolation()
del _build_callback_isolation
