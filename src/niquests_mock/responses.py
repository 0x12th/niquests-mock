from datetime import timedelta
from http import HTTPStatus
from typing import Any

import orjson
from niquests.cookies import cookiejar_from_dict
from niquests.models import PreparedRequest, Response
from niquests.structures import CaseInsensitiveDict

from .models import UNSET, UnsetType


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


__all__ = ["build_response"]
