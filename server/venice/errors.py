class VeniceError(Exception):
    """Non-retryable Venice API failure."""

    def __init__(self, message, status=None, body=None):
        super().__init__(message)
        self.status = status
        self.body = body


class RetryableVeniceError(VeniceError):
    """Transient failure (429/5xx/timeouts) worth retrying with backoff."""
