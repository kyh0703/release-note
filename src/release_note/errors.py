class ReleaseNoteError(Exception):
    """Base exception for release-note failures."""


class ConfigError(ReleaseNoteError):
    """Raised when required configuration is missing or invalid."""


class ApiError(ReleaseNoteError):
    """Raised when an upstream API returns an unexpected response."""


class NotFoundError(ReleaseNoteError):
    """Raised when a requested upstream resource cannot be found."""


class NotificationError(ReleaseNoteError):
    """Raised when notification delivery fails."""
