from collections.abc import Callable, Mapping, Sequence
from re import Pattern
from typing import Any

from niquests.models import PreparedRequest, Response

type URLMatcher = str | Pattern[str] | Callable[[str], bool] | None
type TextMatcher = str | Pattern[str] | Callable[[str], bool]
type BytesMatcher = bytes | Pattern[bytes] | Callable[[bytes | None], bool]
type ScalarMatcher = str | int | float | bool
type QueryValue = ScalarMatcher | Sequence[ScalarMatcher]
type HeaderPattern = Mapping[str, TextMatcher]
type QueryPattern = Mapping[str, QueryValue]
type JSONMatcher = Any | Callable[[Any], bool]
type ContentMatcher = bytes | str | Pattern[bytes] | Callable[[bytes | None], bool] | None
type SyncSideEffect = Callable[[PreparedRequest], Response | None]
type AsyncSideEffect = Callable[[PreparedRequest], Response | None | Any]
type SideEffect = Exception | type[Exception] | SyncSideEffect | AsyncSideEffect
