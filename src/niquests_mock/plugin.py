import pytest

from niquests_mock import MockRouter


def _router_kwargs_from_marker(request) -> dict:
    marker = request.node.get_closest_marker("niquests_mock")
    return dict(marker.kwargs) if marker else {}


def pytest_configure(config) -> None:
    config.addinivalue_line(
        "markers",
        "niquests_mock(**kwargs): configure the niquests_mock fixture/router defaults for a test.",
    )


@pytest.fixture
def niquests_mock(request):
    with MockRouter(**_router_kwargs_from_marker(request)) as mock_router:
        yield mock_router
