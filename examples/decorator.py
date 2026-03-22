import niquests

import niquests_mock as nmock


@nmock.mock
def test_decorator_style() -> None:
    route = nmock.get("https://example.org/", name="homepage").respond(
        status_code=200,
        json={"ok": True},
    )

    response = niquests.get("https://example.org/")

    route.assert_called_once()
    assert nmock.lookup("homepage") is route
    assert response.json() == {"ok": True}
