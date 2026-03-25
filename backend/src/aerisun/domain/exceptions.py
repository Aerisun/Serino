"""Domain exception hierarchy.

Every service-layer error is expressed as one of these exceptions.
A global FastAPI exception handler (registered in ``api.exception_handlers``)
translates each subclass into the appropriate HTTP status code, keeping
the service layer completely free of HTTP/FastAPI concerns.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base for all domain-layer exceptions."""

    def __init__(self, message: str = "", *, detail: str | None = None) -> None:
        super().__init__(message)
        self.detail = detail or message


class ResourceNotFound(DomainError):
    """The requested resource does not exist. → HTTP 404"""


class AuthenticationFailed(DomainError):
    """Credentials are invalid or the session has expired. → HTTP 401"""


class PermissionDenied(DomainError):
    """The caller lacks the required permissions or scopes. → HTTP 403"""


class ValidationError(DomainError):
    """The input violates a business rule. → HTTP 422"""


class StateConflict(DomainError):
    """The operation conflicts with the current resource state (e.g. duplicate). → HTTP 409"""


class PayloadTooLarge(DomainError):
    """The uploaded payload exceeds the allowed size. → HTTP 413"""
