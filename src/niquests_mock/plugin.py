from typing import TypedDict, cast

import pytest
from pytest import FixtureRequest

from niquests_mock import MockRouter


class RouterKwargs(TypedDict, total=False):
    assert_all_mocked: bool
    assert_all_called: bool
    base_url: str | None


_ALLOWED_MARKER_KWARGS = frozenset(RouterKwargs.__annotations__)


def _router_kwargs_from_marker(request: FixtureRequest) -> RouterKwargs:
    marker = request.node.get_closest_marker("niquests_mock")
    if marker is None:
        return {}

    kwargs = dict(marker.kwargs)
    unknown = sorted(set(kwargs) - _ALLOWED_MARKER_KWARGS)
    if unknown:
        unknown_keys = ", ".join(unknown)
        allowed_keys = ", ".join(sorted(_ALLOWED_MARKER_KWARGS))
        raise pytest.UsageError(
            f"Unknown niquests_mock marker kwargs: {unknown_keys}. Allowed kwargs: {allowed_keys}"
        )
    return cast(RouterKwargs, kwargs)


def pytest_configure(config) -> None:
    config.addinivalue_line(
        "markers",
        "niquests_mock(**kwargs): configure the niquests_mock fixture/router defaults for a test.",
    )


@pytest.fixture
def niquests_mock(request: FixtureRequest):
    kwargs = _router_kwargs_from_marker(request)
    with MockRouter(
        assert_all_mocked=kwargs.get("assert_all_mocked", True),
        assert_all_called=kwargs.get("assert_all_called", False),
        base_url=kwargs.get("base_url"),
    ) as mock_router:
        yield mock_router


@pytest.fixture
def respx_mock(niquests_mock: MockRouter):
    yield niquests_mock
