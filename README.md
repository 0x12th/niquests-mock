# niquests-mock

[![CI](https://github.com/0x12th/niquests-mock/actions/workflows/ci.yml/badge.svg)](https://github.com/0x12th/niquests-mock/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/niquests-mock.svg)](https://pypi.org/project/niquests-mock/)
[![Python](https://img.shields.io/pypi/pyversions/niquests-mock.svg)](https://pypi.org/project/niquests-mock/)
[![License](https://img.shields.io/github/license/0x12th/niquests-mock.svg)](LICENSE)

RESPX-style HTTP mocking for [niquests](https://pypi.org/project/niquests/).

## Installation

```bash
uv add niquests-mock
```

or

```bash
pip install niquests-mock
```

## Usage

### Fixture Style

This is the closest workflow to `respx_mock` in pytest.

```python
import niquests


def test_fixture_style(niquests_mock):
    route = niquests_mock.get("https://example.org/")
    route.respond(status_code=200)

    response = niquests.get("https://example.org/")

    assert route.called
    assert response.status_code == 200
```

The plugin also exposes `respx_mock` as a compatibility alias for easier migration from `respx`.

## Development

```bash
uv sync --dev
just check
```

### Decorator Style

Useful when you want a familiar `respx`-style test shape.

```python
import niquests
import niquests_mock as nmock


@nmock.mock
def test_decorator_style():
    route = nmock.get("https://example.org/", name="homepage").respond(status_code=200)
    response = niquests.get("https://example.org/")

    route.assert_called_once()
    assert nmock.lookup("homepage") is route
    assert response.status_code == 200
```

Decorator factory arguments work too:

```python
import niquests
import niquests_mock as nmock


@nmock.mock(assert_all_called=True, base_url="https://api.example.test")
def test_strict_routes():
    nmock.get("/health", name="health").respond(status_code=200)

    response = niquests.get("https://api.example.test/health")

    assert response.status_code == 200
```

Decorator calls use a fresh router for every decorated function invocation. The
fresh router copies router configuration such as `assert_all_mocked`,
`assert_all_called`, and `base_url`, but it does not reuse routes registered on
the decorator object itself. Register routes inside the decorated function via
`nmock.get(...)`, `nmock.route(...)`, or other top-level helpers.

### Context Manager Style

Best when you want explicit router lifetime inside the test body.

```python
import niquests
from niquests_mock import MockRouter


def test_context_manager():
    with MockRouter(base_url="https://api.example.test") as router:
        users = router.get("/users", name="users.list").respond(
            status_code=200,
            json=[{"id": 1, "name": "Ada"}],
        )

        response = niquests.get("https://api.example.test/users")

    assert router["users.list"] is users
    users.assert_called_once()
    assert response.json() == [{"id": 1, "name": "Ada"}]
```

`MockRouter` can be nested. The innermost active router handles requests while it
is active, and the outer router is restored after the inner context exits. Patch
cleanup runs when a context exits, including when the test body raises an
exception. Repeated `start()` / `stop()` calls on the same router are idempotent.

### Strict Mode and Pass-through

By default, `assert_all_mocked=True`: unmatched requests raise `NoMockAddress`.
Set `assert_all_mocked=False` to allow unmatched requests to use the original
`niquests` transport.

A route can opt into pass-through even in strict mode. The request then uses the
original `niquests` transport, so use this only for URLs that your test
environment intentionally allows:

```python
with MockRouter(assert_all_mocked=True) as router:
    router.get(live_url).pass_through()
    response = niquests.get(live_url)
```

Use `assert_all_called=True` when every registered route must be exercised. On a
normal router exit, unused routes raise `AllMockedAssertionError`. If the test
body already raised another exception, `assert_all_called` is skipped so the
original error is preserved.

### Pytest Marker Configuration

The pytest plugin accepts these marker keyword arguments:

- `assert_all_mocked`
- `assert_all_called`
- `base_url`

Unknown marker keyword arguments raise `pytest.UsageError` so typos fail early.

### Matching Order and Precedence

Routes are matched by the active router only. Nested routers use the innermost
active router first; outer routers are restored when inner contexts exit.

Within one router:

1. Exact `method + URL` routes are checked first.
2. If multiple exact routes share the same key, the most recently registered
   route wins.
3. Non-exact routes, including regex/callable/pattern routes, are checked in
   reverse registration order. Exact-route precedence is higher than fallback
   route recency.
4. If no route matches, `assert_all_mocked=True` raises `NoMockAddress`; with
   `assert_all_mocked=False`, the request uses the original `niquests` transport.

Diagnostics intentionally show request method/URL and route summaries, but avoid
printing header values or body contents by default.

### Side Effects

Use `side_effect` when a route needs custom logic. The callable receives the
`niquests.models.PreparedRequest` and must return a `niquests.Response` or raise
an exception.

```python
import niquests
from niquests_mock import MockRouter, build_response


with MockRouter() as router:
    def create_job(request):
        return build_response(request, status_code=201, json={"id": 1})

    router.post("https://api.example.test/jobs").mock(side_effect=create_job)

    response = niquests.post("https://api.example.test/jobs", json={"name": "build"})
```

Exceptions are recorded on `Call.exception` before being re-raised.

```python
with MockRouter() as router:
    route = router.get("https://api.example.test/fails").mock(
        side_effect=RuntimeError("boom"),
    )
```

For async requests, side effects may be `async def` callables or return awaitables.

```python
import niquests
from niquests_mock import MockRouter, build_response


async def test_async_side_effect():
    async with MockRouter() as router:
        async def get_status(request):
            return build_response(request, status_code=200, json={"ok": True})

        router.get("https://api.example.test/status").mock(side_effect=get_status)
        response = await niquests.arequest("GET", "https://api.example.test/status")

    assert response.json() == {"ok": True}
```

### Async Usage

`MockRouter` supports async context-manager use and patches `niquests` async
send calls for the active context.

```python
async def test_async_context_manager():
    async with MockRouter(base_url="https://api.example.test") as router:
        router.get("/health").respond(json={"ok": True})
        response = await niquests.arequest("GET", "https://api.example.test/health")

    assert response.json() == {"ok": True}
```

### Concurrency Notes

The active router is stored in a Python `ContextVar`.

- Async tasks created inside an active `MockRouter` context inherit that active router
  context and can use the same registered routes.
- Nested routers are task-local: the innermost active router handles requests for the
  current context, then the previous router is restored when the inner context exits.
- New threads do not automatically inherit the active router context. If code under
  test performs HTTP calls in another thread, create or start a `MockRouter` in that
  thread, or explicitly propagate the Python context yourself.
- The `niquests` send methods are patched process-wide while at least one router is
  active, but route selection still depends on the current context. A patched send
  call with no active router in its context falls back to the original transport.

### Compatibility Notes vs RESPX

`niquests-mock` is RESPX-like for common pytest workflows, but it is not a full RESPX
clone. This package targets `niquests`, not `httpx`.

Supported workflows:

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

Unsupported RESPX behavior should be treated as out of contract unless it is documented
in this README or covered by tests.

Current non-goals:

- full RESPX API parity;
- `httpx` transport mocking;
- automatic propagation of active routers into newly created threads;
- advanced route indexing for very large fallback route sets;
- a plugin system for custom matcher classes;
- stable internals for `MockRouter` patch lifecycle or route storage;
- supporting `niquests` versions below the package requirement in `pyproject.toml`.

`niquests-mock` patches `niquests.sessions.Session.send` and
`niquests.async_session.AsyncSession.send`. Compatibility depends on those methods
continuing to accept a prepared request and keyword arguments in the shape used by
current supported `niquests` versions. Regression tests cover sync and async delegation
to the original send methods for pass-through and unmatched requests.
