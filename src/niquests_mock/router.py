import inspect
from contextvars import ContextVar, Token
from copy import deepcopy
from datetime import timedelta
from functools import wraps
from http import HTTPStatus
from typing import Any, cast
from unittest.mock import patch

import orjson
from niquests.async_session import AsyncSession
from niquests.cookies import cookiejar_from_dict
from niquests.models import PreparedRequest, Response
from niquests.sessions import Session
from niquests.structures import CaseInsensitiveDict

from .exceptions import AllMockedAssertionError, NoMockAddress
from .matchers import M, RequestPattern, _resolve_url
from .models import UNSET, Call, UnsetType
from .types import (
    ContentMatcher,
    HeaderPattern,
    QueryPattern,
    SideEffect,
    SyncSideEffect,
    TextMatcher,
    URLMatcher,
)


def _response_bytes(
    *,
    content: bytes | str | None,
    text: str | None,
    json: Any | UnsetType,
) -> tuple[bytes | None, str | None]:
    if json is not UNSET:
        return orjson.dumps(json), "application/json"
    if text is not None:
        return text.encode("utf-8"), "text/plain; charset=utf-8"
    if isinstance(content, str):
        return content.encode("utf-8"), None
    return content, None


def _reason_phrase(status_code: int, reason: str | None) -> str:
    if reason is not None:
        return reason
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return str(status_code)


def build_response(
    request: PreparedRequest,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    content: bytes | str | None = None,
    text: str | None = None,
    json: Any | UnsetType = UNSET,
    cookies: dict[str, str] | None = None,
    reason: str | None = None,
) -> Response:
    response = Response()
    response.request = request
    response.url = request.url
    response.status_code = status_code
    response.headers = CaseInsensitiveDict(headers or {})
    response.reason = _reason_phrase(status_code, reason)
    response.elapsed = timedelta(0)

    body, default_content_type = _response_bytes(content=content, text=text, json=json)
    if default_content_type:
        response.headers.setdefault("Content-Type", default_content_type)
        response.encoding = "utf-8"

    response._content = body
    response._content_consumed = True
    if cookies:
        response.cookies = cookiejar_from_dict(cookies)
    if body is not None:
        response.headers.setdefault("Content-Length", str(len(body)))
    return response


class MockRoute:
    def __init__(
        self,
        router: "MockRouter",
        *,
        method: str | None = None,
        url: URLMatcher | RequestPattern = None,
        name: str | None = None,
        scheme: TextMatcher | None = None,
        host: TextMatcher | None = None,
        path: TextMatcher | None = None,
        headers: HeaderPattern | None = None,
        params: QueryPattern | None = None,
        content: ContentMatcher = None,
        json: Any | UnsetType = UNSET,
    ) -> None:
        self.router = router
        self.name = name
        self.pattern = self._build_pattern(
            method=method,
            url=url,
            scheme=scheme,
            host=host,
            path=path,
            headers=headers,
            params=params,
            content=content,
            json=json,
        )
        self.calls: list[Call] = []
        self._return_value: Response | None = None
        self._side_effect: SideEffect | None = None
        self._pass_through = False

    def _build_pattern(
        self,
        *,
        method: str | None,
        url: URLMatcher | RequestPattern,
        scheme: TextMatcher | None,
        host: TextMatcher | None,
        path: TextMatcher | None,
        headers: HeaderPattern | None,
        params: QueryPattern | None,
        content: ContentMatcher,
        json: Any | UnsetType,
    ) -> RequestPattern:
        extra_pattern = M(
            method=method,
            scheme=scheme,
            host=host,
            path=path,
            headers=headers,
            params=params,
            content=content,
            json=json,
        )
        if isinstance(url, RequestPattern):
            return url.with_base_url(self.router.base_url) & extra_pattern
        return RequestPattern(
            method=method.upper() if method else None,
            url=_resolve_url(self.router.base_url, url),
            scheme=scheme,
            host=host,
            path=path,
            headers=headers,
            params=params,
            content=content,
            json=json,
        )

    @property
    def method(self) -> str | None:
        return self.pattern.method

    @property
    def url(self) -> URLMatcher:
        return self.pattern.url

    @property
    def called(self) -> bool:
        return bool(self.calls)

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def matches(self, request: PreparedRequest) -> bool:
        return self.pattern.matches(request)

    def mock(
        self,
        *,
        return_value: Response | None = None,
        side_effect: SideEffect | None = None,
        pass_through: bool = False,
    ) -> "MockRoute":
        self._return_value = return_value
        self._side_effect = side_effect
        self._pass_through = pass_through
        return self

    def respond(
        self,
        status_code: int = 200,
        *,
        headers: dict[str, str] | None = None,
        content: bytes | str | None = None,
        text: str | None = None,
        json: Any | UnsetType = UNSET,
        cookies: dict[str, str] | None = None,
        reason: str | None = None,
    ) -> "MockRoute":
        def responder(request: PreparedRequest) -> Response:
            return build_response(
                request,
                status_code=status_code,
                headers=headers,
                content=content,
                text=text,
                json=json,
                cookies=cookies,
                reason=reason,
            )

        return self.mock(side_effect=responder)

    def pass_through(self) -> "MockRoute":
        return self.mock(pass_through=True)

    def reset(self) -> None:
        self.calls.clear()

    def assert_called(self) -> None:
        if not self.called:
            raise AssertionError(f"Route was not called: {self.pattern.describe()}")

    def assert_not_called(self) -> None:
        if self.called:
            raise AssertionError(f"Route was unexpectedly called: {self.pattern.describe()}")

    def assert_called_once(self) -> None:
        if self.call_count != 1:
            raise AssertionError(
                f"Route expected 1 call, got {self.call_count}: {self.pattern.describe()}"
            )

    def assert_called_with(
        self,
        *,
        method: str | None = None,
        url: URLMatcher | RequestPattern = None,
        scheme: TextMatcher | None = None,
        host: TextMatcher | None = None,
        path: TextMatcher | None = None,
        headers: HeaderPattern | None = None,
        params: QueryPattern | None = None,
        content: ContentMatcher = None,
        json: Any | UnsetType = UNSET,
    ) -> None:
        self.assert_called()
        matcher = self._build_pattern(
            method=method,
            url=url,
            scheme=scheme,
            host=host,
            path=path,
            headers=headers,
            params=params,
            content=content,
            json=json,
        )
        last_request = self.calls[-1].request
        if not matcher.matches(last_request):
            raise AssertionError("Last call did not match the expected request payload.")

    def assert_called_once_with(self, **kwargs: Any) -> None:
        self.assert_called_once()
        self.assert_called_with(**kwargs)

    def _record(self, request: PreparedRequest, kwargs: dict[str, Any]) -> Call:
        call = Call(request=request, kwargs=dict(kwargs), route=self)
        self.calls.append(call)
        self.router.calls.append(call)
        return call

    def _finalize(self, call: Call, response: Response) -> Response:
        response.request = call.request
        response.url = response.url or call.request.url
        call.response = response
        return response

    def _raise_side_effect(self) -> None:
        if isinstance(self._side_effect, Exception):
            raise self._side_effect
        if isinstance(self._side_effect, type) and issubclass(self._side_effect, Exception):
            raise self._side_effect()

    def _resolve_sync(self, request: PreparedRequest, kwargs: dict[str, Any]) -> Response | None:
        call = self._record(request, kwargs)
        try:
            if self._pass_through:
                return None
            self._raise_side_effect()
            if callable(self._side_effect):
                response = cast(SyncSideEffect, self._side_effect)(request)
                if response is None:
                    raise TypeError(
                        "Route side_effect must return niquests.Response or raise an exception."
                    )
                return self._finalize(call, response)
            if self._return_value is not None:
                return self._finalize(call, deepcopy(self._return_value))
            raise TypeError(f"Matched route has no configured response: {self.pattern.describe()}")
        except Exception as exc:
            call.exception = exc
            raise

    async def _resolve_async(
        self, request: PreparedRequest, kwargs: dict[str, Any]
    ) -> Response | None:
        call = self._record(request, kwargs)
        try:
            if self._pass_through:
                return None
            self._raise_side_effect()
            if callable(self._side_effect):
                response = cast(Any, self._side_effect)(request)
                if inspect.isawaitable(response):
                    response = await response
                if response is None:
                    raise TypeError(
                        "Route side_effect must return niquests.Response or raise an exception."
                    )
                return self._finalize(call, cast(Response, response))
            if self._return_value is not None:
                return self._finalize(call, deepcopy(self._return_value))
            raise TypeError(f"Matched route has no configured response: {self.pattern.describe()}")
        except Exception as exc:
            call.exception = exc
            raise


class MockRouter:
    _active_routers: ContextVar[tuple["MockRouter", ...]] = ContextVar(
        "niquests_mock_active_routers", default=()
    )
    _sync_patch: Any = None
    _async_patch: Any = None
    _patch_depth: int = 0

    def __init__(
        self,
        *,
        assert_all_mocked: bool = True,
        assert_all_called: bool = False,
        base_url: str | None = None,
    ) -> None:
        self.assert_all_mocked = assert_all_mocked
        self.assert_all_called = assert_all_called
        self.base_url = base_url
        self.routes: list[MockRoute] = []
        self._fallback_routes: list[MockRoute] = []
        self._exact_routes: dict[tuple[str, str], list[MockRoute]] = {}
        self.named_routes: dict[str, MockRoute] = {}
        self.calls: list[Call] = []
        self._token: Token[tuple[MockRouter, ...]] | None = None

    def __enter__(self) -> "MockRouter":
        self.start()
        return self

    def __call__(self, func):
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any):
                async with type(self)(
                    assert_all_mocked=self.assert_all_mocked,
                    assert_all_called=self.assert_all_called,
                    base_url=self.base_url,
                ):
                    return await func(*args, **kwargs)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any):
            with type(self)(
                assert_all_mocked=self.assert_all_mocked,
                assert_all_called=self.assert_all_called,
                base_url=self.base_url,
            ):
                return func(*args, **kwargs)

        return sync_wrapper

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()
        if exc_type is None:
            self.assert_all()

    async def __aenter__(self) -> "MockRouter":
        self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.stop()
        if exc_type is None:
            self.assert_all()

    def __getitem__(self, name: str) -> MockRoute:
        return self.named_routes[name]

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self.named_routes

    @classmethod
    def current_or_none(cls) -> "MockRouter | None":
        routers = cls._active_routers.get()
        return routers[-1] if routers else None

    @classmethod
    def current(cls) -> "MockRouter":
        router = cls.current_or_none()
        if router is None:
            raise RuntimeError("No active MockRouter in the current context.")
        return router

    @classmethod
    def _install_patches(cls) -> None:
        def sync_send(
            session: Session,
            request: PreparedRequest,
            *,
            _original=Session.send,
            **kwargs: Any,
        ) -> Response:
            router = cls.current_or_none()
            if router is None:
                return _original(session, request, **kwargs)
            route = router.match(request)
            if route is None:
                if router.assert_all_mocked:
                    raise NoMockAddress(f"Request not mocked: {request.method} {request.url}")
                return _original(session, request, **kwargs)
            response = route._resolve_sync(request, kwargs)
            if response is None:
                return _original(session, request, **kwargs)
            return response

        async def async_send(
            session: AsyncSession,
            request: PreparedRequest,
            *,
            _original=AsyncSession.send,
            **kwargs: Any,
        ) -> Response:
            router = cls.current_or_none()
            if router is None:
                return await _original(session, request, **kwargs)
            route = router.match(request)
            if route is None:
                if router.assert_all_mocked:
                    raise NoMockAddress(f"Request not mocked: {request.method} {request.url}")
                return await _original(session, request, **kwargs)
            response = await route._resolve_async(request, kwargs)
            if response is None:
                return await _original(session, request, **kwargs)
            return response

        cls._sync_patch = patch.object(Session, "send", sync_send)
        cls._async_patch = patch.object(AsyncSession, "send", async_send)
        cls._sync_patch.start()
        cls._async_patch.start()

    @classmethod
    def _remove_patches(cls) -> None:
        if cls._sync_patch is not None:
            cls._sync_patch.stop()
            cls._sync_patch = None
        if cls._async_patch is not None:
            cls._async_patch.stop()
            cls._async_patch = None

    def start(self) -> "MockRouter":
        cls = type(self)
        if self._token is not None:
            return self
        if cls._patch_depth == 0:
            cls._install_patches()
        cls._patch_depth += 1
        routers = cls._active_routers.get()
        self._token = cls._active_routers.set((*routers, self))
        return self

    def stop(self) -> "MockRouter":
        cls = type(self)
        if self._token is None:
            return self
        cls._active_routers.reset(self._token)
        self._token = None
        cls._patch_depth -= 1
        if cls._patch_depth == 0:
            cls._remove_patches()
        return self

    def reset(self) -> None:
        self.calls.clear()
        for route in self.routes:
            route.reset()

    def pop(self, name: str) -> MockRoute:
        route = self.named_routes.pop(name)
        self.routes.remove(route)
        if route.pattern.is_exact and isinstance(route.url, str) and route.method is not None:
            key = (route.method, route.url)
            bucket = self._exact_routes.get(key)
            if bucket is not None:
                bucket.remove(route)
                if not bucket:
                    del self._exact_routes[key]
        else:
            self._fallback_routes.remove(route)
        return route

    def assert_all(self) -> None:
        if not self.assert_all_called:
            return
        not_called = [route for route in self.routes if not route.called]
        if not_called:
            names = [route.name or route.pattern.describe() for route in not_called]
            raise AllMockedAssertionError(f"Routes not called: {', '.join(names)}")

    def assert_not_called(self) -> None:
        if self.calls:
            raise AssertionError(f"Router expected no calls, got {len(self.calls)}")

    def match(self, request: PreparedRequest) -> "MockRoute | None":
        request_url = request.url
        request_method = request.method
        if request_url is not None and request_method is not None:
            exact_bucket = self._exact_routes.get((request_method, request_url))
            if exact_bucket:
                return exact_bucket[-1]
        for route in reversed(self._fallback_routes):
            if route.matches(request):
                return route
        return None

    def route(
        self,
        url: URLMatcher | RequestPattern = None,
        *,
        method: str | None = None,
        name: str | None = None,
        scheme: TextMatcher | None = None,
        host: TextMatcher | None = None,
        path: TextMatcher | None = None,
        headers: HeaderPattern | None = None,
        params: QueryPattern | None = None,
        content: ContentMatcher = None,
        json: Any | UnsetType = UNSET,
    ) -> MockRoute:
        route = MockRoute(
            self,
            method=method,
            url=url,
            name=name,
            scheme=scheme,
            host=host,
            path=path,
            headers=headers,
            params=params,
            content=content,
            json=json,
        )
        self.routes.append(route)
        if route.pattern.is_exact and isinstance(route.url, str) and route.method is not None:
            self._exact_routes.setdefault((route.method, route.url), []).append(route)
        else:
            self._fallback_routes.append(route)
        if name is not None:
            self.named_routes[name] = route
        return route

    def request(self, method: str, url: URLMatcher = None, **kwargs: Any) -> MockRoute:
        return self.route(url, method=method, **kwargs)

    def get(self, url: URLMatcher | RequestPattern = None, **kwargs: Any) -> MockRoute:
        return self.route(url, method="GET", **kwargs)

    def post(self, url: URLMatcher | RequestPattern = None, **kwargs: Any) -> MockRoute:
        return self.route(url, method="POST", **kwargs)

    def put(self, url: URLMatcher | RequestPattern = None, **kwargs: Any) -> MockRoute:
        return self.route(url, method="PUT", **kwargs)

    def patch(self, url: URLMatcher | RequestPattern = None, **kwargs: Any) -> MockRoute:
        return self.route(url, method="PATCH", **kwargs)

    def delete(self, url: URLMatcher | RequestPattern = None, **kwargs: Any) -> MockRoute:
        return self.route(url, method="DELETE", **kwargs)

    def head(self, url: URLMatcher | RequestPattern = None, **kwargs: Any) -> MockRoute:
        return self.route(url, method="HEAD", **kwargs)

    def options(self, url: URLMatcher | RequestPattern = None, **kwargs: Any) -> MockRoute:
        return self.route(url, method="OPTIONS", **kwargs)


__all__ = ["MockRoute", "MockRouter", "build_response"]
