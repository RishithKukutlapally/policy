"""Typed PolicyForge errors aligned to the `docs/conventions.md` error table."""

from typing import Any

ErrorDetails = list[dict[str, str]] | dict[str, Any] | None


class PolicyForgeError(Exception):
    """Base of every typed error; its defaults are the 500 `INTERNAL_ERROR` envelope."""

    code: str = "INTERNAL_ERROR"
    http_status: int = 500

    def __init__(self, message: str, details: ErrorDetails = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: ErrorDetails = details


class ValidationError(PolicyForgeError):
    """Body, query or rule-file validation failed; `details` lists every failing field."""

    code, http_status = "VALIDATION_ERROR", 422


class UnauthenticatedError(PolicyForgeError):
    """Actor headers are missing or carry a role outside `ActorRole`."""

    code, http_status = "UNAUTHENTICATED", 401


class ForbiddenError(PolicyForgeError):
    """The actor's role is not allowed on the route."""

    code, http_status = "FORBIDDEN", 403


class NotFoundError(PolicyForgeError):
    """Unknown resource, or another customer's resource (no existence leak)."""

    code, http_status = "NOT_FOUND", 404


class NoPublishedVersionError(PolicyForgeError):
    """The product has no PUBLISHED rule version; quoting is refused with no fallback."""

    code, http_status = "NO_PUBLISHED_VERSION", 409


class VersionImmutableError(PolicyForgeError):
    """An already PUBLISHED rule version cannot be changed or re-published (NFR-02)."""

    code, http_status = "VERSION_IMMUTABLE", 409


class DraftAlreadyOpenError(PolicyForgeError):
    """The product already has an open DRAFT version."""

    code, http_status = "DRAFT_ALREADY_OPEN", 409


class InvalidPolicyStateException(PolicyForgeError):
    """A disallowed policy transition, or an action on a terminal policy (AC-10)."""

    code, http_status = "INVALID_POLICY_STATE", 409


class InvalidApplicationStateError(PolicyForgeError):
    """The application is not in the status the requested action needs."""

    code, http_status = "INVALID_APPLICATION_STATE", 409


class QuoteStaleError(PolicyForgeError):
    """The quote's rule version is no longer the product's active version."""

    code, http_status = "QUOTE_STALE", 409


class PremiumAlreadyPaidError(PolicyForgeError):
    """A premium payment already exists for that due date."""

    code, http_status = "PREMIUM_ALREADY_PAID", 409


class OutsideRenewalWindowError(PolicyForgeError):
    """Renewal was requested outside the renewal window or after the grace period."""

    code, http_status = "OUTSIDE_RENEWAL_WINDOW", 409


class PremiumFactorNotFoundError(ValidationError):
    """An input matches no band or key of a rating factor; the message names the factor."""
