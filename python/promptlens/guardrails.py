from __future__ import annotations

import json
from typing import Optional

from promptlens._core import contains_pii as _contains_pii
from promptlens._core import redact_pii as _redact_pii
from promptlens._core import CustomRule, RuleMatch, GuardCore


# ── Convenience wrappers ──────────────────────────────────────────────────────

def contains_pii(text: str) -> bool:
    """Return True if *text* contains detectable PII."""
    return bool(_contains_pii(text))


def redact_pii(text: str) -> str:
    """Return *text* with PII replaced by '[REDACTED]'."""
    return str(_redact_pii(text))


# ── GuardChecker — high-level Python facade ───────────────────────────────────

class GuardChecker:
    """High-level facade around GuardCore.

    Args:
        rules:         Built-in rule names to enable.
        content_rules: Path to a JSON file **or** a dict mapping
                       category names to keyword lists.
        custom_rules:  List of ``CustomRule`` instances.

    Example::

        checker = GuardChecker(
            rules=["email", "phone_it"],
            content_rules={"violence": ["kill", "attack"]},
        )
        matches = checker.check("Call me at mario@example.com")
    """

    def __init__(
        self,
        rules: list[str],
        content_rules: Optional[dict[str, list[str]] | str] = None,
        custom_rules: Optional[list[CustomRule]] = None,
    ) -> None:
        # Accept a file path string or an already-parsed dict
        parsed_content: Optional[dict[str, list[str]]] = None
        if isinstance(content_rules, str):
            with open(content_rules, encoding="utf-8") as f:
                parsed_content = json.load(f)
        elif content_rules is not None:
            parsed_content = content_rules

        self._core = GuardCore(
            rules=rules,
            content_rules=parsed_content,
            custom_rules=custom_rules,
        )

    def check(self, text: str) -> list[RuleMatch]:
        """Run all enabled rules against *text*.

        Returns:
            List of :class:`RuleMatch` sorted by start position.
        """
        return self._core.check(text)


__all__ = [
    "contains_pii",
    "redact_pii",
    "CustomRule",
    "RuleMatch",
    "GuardCore",
    "GuardChecker",
]

