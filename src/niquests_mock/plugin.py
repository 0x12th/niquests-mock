import pytest
from niquests_mock import MockRouter


@pytest.fixture
def niquests_mock(request):
    with MockRouter() as mock:
        yield mock
