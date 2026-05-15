_PHRASES = ["be quick", "just do it", "trivial fix"]


def has_override(message: str) -> bool:
    """Return True if message contains an intentional bypass phrase."""
    lower = message.lower()
    return any(phrase in lower for phrase in _PHRASES)
