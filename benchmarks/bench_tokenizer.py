"""
Benchmark: tokenizer — Python pure implementation performance.

Tests: count_tokens, context_usage, truncate_to_limit.

Run with:
    python benchmarks/bench_tokenizer.py
"""

import timeit

from promptlens import count_tokens, context_usage, truncate_to_limit

# ---------------------------------------------------------------------------
# Test corpus
# ---------------------------------------------------------------------------

TEXTS = {
    "small":  "Hello world! " * 10,        # ~30 tokens
    "medium": "Hello world! " * 250,       # ~750 tokens
    "large":  "Hello world! " * 8_000,     # ~24k tokens
    "xlarge": "Hello world! " * 32_000,    # ~96k tokens
}

REPEAT = 1_000
CONTEXT_WINDOW = 128_000   # typical large-model context window


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _bench(label: str, fn, texts: dict, repeat: int, extra_col: str | None = None) -> None:
    col_extra = f" {extra_col:>10}" if extra_col else ""
    width = 55 + (11 if extra_col else 0)
    print("=" * width)
    print(f"{label}")
    print("=" * width)
    print(f"{'size':<8} {'n':>6}{col_extra} {'ms/call':>10} {'calls/s':>12}")
    print("-" * width)
    for name, text in texts.items():
        t = timeit.timeit(lambda v=text: fn(v), number=repeat)
        ms_per_call = t * 1000 / repeat
        calls_per_s = repeat / t
        extra_val = f" {extra_col:>10}" if extra_col else ""
        print(f"{name:<8} {repeat:>6}{extra_val} {ms_per_call:>10.4f} {calls_per_s:>12,.0f}")
    print()


# ---------------------------------------------------------------------------
# 1. count_tokens
# ---------------------------------------------------------------------------

_bench("count_tokens", count_tokens, TEXTS, REPEAT)

# ---------------------------------------------------------------------------
# 2. context_usage
# ---------------------------------------------------------------------------

_bench(
    f"context_usage  (window={CONTEXT_WINDOW:,})",
    lambda t: context_usage(t, CONTEXT_WINDOW),
    TEXTS,
    REPEAT,
)

# ---------------------------------------------------------------------------
# 3. truncate_to_limit — truncate to half the token count of each text
# ---------------------------------------------------------------------------

HALF_LIMITS = {
    name: max(1, count_tokens(text) // 2)
    for name, text in TEXTS.items()
}

print("=" * 66)
print("truncate_to_limit  (limit = half the text tokens)")
print("=" * 66)
print(f"{'size':<8} {'n':>6} {'max_tok':>8} {'ms/call':>10} {'calls/s':>12}")
print("-" * 66)

for name, text in TEXTS.items():
    limit = HALF_LIMITS[name]
    t = timeit.timeit(lambda v=text, l=limit: truncate_to_limit(v, l), number=REPEAT)
    ms_per_call = t * 1000 / REPEAT
    calls_per_s = REPEAT / t
    print(f"{name:<8} {REPEAT:>6} {limit:>8,} {ms_per_call:>10.4f} {calls_per_s:>12,.0f}")

print()

