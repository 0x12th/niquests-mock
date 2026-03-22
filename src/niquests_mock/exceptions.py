from niquests.exceptions import ConnectionError


class NoMockAddress(ConnectionError):
    """Raised when a request did not match any registered mock route."""


class AllMockedAssertionError(AssertionError):
    """Raised when a router is configured to require mocked calls."""
