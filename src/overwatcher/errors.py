"""Named exceptions. `except Exception` without a named class is a code smell — forbidden."""


class OverwatcherError(Exception):
    """Base for all app-level errors."""


class TwilioSignatureError(OverwatcherError):
    """Inbound webhook signature missing or invalid."""


class DuplicateMessageError(OverwatcherError):
    """Same Twilio MessageSid seen twice."""


class PhoneNumberMismatch(OverwatcherError):
    """Inbound From != configured USER_PHONE."""


class QuietWindowActive(OverwatcherError):
    """Command received while user is in a declared quiet window."""


class ClassificationSchemaError(OverwatcherError):
    """LLM returned output that didn't parse against the classifier schema."""


class LLMTimeoutError(OverwatcherError):
    """All providers in the fallback chain timed out."""
