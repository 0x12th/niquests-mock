from collections.abc import Mapping
from dataclasses import dataclass, field
from re import Pattern
from typing import Any, cast, overload
from urllib.parse import parse_qs, urljoin, urlparse

import orjson
from niquests.models import PreparedRequest

from .models import UNSET, UnsetType
from .types import (
    ContentMatcher,
    HeaderPattern,
    JSONMatcher,
    QueryPattern,
    TextMatcher,
    URLMatcher,
)


def _resolve_url(base_url: str | None, url: URLMatcher) -> URLMatcher:
    if base_url is None or url is None or not isinstance(url, str):
        return url
    if "://" in url:
        return url
    return urljoin(base_url.rstrip("/") + "/", url.lstrip("/"))


@dataclass(frozen=True, slots=True)
class TextValueMatcher:
    op: str
    needle: str

    def __call__(self, actual: str) -> bool:
        if self.op == "startswith":
            return actual.startswith(self.needle)
        if self.op == "endswith":
            return actual.endswith(self.needle)
        if self.op == "contains":
            return self.needle in actual
        raise ValueError(f"Unsupported text matcher op: {self.op}")

    def __repr__(self) -> str:
        return f"{self.op}({self.needle!r})"


@dataclass(frozen=True, slots=True)
class BytesValueMatcher:
    op: str
    needle: bytes

    def __call__(self, actual: bytes | None) -> bool:
        if actual is None:
            return False
        if self.op == "startswith":
            return actual.startswith(self.needle)
        if self.op == "endswith":
            return actual.endswith(self.needle)
        if self.op == "contains":
            return self.needle in actual
        raise ValueError(f"Unsupported bytes matcher op: {self.op}")

    def __repr__(self) -> str:
        return f"{self.op}({self.needle!r})"


@dataclass(frozen=True, slots=True)
class MappingSubsetMatcher:
    expected: Mapping[str, Any]

    def __call__(self, actual: Any) -> bool:
        if not isinstance(actual, Mapping):
            return False
        for key, expected_value in self.expected.items():
            if key not in actual or actual[key] != expected_value:
                return False
        return True

    def __repr__(self) -> str:
        return f"subset({dict(self.expected)!r})"


@overload
def startswith(value: str) -> TextValueMatcher: ...


@overload
def startswith(value: bytes) -> BytesValueMatcher: ...


def startswith(value: str | bytes) -> TextValueMatcher | BytesValueMatcher:
    if isinstance(value, bytes):
        return BytesValueMatcher("startswith", value)
    return TextValueMatcher("startswith", value)


@overload
def endswith(value: str) -> TextValueMatcher: ...


@overload
def endswith(value: bytes) -> BytesValueMatcher: ...


def endswith(value: str | bytes) -> TextValueMatcher | BytesValueMatcher:
    if isinstance(value, bytes):
        return BytesValueMatcher("endswith", value)
    return TextValueMatcher("endswith", value)


@overload
def contains(value: str) -> TextValueMatcher: ...


@overload
def contains(value: bytes) -> BytesValueMatcher: ...


def contains(value: str | bytes) -> TextValueMatcher | BytesValueMatcher:
    if isinstance(value, bytes):
        return BytesValueMatcher("contains", value)
    return TextValueMatcher("contains", value)


@overload
def regex(pattern: str) -> Pattern[str]: ...


@overload
def regex(pattern: bytes) -> Pattern[bytes]: ...


def regex(pattern: str | bytes) -> Pattern[str] | Pattern[bytes]:
    import re

    return re.compile(pattern)


def subset(expected: Mapping[str, Any]) -> MappingSubsetMatcher:
    return MappingSubsetMatcher(expected)


def _match_value(expected: Any, actual: Any) -> bool:
    if callable(expected):
        return bool(expected(actual))
    if isinstance(expected, Pattern):
        return expected.search(actual) is not None
    return expected == actual


def _match_text(expected: TextMatcher | None, actual: str | None) -> bool:
    if expected is None:
        return True
    if actual is None:
        return False
    return _match_value(expected, actual)


def _strip_query(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(query="", fragment="").geturl()


def _match_headers(headers: HeaderPattern | None, request: PreparedRequest) -> bool:
    if not headers:
        return True
    request_headers = request.headers or {}
    for key, expected in headers.items():
        actual = request_headers.get(key)
        if actual is None:
            return False
        if not _match_value(expected, actual):
            return False
    return True


def _normalize_query_value(value: Any) -> list[str]:
    if isinstance(value, (str, int, float, bool)):
        return [str(value)]
    return [str(item) for item in value]


def _match_normalized_params(
    expected_params: dict[str, list[str]] | None,
    request_url: str | None,
) -> bool:
    if not expected_params:
        return True
    if request_url is None:
        return False
    actual_params = parse_qs(urlparse(request_url).query, keep_blank_values=True)
    for key, expected in expected_params.items():
        actual = actual_params.get(key)
        if actual is None or actual != expected:
            return False
    return True


def _body_bytes(request: PreparedRequest) -> bytes | None:
    body = request.body
    if body is None:
        return None
    if isinstance(body, bytes):
        return body
    if isinstance(body, str):
        return body.encode("utf-8")
    return None


def _match_content(content: ContentMatcher, request: PreparedRequest) -> bool:
    if content is None:
        return True
    actual = _body_bytes(request)
    if callable(content):
        return bool(cast(Any, content)(actual))
    if isinstance(content, Pattern):
        return actual is not None and content.search(actual) is not None
    if isinstance(content, str):
        return actual == content.encode("utf-8")
    return actual == content


def _match_json(expected: JSONMatcher | UnsetType, request: PreparedRequest) -> bool:
    if expected is UNSET:
        return True
    actual = _body_bytes(request)
    if actual is None:
        return False
    try:
        payload = orjson.loads(actual)
    except orjson.JSONDecodeError:
        return False
    if callable(expected):
        return bool(cast(Any, expected)(payload))
    return payload == expected


@dataclass(slots=True)
class RequestPattern:
    method: str | None = None
    url: URLMatcher = None
    scheme: TextMatcher | None = None
    host: TextMatcher | None = None
    path: TextMatcher | None = None
    headers: HeaderPattern | None = None
    params: QueryPattern | None = None
    content: ContentMatcher = None
    json: JSONMatcher | UnsetType = UNSET
    _url_no_query: str | None = field(init=False, default=None, repr=False)
    _normalized_params: dict[str, list[str]] | None = field(init=False, default=None, repr=False)
    _needs_urlparse: bool = field(init=False, default=False, repr=False)

    def __post_init__(self) -> None:
        if isinstance(self.url, str) and self.params:
            self._url_no_query = _strip_query(self.url)
        if self.params:
            self._normalized_params = {
                key: _normalize_query_value(value) for key, value in self.params.items()
            }
        self._needs_urlparse = bool(self.scheme or self.host or self.path or self.params)

    @property
    def is_exact(self) -> bool:
        return (
            self.method is not None
            and isinstance(self.url, str)
            and self.scheme is None
            and self.host is None
            and self.path is None
            and self.headers is None
            and self.params is None
            and self.content is None
            and self.json is UNSET
        )

    def __and__(self, other: "RequestPattern") -> "RequestPattern":
        if not isinstance(other, RequestPattern):
            return NotImplemented
        if self.method and other.method and self.method != other.method:
            raise ValueError("Conflicting method matchers cannot be combined.")
        return RequestPattern(
            method=other.method or self.method,
            url=other.url if other.url is not None else self.url,
            scheme=other.scheme or self.scheme,
            host=other.host or self.host,
            path=other.path or self.path,
            headers=(dict(self.headers or {}) | dict(other.headers or {})) or None,
            params=(dict(self.params or {}) | dict(other.params or {})) or None,
            content=other.content if other.content is not None else self.content,
            json=other.json if other.json is not UNSET else self.json,
        )

    def with_base_url(self, base_url: str | None) -> "RequestPattern":
        if self.url is None:
            return self
        return RequestPattern(
            method=self.method,
            url=_resolve_url(base_url, self.url),
            scheme=self.scheme,
            host=self.host,
            path=self.path,
            headers=self.headers,
            params=self.params,
            content=self.content,
            json=self.json,
        )

    def matches(self, request: PreparedRequest) -> bool:
        if self.method and request.method != self.method:
            return False
        request_url = request.url
        if self.url is not None:
            if request_url is None:
                return False
            if self._url_no_query is not None:
                if self._url_no_query != _strip_query(request_url):
                    return False
            elif not _match_value(self.url, request_url):
                return False
        parsed = urlparse(request_url) if self._needs_urlparse and request_url is not None else None
        if not _match_text(self.scheme, parsed.scheme if parsed else None):
            return False
        if not _match_text(self.host, parsed.netloc if parsed else None):
            return False
        if not _match_text(self.path, parsed.path if parsed else None):
            return False
        if not _match_headers(self.headers, request):
            return False
        if not _match_normalized_params(self._normalized_params, request_url):
            return False
        if not _match_content(self.content, request):
            return False
        if not _match_json(self.json, request):
            return False
        return True

    def describe(self) -> str:
        parts: list[str] = []
        if self.method:
            parts.append(self.method)
        if self.url is not None:
            parts.append(str(self.url))
        if self.scheme:
            parts.append(f"scheme={self.scheme}")
        if self.host:
            parts.append(f"host={self.host}")
        if self.path:
            parts.append(f"path={self.path}")
        if self.headers:
            parts.append(f"headers={dict(self.headers)}")
        if self.params:
            parts.append(f"params={dict(self.params)}")
        if self.content is not None:
            parts.append("content=<set>")
        if self.json is not UNSET:
            parts.append("json=<set>")
        return " ".join(parts) or "*"


def M(
    *,
    method: str | None = None,
    url: URLMatcher = None,
    scheme: TextMatcher | None = None,
    host: TextMatcher | None = None,
    path: TextMatcher | None = None,
    headers: HeaderPattern | None = None,
    params: QueryPattern | None = None,
    content: ContentMatcher = None,
    json: JSONMatcher | UnsetType = UNSET,
) -> RequestPattern:
    return RequestPattern(
        method=method.upper() if method else None,
        url=url,
        scheme=scheme,
        host=host,
        path=path,
        headers=headers,
        params=params,
        content=content,
        json=json,
    )
