from collections.abc import Callable, Mapping, Sequence
from re import Pattern
from typing import Any, TypeAlias

from niquests.models import PreparedRequest, Response

URLMatcher: TypeAlias = str | Pattern[str] | Callable[[str], bool] | None
TextMatcher: TypeAlias = str | Pattern[str] | Callable[[str], bool]
BytesMatcher: TypeAlias = bytes | Pattern[bytes] | Callable[[bytes | None], bool]
ScalarMatcher: TypeAlias = str | int | float | bool
QueryValue: TypeAlias = ScalarMatcher | Sequence[ScalarMatcher]
HeaderPattern: TypeAlias = Mapping[str, TextMatcher]
QueryPattern: TypeAlias = Mapping[str, QueryValue]
JSONMatcher: TypeAlias = Any | Callable[[Any], bool]
ContentMatcher: TypeAlias = bytes | str | Pattern[bytes] | Callable[[bytes | None], bool] | None
SyncSideEffect: TypeAlias = Callable[[PreparedRequest], Response | None]
AsyncSideEffect: TypeAlias = Callable[[PreparedRequest], Response | None | Any]
SideEffect: TypeAlias = Exception | type[Exception] | SyncSideEffect | AsyncSideEffect
