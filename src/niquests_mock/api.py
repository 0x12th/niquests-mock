from typing import Any

from .matchers import RequestPattern
from .models import UNSET, Call
from .router import MockRoute, MockRouter
from .types import ContentMatcher, HeaderPattern, QueryPattern, TextMatcher, URLMatcher


def current() -> MockRouter:
    return MockRouter.current()


def calls() -> list[Call]:
    return list(current().calls)


def lookup(name: str) -> MockRoute:
    return current()[name]


def route(
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
    json: Any = UNSET,
) -> MockRoute:
    kwargs = {
        "scheme": scheme,
        "host": host,
        "path": path,
        "headers": headers,
        "params": params,
        "content": content,
    }
    if json is not UNSET:
        kwargs["json"] = json
    return current().route(url, method=method, name=name, **kwargs)


def request(
    method: str,
    url: URLMatcher | RequestPattern = None,
    *,
    name: str | None = None,
    scheme: TextMatcher | None = None,
    host: TextMatcher | None = None,
    path: TextMatcher | None = None,
    headers: HeaderPattern | None = None,
    params: QueryPattern | None = None,
    content: ContentMatcher = None,
    json: Any = UNSET,
) -> MockRoute:
    return route(
        url,
        method=method,
        name=name,
        scheme=scheme,
        host=host,
        path=path,
        headers=headers,
        params=params,
        content=content,
        json=json,
    )


def get(url: URLMatcher = None, **kwargs: Any) -> MockRoute:
    return route(url, method="GET", **kwargs)


def post(url: URLMatcher = None, **kwargs: Any) -> MockRoute:
    return route(url, method="POST", **kwargs)


def put(url: URLMatcher = None, **kwargs: Any) -> MockRoute:
    return route(url, method="PUT", **kwargs)


def patch(url: URLMatcher = None, **kwargs: Any) -> MockRoute:
    return route(url, method="PATCH", **kwargs)


def delete(url: URLMatcher = None, **kwargs: Any) -> MockRoute:
    return route(url, method="DELETE", **kwargs)


def head(url: URLMatcher = None, **kwargs: Any) -> MockRoute:
    return route(url, method="HEAD", **kwargs)


def options(url: URLMatcher = None, **kwargs: Any) -> MockRoute:
    return route(url, method="OPTIONS", **kwargs)


def mock(func=None, /, **router_kwargs: Any):
    if func is None:
        return MockRouter(**router_kwargs)
    return MockRouter(**router_kwargs)(func)
