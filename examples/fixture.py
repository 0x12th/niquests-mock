import niquests


def test_fixture_style(niquests_mock) -> None:
    route = niquests_mock.get("https://example.org/").respond(status_code=200)
    response = niquests.get("https://example.org/")

    assert route.called
    assert response.status_code == 200
