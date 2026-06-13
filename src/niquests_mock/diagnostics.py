from niquests.models import PreparedRequest

from .matchers import RequestPattern
from .models import UNSET


def request_summary(request: PreparedRequest) -> str:
    parts = [str(request.method or "<unknown>"), str(request.url or "<unknown>")]
    if request.body is not None:
        parts.append("body=<set>")
    return " ".join(parts)


def pattern_summary(pattern: RequestPattern) -> str:
    parts: list[str] = []
    if pattern.method:
        parts.append(pattern.method)
    if pattern.url is not None:
        parts.append(str(pattern.url))
    if pattern.scheme:
        parts.append(f"scheme={pattern.scheme}")
    if pattern.host:
        parts.append(f"host={pattern.host}")
    if pattern.path:
        parts.append(f"path={pattern.path}")
    if pattern.headers:
        parts.append("headers=<set>")
    if pattern.params:
        parts.append("params=<set>")
    if pattern.content is not None:
        parts.append("content=<set>")
    if pattern.json is not UNSET:
        parts.append("json=<set>")
    return " ".join(parts) or "*"
