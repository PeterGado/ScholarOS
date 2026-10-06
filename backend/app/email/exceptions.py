from app.core.exceptions import ScholarOSError


class EmailSendError(ScholarOSError):
    """Raised when an email genuinely fails to send: missing configuration, a network error,
    or a non-2xx response from the provider. Unlike app.ai.wikipedia/app.ai.crossref (optional
    enrichment that silently returns None on failure), a password-reset email's delivery *is*
    the feature - a caller that swallowed this exception would silently leave a user with no
    way to know their reset request went nowhere. Never includes the API key in its message.
    """
