import asyncio
import inspect
import re
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any

import niquests
import pytest

import niquests_mock as nmock
from niquests_mock import AllMockedAssertionError, MockRouter, NoMockAddress

pytest_plugins = ("pytester",)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(209)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"live")

    def log_message(self, format: str, *args: Any) -> None:
        pass


@contextmanager
def local_http_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/live"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


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


def test_unmatched_request_error_lists_registered_routes_without_sensitive_values() -> None:
    with MockRouter() as router:
        router.get("https://api.example.test/users", name="users.list").respond()
        router.post(
            "https://api.example.test/jobs",
            name="jobs.create",
            headers={"Authorization": "Bearer secret"},
            json={"token": "secret"},
        ).respond(status_code=201)

        with pytest.raises(NoMockAddress) as exc_info:
            niquests.delete("https://api.example.test/missing", headers={"Authorization": "secret"})

    message = str(exc_info.value)
    assert "Request not mocked: DELETE https://api.example.test/missing" in message
    assert "Registered routes:" in message
    assert "- users.list: GET https://api.example.test/users" in message
    assert "- jobs.create: POST https://api.example.test/jobs headers=<set> json=<set>" in message
    assert "Bearer secret" not in message
    assert "Authorization" not in message
    assert "token" not in message


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


def test_query_matching_keeps_duplicate_value_order_and_decodes_values() -> None:
    with MockRouter() as router:
        route = router.get(
            "https://api.example.test/search?ignored=true",
            params={"tag": ["one", "two"], "q": "hello world"},
        ).respond(status_code=200)

        response = niquests.get("https://api.example.test/search?tag=one&tag=two&q=hello%20world")

    assert response.status_code == 200
    route.assert_called_once()


def test_query_matching_rejects_different_duplicate_value_order() -> None:
    with MockRouter() as router:
        router.get(
            "https://api.example.test/search",
            params={"tag": ["one", "two"]},
        ).respond(status_code=200)

        with pytest.raises(NoMockAddress):
            niquests.get("https://api.example.test/search?tag=two&tag=one")


def test_header_matching_uses_niquests_case_insensitive_headers() -> None:
    with MockRouter() as router:
        route = router.get(
            "https://api.example.test/headers",
            headers={"x-trace": "trace-1"},
        ).respond(status_code=200)

        response = niquests.get(
            "https://api.example.test/headers",
            headers={"X-Trace": "trace-1"},
        )

    assert response.status_code == 200
    route.assert_called_once()


def test_exact_route_precedence_beats_later_fallback_route() -> None:
    with MockRouter() as router:
        exact = router.get("https://api.example.test/users").respond(text="exact")
        fallback = router.get(nmock.M(host="api.example.test", path="/users")).respond(
            text="fallback"
        )

        response = niquests.get("https://api.example.test/users")

    assert response.text == "exact"
    exact.assert_called_once()
    fallback.assert_not_called()


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


def test_mock_decorator_uses_fresh_router_for_each_call() -> None:
    router_ids: list[int] = []
    call_counts_at_start: list[int] = []

    @nmock.mock
    def run() -> int:
        router = nmock.current()
        router_ids.append(id(router))
        call_counts_at_start.append(len(router.calls))
        nmock.get("https://example.org/fresh").respond(status_code=203)
        response = niquests.get("https://example.org/fresh")
        assert response.status_code is not None
        return response.status_code

    assert run() == 203
    assert run() == 203
    assert router_ids[0] != router_ids[1]
    assert call_counts_at_start == [0, 0]


def test_mock_router_call_copies_configuration_but_not_routes() -> None:
    decorator = MockRouter(base_url="https://example.org")
    decorator.get("/preconfigured").respond(status_code=204)

    @decorator
    def run() -> int:
        nmock.get("/registered-inside").respond(status_code=205)
        response = niquests.get("https://example.org/registered-inside")
        assert response.status_code is not None
        return response.status_code

    assert run() == 205
    assert decorator.routes[0].called is False


def test_fixture_api_matches_respx_style(niquests_mock: MockRouter) -> None:
    route = niquests_mock.get("https://example.org/").respond()
    response = niquests.get("https://example.org/")

    assert route.called
    assert response.status_code == 200


def test_respx_mock_fixture_alias(respx_mock: MockRouter) -> None:
    route = respx_mock.get("https://example.org/alias").respond(status_code=201)
    response = niquests.get("https://example.org/alias")

    route.assert_called_once()
    assert response.status_code == 201


def test_assert_called_with_supports_request_pattern() -> None:
    pattern = nmock.M(host="api.example.test", path="/users", method="GET")

    with MockRouter() as router:
        route = router.get(pattern).respond(status_code=200)
        niquests.get("https://api.example.test/users")

    route.assert_called_once_with(url=pattern)


def test_assert_called_with_mismatch_describes_expected_and_actual_safely() -> None:
    with MockRouter() as router:
        route = router.post(nmock.M(host="api.example.test", path="/jobs")).respond(status_code=201)
        niquests.post(
            "https://api.example.test/jobs?token=secret",
            headers={"Authorization": "Bearer secret"},
            json={"token": "secret"},
        )

    with pytest.raises(AssertionError) as exc_info:
        route.assert_called_once_with(
            headers={"Authorization": "Bearer secret"},
            params={"expand": "details"},
            json={"token": "secret"},
        )

    message = str(exc_info.value)
    assert "Last call did not match the expected request." in message
    assert "Expected: headers=<set> params=<set> json=<set>" in message
    assert "Actual: POST https://api.example.test/jobs?token=secret body=<set>" in message
    assert "Bearer secret" not in message
    assert "Authorization" not in message
    assert "expand" not in message


def test_route_assertion_errors_redact_sensitive_matchers() -> None:
    with MockRouter() as router:
        route = router.get(
            "https://api.example.test/secret",
            headers={"Authorization": "Bearer secret"},
            params={"token": "secret"},
            json={"token": "secret"},
        )

    with pytest.raises(AssertionError) as not_called:
        route.assert_called()
    with pytest.raises(AssertionError) as not_called_once:
        route.assert_called_once()

    with MockRouter() as router:
        called_route = router.get(
            "https://api.example.test/called",
            headers={"Authorization": "Bearer secret"},
            params={"token": "secret"},
        ).respond()
        niquests.get(
            "https://api.example.test/called?token=secret",
            headers={"Authorization": "Bearer secret"},
        )

    with pytest.raises(AssertionError) as unexpectedly_called:
        called_route.assert_not_called()

    messages = [str(not_called.value), str(not_called_once.value), str(unexpectedly_called.value)]
    for message in messages:
        assert "headers=<set>" in message
        assert "params=<set>" in message
        assert "Bearer secret" not in message
        assert "Authorization" not in message
        assert "token" not in message


def test_missing_response_error_redacts_sensitive_matchers() -> None:
    with MockRouter() as router:
        router.get(
            "https://api.example.test/no-response",
            headers={"Authorization": "Bearer secret"},
            params={"token": "secret"},
        )
        with pytest.raises(TypeError) as exc_info:
            niquests.get(
                "https://api.example.test/no-response?token=secret",
                headers={"Authorization": "Bearer secret"},
            )

    message = str(exc_info.value)
    assert "Matched route has no configured response" in message
    assert "headers=<set>" in message
    assert "params=<set>" in message
    assert "Bearer secret" not in message
    assert "Authorization" not in message
    assert "token" not in message


def test_assert_all_called_error_redacts_sensitive_matchers() -> None:
    with pytest.raises(AllMockedAssertionError) as exc_info:
        with MockRouter(assert_all_called=True) as router:
            router.get(
                "https://api.example.test/unused-sensitive",
                headers={"Authorization": "Bearer secret"},
                params={"token": "secret"},
            ).respond()

    message = str(exc_info.value)
    assert "headers=<set>" in message
    assert "params=<set>" in message
    assert "Bearer secret" not in message
    assert "Authorization" not in message
    assert "token" not in message


def test_build_response_allows_non_standard_status_code() -> None:
    with MockRouter() as router:
        router.get("https://example.org/custom").respond(status_code=299)
        response = niquests.get("https://example.org/custom")

    assert response.status_code == 299
    assert response.reason == "299"


def test_niquests_runtime_contracts_are_supported() -> None:
    from niquests.async_session import AsyncSession
    from niquests.models import Response
    from niquests.sessions import Session

    sync_signature = inspect.signature(Session.send)
    async_signature = inspect.signature(AsyncSession.send)
    assert "request" in sync_signature.parameters
    assert "request" in async_signature.parameters

    with MockRouter() as router:
        router.get("https://api.example.test/compat").respond(
            status_code=200,
            json={"ok": True},
            headers={"X-Test": "yes"},
        )
        response = niquests.get("https://api.example.test/compat")

    assert isinstance(response, Response)
    assert response.request is not None
    assert response.url == "https://api.example.test/compat"
    assert response.headers["X-Test"] == "yes"
    assert response.json() == {"ok": True}


def test_pass_through_uses_original_send_in_strict_mode() -> None:
    with local_http_url() as url:
        with MockRouter(assert_all_mocked=True) as router:
            router.get(url).pass_through()
            response = niquests.get(url)
            with pytest.raises(NoMockAddress):
                niquests.get("https://api.example.test/unmocked")

    assert response.status_code == 209
    assert response.text == "live"


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


def test_nested_routers_use_innermost_then_restore_outer() -> None:
    with MockRouter() as outer:
        outer_route = outer.get("https://api.example.test/resource").respond(text="outer")
        assert niquests.get("https://api.example.test/resource").text == "outer"

        with MockRouter() as inner:
            inner_route = inner.get("https://api.example.test/resource").respond(text="inner")
            assert niquests.get("https://api.example.test/resource").text == "inner"

        assert niquests.get("https://api.example.test/resource").text == "outer"

    assert outer_route.call_count == 2
    assert inner_route.call_count == 1


def test_patch_cleanup_after_exception_inside_context() -> None:
    with local_http_url() as url:
        with pytest.raises(RuntimeError, match="boom"):
            with MockRouter():
                raise RuntimeError("boom")

        response = niquests.get(url)

    assert response.status_code == 209
    assert response.text == "live"


def test_repeated_start_stop_is_idempotent_and_reusable() -> None:
    router = MockRouter()
    router.get("https://api.example.test/first").respond(status_code=201)

    router.start()
    router.start()
    assert niquests.get("https://api.example.test/first").status_code == 201
    router.stop()
    router.stop()

    with local_http_url() as url:
        assert niquests.get(url).status_code == 209

    router.get("https://api.example.test/second").respond(status_code=202)
    router.start()
    try:
        assert niquests.get("https://api.example.test/second").status_code == 202
    finally:
        router.stop()


def test_patch_depth_invariant_failure_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    router = MockRouter()
    monkeypatch.setattr(MockRouter, "_patch_depth", -1)

    with pytest.raises(RuntimeError, match="patch depth is inconsistent"):
        router.start()


def test_assert_all_called_fails_for_unused_route() -> None:
    with pytest.raises(AllMockedAssertionError, match="unused"):
        with MockRouter(assert_all_called=True) as router:
            router.get("https://api.example.test/unused", name="unused").respond()


def test_side_effect_exception_is_recorded_on_call() -> None:
    error = ValueError("side effect failed")

    with MockRouter() as router:
        route = router.get("https://api.example.test/fails").mock(side_effect=error)
        with pytest.raises(ValueError, match="side effect failed"):
            niquests.get("https://api.example.test/fails")

    assert route.call_count == 1
    assert route.calls[0].exception is error


def test_async_side_effect_awaitable_is_awaited() -> None:
    async def run() -> None:
        async def side_effect(request):
            await asyncio.sleep(0)
            return nmock.build_response(request, status_code=207, text="async")

        async with MockRouter() as router:
            route = router.get("https://api.example.test/async-side-effect").mock(
                side_effect=side_effect
            )
            response = await niquests.arequest("GET", "https://api.example.test/async-side-effect")

        route.assert_called_once()
        assert response.status_code == 207
        assert response.text == "async"

    asyncio.run(run())


def test_niquests_mock_marker_rejects_unknown_kwargs(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import niquests
        import pytest

        @pytest.mark.niquests_mock(assert_all_moked=False)
        def test_typo(niquests_mock):
            niquests.get("https://api.example.test/unmocked")
        """
    )

    result = pytester.runpytest("-q")

    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(
        [
            "*pytest.UsageError: Unknown niquests_mock marker kwargs: assert_all_moked. "
            "Allowed kwargs: assert_all_called, assert_all_mocked, base_url*"
        ]
    )
