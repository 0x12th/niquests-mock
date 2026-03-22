from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from niquests.models import PreparedRequest, Response

if TYPE_CHECKING:
    from .router import MockRoute


class UnsetType:
    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


UNSET = UnsetType()


@dataclass(slots=True)
class Call:
    request: PreparedRequest
    kwargs: dict[str, Any] = field(default_factory=dict)
    route: "MockRoute | None" = None
    response: Response | None = None
    exception: Exception | None = None
