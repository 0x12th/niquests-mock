# Compatibility Notes

`niquests-mock` is RESPX-like for common pytest workflows, but it is not a full RESPX
clone. This package targets `niquests`, not `httpx`.

## Supported workflows

The following workflows are part of the intended public contract:

- pytest fixture style via `niquests_mock`;
- `respx_mock` fixture alias for easier migration from RESPX-shaped tests;
- decorator style via `@niquests_mock.mock`;
- context-manager style via `MockRouter`;
- named routes and `lookup()`;
- sync and async `niquests` requests;
- strict unmatched-request failures via `NoMockAddress`;
- route-level pass-through;
- exact URL matching and fallback pattern matching;
- method, URL, scheme, host, path, headers, query params, content, and JSON matchers;
- route call assertions and router `assert_all_called`.

## Explicit non-goals for now

Unsupported RESPX behavior should be treated as out of contract unless it is documented
in `README.md`, documented here, or covered by tests.

Current non-goals:

- full RESPX API parity;
- `httpx` transport mocking;
- automatic propagation of active routers into newly created threads;
- advanced route indexing for very large fallback route sets;
- a plugin system for custom matcher classes;
- stable internals for `MockRouter` patch lifecycle or route storage;
- supporting `niquests` versions below the package requirement in `pyproject.toml`.

## Matching behavior

Within one active router:

1. Exact `method + URL` routes are checked first.
2. If multiple exact routes share the same key, the most recently registered route wins.
3. Non-exact routes are checked in reverse registration order.
4. Exact-route precedence is higher than fallback route recency.
5. If no route matches, strict mode raises `NoMockAddress`; non-strict mode uses the
   original `niquests` transport.

## Concurrency behavior

The active router is stored in a Python `ContextVar`.

- Async tasks created inside an active router context inherit that context.
- Nested routers use the innermost active router for the current context.
- New threads do not inherit the active router automatically.
- The underlying `niquests` send methods are patched process-wide only while routers
  are active, but route selection remains context-dependent.

## Upstream `niquests` contract

`niquests-mock` patches `niquests.sessions.Session.send` and
`niquests.async_session.AsyncSession.send`. Compatibility depends on those methods
continuing to accept a prepared request and keyword arguments in the shape used by
current supported `niquests` versions.

Regression tests cover sync and async delegation to the original send methods for
pass-through and unmatched requests. If `niquests` changes its send contract, update the
compatibility tests before changing the implementation.
