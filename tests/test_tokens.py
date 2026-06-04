import pytest
from promptlens import count_tokens, context_usage, truncate_to_limit


class TestCountTokensReturnType:
    def test_returns_int(self):
        assert type(count_tokens("hello")) is int

    def test_not_float(self):
        assert not isinstance(count_tokens("hello"), float)


class TestCountTokensEdgeCases:
    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_single_word(self):
        assert count_tokens("hello") == 1

    def test_single_word_with_punctuation(self):
        assert count_tokens("hello,") == 1

    def test_two_words(self):
        assert count_tokens("hello world") == 2

    def test_whitespace_counts_as_chars(self):
        # L'approssimazione conta tutti i caratteri inclusi gli spazi
        # "a  b" = 4 chars → 1 token;  "a b" = 3 chars → 0 token
        assert count_tokens("a  b") == 4 // 4
        assert count_tokens("a b") == 3 // 4

    def test_tabs_and_newlines(self):
        # "a\tb\nc" = 5 chars → 5 // 4 = 1
        assert count_tokens("a\tb\nc") == 1

    def test_only_whitespace(self):
        assert count_tokens("   ") == 0


class TestCountTokensMonotonicity:
    def test_longer_text_has_more_tokens(self):
        short = "Say hello."
        long = "Say hello. " * 10
        assert count_tokens(long) > count_tokens(short)

    def test_appending_long_text_increases_count(self):
        # Con la regola 4-chars/token, aggiungere poche parole non garantisce
        # esattamente +1 token; verifichiamo solo la monotonia su testi lunghi
        base = "The quick brown fox jumps over the lazy dog"
        extended = base * 3
        assert count_tokens(extended) > count_tokens(base)


class TestCountTokensDeterminism:
    def test_same_input_same_output(self):
        text = "You are a helpful assistant. Answer concisely."
        assert count_tokens(text) == count_tokens(text)

    def test_repeated_calls_stable(self):
        text = "What is the capital of France?"
        results = [count_tokens(text) for _ in range(5)]
        assert len(set(results)) == 1


class TestCountTokensRealisticPrompts:
    def test_system_prompt(self):
        prompt = "You are a helpful assistant. Answer concisely and cite your sources."
        assert count_tokens(prompt) > 0

    def test_user_turn(self):
        turn = "What is the capital of France, and what is its population?"
        assert count_tokens(turn) > 0

    def test_multiline_prompt(self):
        # "Line one.\nLine two.\nLine three." = 31 chars → 31 // 4 = 7
        prompt = "Line one.\nLine two.\nLine three."
        assert count_tokens(prompt) == len(prompt) // 4


class TestContextUsage:
    def test_returns_float(self):
        assert isinstance(context_usage("hello world", 100), float)

    def test_empty_text_zero(self):
        assert context_usage("", 1000) == 0.0

    def test_full_window(self):
        # testo da esattamente context_window token → 100.0%
        text = "a" * (8 * 4)   # 8 token (32 chars)
        assert context_usage(text, 8) == pytest.approx(100.0)

    def test_half_window(self):
        text = "a" * (4 * 4)   # 4 token
        assert context_usage(text, 8) == pytest.approx(50.0)

    def test_over_limit_above_100(self):
        text = "a" * (200 * 4)  # 200 token
        assert context_usage(text, 100) > 100.0

    def test_zero_context_window_raises(self):
        with pytest.raises(ValueError):
            context_usage("hello", 0)

    def test_deterministic(self):
        text = "You are a helpful assistant."
        assert context_usage(text, 1000) == context_usage(text, 1000)


class TestTruncateToLimit:
    def test_short_text_unchanged(self):
        text = "Hi"
        assert truncate_to_limit(text, 100) == text

    def test_empty_text_unchanged(self):
        assert truncate_to_limit("", 10) == ""

    def test_truncated_fits_limit(self):
        text = "a" * 100
        result = truncate_to_limit(text, 10)
        assert count_tokens(result) <= 10

    def test_truncated_length(self):
        # max_tokens=5 → max_chars=20; testo da 40 chars → risultato da 20
        text = "a" * 40
        result = truncate_to_limit(text, 5)
        assert len(result) == 20

    def test_exact_limit_unchanged(self):
        text = "a" * 20  # 20 chars = 5 token
        assert truncate_to_limit(text, 5) == text

    def test_returns_string(self):
        assert isinstance(truncate_to_limit("hello world", 2), str)

    def test_unicode_safe(self):
        # emoji = 1 codepoint → conta come 1 char per la regola
        text = "😀" * 20
        result = truncate_to_limit(text, 2)
        assert count_tokens(result) <= 2

