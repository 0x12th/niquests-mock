# niquests-mock

[![CI](https://github.com/0x12th/niquests-mock/actions/workflows/ci.yml/badge.svg)](https://github.com/0x12th/niquests-mock/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/niquests-mock.svg)](https://pypi.org/project/niquests-mock/)
[![Python](https://img.shields.io/pypi/pyversions/niquests-mock.svg)](https://pypi.org/project/niquests-mock/)
[![License](https://img.shields.io/github/license/0x12th/niquests-mock.svg)](LICENSE)

RESPX-style HTTP mocking for [niquests](https://pypi.org/project/niquests/).

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

## Publishing

PyPI publishing is configured through GitHub Actions with trusted publishing on version tags like `v0.1.1`.
Recommended flow:

1. Run the manual `Publish TestPyPI` workflow.
2. Install and smoke-test the package from TestPyPI.
3. Push a release tag like `v0.1.1`.
4. The publish workflow verifies the tag matches `pyproject.toml`, runs checks, publishes to PyPI, and creates a GitHub Release.

Before the first release, configure the PyPI and TestPyPI projects, GitHub environments, and trusted publishers.

### Decorator Style

Useful when you want the test to look almost exactly like a `respx`-based test.

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

## Project Status

Currently in dev.
