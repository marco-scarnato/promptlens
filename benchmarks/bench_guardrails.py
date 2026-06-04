"""
Benchmark: guardrails — Rust (via promptlens._core) vs Python pure implementation.

Run with:
    python benchmarks/bench_guardrails.py
"""

import re
import timeit

from promptlens import GuardChecker, contains_pii, redact_pii

# ---------------------------------------------------------------------------
# Test corpus
# ---------------------------------------------------------------------------

TEXTS = {
    "small":  "Hello world! " * 10,
    "medium": "Hello world! " * 250,
    "large":  "Hello world! " * 8_000,
    "xlarge": "Hello world! " * 32_000,
}

MEDIUM_TEXT = TEXTS["medium"]

ALL_RULES = [
    "email", "phone_it", "phone_international", "fiscal_code_it",
    "credit_card", "iban", "ip_address", "sql_query",
    "base64", "api_key", "url", "code_block",
]

REPEAT_SMALL = 500
REPEAT_LARGE = 50

# ---------------------------------------------------------------------------
# Python-pure baseline — same patterns used by the Rust core
# ---------------------------------------------------------------------------

_PII_PATTERNS = [
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    r"(?:\+39[\s\-]?)?(?:0\d{1,4}[\s\-]?\d{4,8}|3\d{2}[\s\-]?\d{6,7})",
    r"\+[1-9]\d{6,14}\b",
    r"[A-Za-z]{6}\d{2}[A-Za-z]\d{2}[A-Za-z]\d{3}[A-Za-z]",
    r"\b(?:\d[ \-]?){12,15}\d\b",
    r"\b[A-Z]{2}\d{2}[A-Z0-9]{1,30}\b",
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b",
    r"\b(?:SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b",
    r"https?://[^\s]+",
]
_PII_RES = [re.compile(p, re.IGNORECASE) for p in _PII_PATTERNS]


def _contains_pii_py(text: str) -> bool:
    return any(r.search(text) for r in _PII_RES)


def _redact_pii_py(text: str) -> str:
    for r in _PII_RES:
        text = r.sub("[REDACTED]", text)
    return text


def _n(name: str) -> int:
    return REPEAT_LARGE if name in ("large", "xlarge") else REPEAT_SMALL


# ---------------------------------------------------------------------------
# 1. contains_pii — Rust vs Python
# ---------------------------------------------------------------------------

print("=" * 65)
print("contains_pii — Rust vs Python")
print("=" * 65)
print(f"{'size':<8} {'n':>6} {'Rust (ms)':>12} {'Python (ms)':>12} {'speedup':>9}")
print("-" * 65)

for name, text in TEXTS.items():
    n = _n(name)
    rust_t = timeit.timeit(lambda t=text: contains_pii(t), number=n)
    py_t   = timeit.timeit(lambda t=text: _contains_pii_py(t), number=n)
    speedup = py_t / rust_t if rust_t > 0 else float("inf")
    print(f"{name:<8} {n:>6} {rust_t*1000:>12.2f} {py_t*1000:>12.2f} {speedup:>8.1f}x")

# ---------------------------------------------------------------------------
# 2. redact_pii — Rust vs Python
# ---------------------------------------------------------------------------

print()
print("=" * 65)
print("redact_pii — Rust vs Python")
print("=" * 65)
print(f"{'size':<8} {'n':>6} {'Rust (ms)':>12} {'Python (ms)':>12} {'speedup':>9}")
print("-" * 65)

for name, text in TEXTS.items():
    n = _n(name)
    rust_t = timeit.timeit(lambda t=text: redact_pii(t), number=n)
    py_t   = timeit.timeit(lambda t=text: _redact_pii_py(t), number=n)
    speedup = py_t / rust_t if rust_t > 0 else float("inf")
    print(f"{name:<8} {n:>6} {rust_t*1000:>12.2f} {py_t*1000:>12.2f} {speedup:>8.1f}x")

# ---------------------------------------------------------------------------
# 3. GuardChecker [Rust] — throughput across text sizes
# ---------------------------------------------------------------------------

RULES_6 = ["email", "phone_it", "credit_card", "iban", "ip_address", "url"]
checker_6 = GuardChecker(rules=RULES_6)

print()
print("=" * 65)
print(f"GuardChecker.check() [Rust] — {len(RULES_6)} rules")
print("=" * 65)
print(f"{'size':<8} {'n':>6} {'total (ms)':>12} {'per call (us)':>14}")
print("-" * 65)

for name, text in TEXTS.items():
    n = _n(name)
    t = timeit.timeit(lambda t=text: checker_6.check(t), number=n)
    print(f"{name:<8} {n:>6} {t*1000:>12.2f} {t/n*1e6:>14.1f}")

# ---------------------------------------------------------------------------
# 4. GuardChecker [Rust] — impact of number of rules (medium text)
# ---------------------------------------------------------------------------

RULE_SETS = {
    "1 rule":   ALL_RULES[:1],
    "3 rules":  ALL_RULES[:3],
    "6 rules":  ALL_RULES[:6],
    "12 rules": ALL_RULES,
}

print()
print("=" * 65)
print(f"GuardChecker [Rust] — number of rules (medium text, n={REPEAT_SMALL})")
print("=" * 65)
print(f"{'rules':<12} {'total (ms)':>12} {'per call (us)':>14}")
print("-" * 65)

for label, rules in RULE_SETS.items():
    c = GuardChecker(rules=rules)
    t = timeit.timeit(lambda c=c: c.check(MEDIUM_TEXT), number=REPEAT_SMALL)
    print(f"{label:<12} {t*1000:>12.2f} {t/REPEAT_SMALL*1e6:>14.1f}")

# ---------------------------------------------------------------------------
# 5. GuardChecker [Rust] — match density: PII-heavy vs clean text
# ---------------------------------------------------------------------------

DENSE_PII = (
    "Contact mario@example.com or luigi@test.it. "
    "Call +39 333 1234567 or +39 02 12345678. "
    "CC: 4111 1111 1111 1111. IBAN: IT60X0542811101000000123456. "
    "IP: 192.168.1.1. Visit https://example.com/path?q=1. "
) * 50

CLEAN_TEXT = "The quick brown fox jumps over the lazy dog. " * 100

checker_all = GuardChecker(rules=ALL_RULES)
matches_dense = len(checker_all.check(DENSE_PII))
matches_clean = len(checker_all.check(CLEAN_TEXT))

print()
print("=" * 65)
print(f"GuardChecker [Rust] — match density (12 rules, n={REPEAT_SMALL})")
print("=" * 65)
t_dense = timeit.timeit(lambda: checker_all.check(DENSE_PII), number=REPEAT_SMALL)
t_clean = timeit.timeit(lambda: checker_all.check(CLEAN_TEXT), number=REPEAT_SMALL)
print(f"{'PII-heavy':<12} {t_dense*1000:>10.2f} ms  {matches_dense:>4} matches  ({t_dense/REPEAT_SMALL*1e6:.1f} us/call)")
print(f"{'clean':<12} {t_clean*1000:>10.2f} ms  {matches_clean:>4} matches  ({t_clean/REPEAT_SMALL*1e6:.1f} us/call)")

print()
