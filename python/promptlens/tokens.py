def count_tokens(text: str) -> int:
    """Return the number of tokens in *text* (~4 chars/token approximation)."""
    return len(text) // 4


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
    if context_window == 0:
        raise ValueError("context_window must be greater than 0")
    return (len(text) // 4) / context_window * 100.0


def truncate_to_limit(text: str, max_tokens: int) -> str:
    """Return *text* truncated so that ``count_tokens(result) <= max_tokens``.

    If the text already fits, it is returned unchanged.
    """
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars]

