from promptguard._core import count_tokens as _count_tokens
from promptguard._core import context_usage as _context_usage
from promptguard._core import truncate_to_limit as _truncate_to_limit


def count_tokens(text: str) -> int:
    """Return the number of tokens in *text* (~4 chars/token approximation)."""
    return int(_count_tokens(text))


def context_usage(text: str, context_window: int) -> float:
    """Return the percentage of *context_window* occupied by *text*.

    Args:
        text: The prompt text.
        context_window: Total token capacity of the model (must be > 0).

    Returns:
        A float in [0.0, +inf).  Values above 100.0 mean the text exceeds
        the context window.

    Raises:
        ValueError: If *context_window* is 0.
    """
    return float(_context_usage(text, context_window))


def truncate_to_limit(text: str, max_tokens: int) -> str:
    """Return *text* truncated so that ``count_tokens(result) <= max_tokens``.

    If the text already fits, it is returned unchanged.
    """
    return str(_truncate_to_limit(text, max_tokens))

