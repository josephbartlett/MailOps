"""Custom exceptions for MailOps."""


class MailOpsError(Exception):
    """Base exception for package-specific failures."""


class ConfigurationError(MailOpsError):
    """Raised when runtime configuration is invalid."""


class AdapterError(MailOpsError):
    """Raised when a provider adapter fails."""


class PolicyError(MailOpsError):
    """Raised when an action violates local policy."""


class ReviewRequiredError(MailOpsError):
    """Raised when an action requires review before execution."""

