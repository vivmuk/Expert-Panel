class VeniceError(Exception):
    """Non-retryable Venice API failure."""

    def __init__(self, message, status=None, body=None):
        super().__init__(message)
        self.status = status
        self.body = body


class RetryableVeniceError(VeniceError):
    """A received HTTP status that this client may retry inside one call."""


class AmbiguousSend(Exception):
    """The request may have been accepted and no complete response came back.

    This is not a VeniceError. Callers must not start a repair or thinking retry
    after it.
    """


SPEND_LIMIT_REPLY = (
    "The AI model's spending limit has been reached, so this run can't finish right now. "
    "Your answers are saved."
)


def out_of_credit(exc):
    """True when Venice refused the call with 402 Payment Required, anywhere in the cause chain."""
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, VeniceError) and exc.status == 402:
            return True
        exc = exc.__cause__ or exc.__context__
    return False
