from typing import TypedDict, cast

import pytest
from pytest import FixtureRequest

from niquests_mock import MockRouter


class RouterKwargs(TypedDict, total=False):
    assert_all_mocked: bool
    assert_all_called: bool
    base_url: str | None


def _router_kwargs_from_marker(request: FixtureRequest) -> RouterKwargs:
    marker = request.node.get_closest_marker("niquests_mock")
    return cast(RouterKwargs, dict(marker.kwargs)) if marker else {}


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
