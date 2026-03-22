import asyncio
import re

import niquests
import pytest

import niquests_mock as nmock
from niquests_mock import MockRouter, NoMockAddress


def test_sync_request_is_mocked() -> None:
    with MockRouter() as router:
        route = router.get("https://api.example.test/users").respond(
            status_code=200,
            json=[{"id": 1, "name": "Ada"}],
            headers={"X-Test": "yes"},
        )

        response = niquests.get("https://api.example.test/users")

    assert response.status_code == 200
    assert response.json() == [{"id": 1, "name": "Ada"}]
    assert response.headers["X-Test"] == "yes"
    route.assert_called_once()
    assert route.calls[0].request.method == "GET"


def test_regex_route_matches() -> None:
    with MockRouter() as router:
        route = router.get(re.compile(r"https://api\.example\.test/users/\d+$")).respond(text="ok")
        response = niquests.get("https://api.example.test/users/42")

    assert response.text == "ok"
    assert route.call_count == 1


def test_unmatched_request_raises() -> None:
    with MockRouter():
        with pytest.raises(NoMockAddress):
            niquests.get("https://api.example.test/missing")


def test_named_route_lookup_and_payload_matchers() -> None:
    with MockRouter(base_url="https://api.example.test") as router:
        route = router.post(
            "/jobs",
            name="jobs.create",
            headers={"X-Trace": "trace-1"},
            params={"expand": "details"},
            json={"name": "build"},
        ).respond(status_code=201, json={"ok": True})

        response = niquests.post(
            "https://api.example.test/jobs?expand=details",
            json={"name": "build"},
            headers={"X-Trace": "trace-1"},
        )

    assert router["jobs.create"] is route
    assert response.status_code == 201
    route.assert_called_once_with(
        headers={"X-Trace": "trace-1"},
        params={"expand": "details"},
        json={"name": "build"},
    )


def test_pattern_object_supports_host_path_and_composition() -> None:
    pattern = nmock.M(host="api.example.test", path="/users") & nmock.M(method="GET")

    with MockRouter() as router:
        route = router.route(pattern, name="users.list").respond(json=[{"id": 1}])
        response = niquests.get("https://api.example.test/users")

    assert router["users.list"] is route
    route.assert_called_once_with(host="api.example.test", path="/users", method="GET")
    assert response.json() == [{"id": 1}]


def test_content_matcher_supports_regex() -> None:
    with MockRouter() as router:
        route = router.post(
            "https://api.example.test/upload",
            content=re.compile(rb'"name"\s*:\s*"build"'),
        ).respond(status_code=202)
        response = niquests.post(
            "https://api.example.test/upload",
            data=b'{"name": "build", "kind": "job"}',
        )

    route.assert_called_once()
    assert response.status_code == 202


def test_helper_matchers_and_json_subset() -> None:
    with MockRouter() as router:
        route = router.post(
            nmock.M(
                host=nmock.endswith("example.test"),
                path=nmock.startswith("/api/"),
                json=nmock.subset({"name": "build"}),
            ),
            name="jobs.create",
        ).respond(status_code=201, cookies={"session": "abc"})
        response = niquests.post(
            "https://service.example.test/api/jobs",
            json={"name": "build", "priority": "high"},
        )

    assert response.status_code == 201
    assert any(cookie.name == "session" and cookie.value == "abc" for cookie in response.cookies)
    assert router["jobs.create"] is route


def test_top_level_regex_helper() -> None:
    with MockRouter() as router:
        route = router.get(nmock.M(path=nmock.regex(r"^/v\d+/users$"), method="GET")).respond(
            status_code=200
        )
        response = niquests.get("https://api.example.test/v1/users")

    route.assert_called_once()
    assert response.status_code == 200


def test_decorator_api_matches_respx_style() -> None:
    @nmock.mock
    def run() -> tuple[int, bool]:
        route = nmock.get("https://example.org/", name="homepage").respond(status_code=204)
        response = niquests.get("https://example.org/")
        assert response.status_code is not None
        return response.status_code, nmock.lookup("homepage").called and route.called

    status_code, called = run()

    assert status_code == 204
    assert called is True


def test_decorator_factory_api_matches_respx_style() -> None:
    @nmock.mock(assert_all_called=True, base_url="https://example.org")
    def run() -> int:
        nmock.get("/health", name="health").respond(status_code=202)
        response = niquests.get("https://example.org/health")
        assert response.status_code is not None
        return response.status_code

    assert run() == 202


def test_fixture_api_matches_respx_style(niquests_mock: MockRouter) -> None:
    route = niquests_mock.get("https://example.org/").respond()
    response = niquests.get("https://example.org/")

    assert route.called
    assert response.status_code == 200


def test_pass_through_uses_original_send(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_send(self, request, **kwargs):
        return nmock.build_response(request, status_code=204, text="passthrough")

    monkeypatch.setattr("niquests.sessions.Session.send", fake_send)

    with MockRouter() as router:
        router.get("https://api.example.test/live").pass_through()
        response = niquests.get("https://api.example.test/live")

    assert response.status_code == 204
    assert response.text == "passthrough"


def test_async_request_is_mocked() -> None:
    async def run() -> None:
        async with MockRouter() as router:
            route = router.post(
                "https://api.example.test/jobs",
                json={"name": "build"},
            ).respond(status_code=201, json={"ok": True})
            response = await niquests.arequest(
                "POST",
                "https://api.example.test/jobs",
                json={"name": "build"},
            )

        assert response.status_code == 201
        assert response.json() == {"ok": True}
        route.assert_called_once_with(json={"name": "build"})

    asyncio.run(run())


def test_global_patch_falls_back_without_active_router(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_send(self, request, **kwargs):
        calls.append(request.url or "")
        return nmock.build_response(request, status_code=204)

    monkeypatch.setattr("niquests.sessions.Session.send", fake_send)
    MockRouter._install_patches()
    try:
        response = niquests.get("https://example.org/fallback")
    finally:
        MockRouter._remove_patches()

    assert response.status_code == 204
    assert calls == ["https://example.org/fallback"]
