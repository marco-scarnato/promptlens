import pytest
from promptguard import contains_pii, redact_pii, CustomRule, RuleMatch, GuardChecker


# ── contains_pii / redact_pii (convenience wrappers) ─────────────────────────

class TestContainsPiiReturnType:
    def test_returns_bool(self):
        assert isinstance(contains_pii("hello"), bool)

    def test_not_int(self):
        assert type(contains_pii("hello")) is bool


class TestContainsPiiDetection:
    def test_email_detected(self):
        assert contains_pii("mario@example.com") is True

    def test_phone_it_detected(self):
        assert contains_pii("+39 333 1234567") is True

    def test_neutral_text_clean(self):
        assert contains_pii("The sky is blue") is False

    def test_empty_string_clean(self):
        assert contains_pii("") is False

    def test_mixed_text_detected(self):
        assert contains_pii("Contact me at mario@example.com for details") is True


class TestContainsPiiDeterminism:
    def test_repeated_calls_stable(self):
        text = "mario@example.com"
        results = [contains_pii(text) for _ in range(5)]
        assert len(set(results)) == 1


class TestRedactPiiReturnType:
    def test_returns_str(self):
        assert isinstance(redact_pii("hello"), str)


class TestRedactPiiRedaction:
    def test_email_redacted(self):
        result = redact_pii("email: mario@example.com")
        assert "mario@example.com" not in result

    def test_phone_redacted(self):
        result = redact_pii("call +39 333 1234567")
        assert "+39 333 1234567" not in result

    def test_clean_text_unchanged(self):
        assert redact_pii("The sky is blue") == "The sky is blue"

    def test_empty_string_unchanged(self):
        assert redact_pii("") == ""

    def test_redacted_contains_no_pii(self):
        result = redact_pii("mario@example.com and +39 333 1234567")
        assert contains_pii(result) is False

    def test_deterministic(self):
        text = "mario@example.com"
        assert redact_pii(text) == redact_pii(text)


# ── RuleMatch ─────────────────────────────────────────────────────────────────

class TestRuleMatch:
    def _make_match(self):
        checker = GuardChecker(rules=["email"])
        matches = checker.check("write to mario@example.com please")
        assert matches, "no match found"
        return matches[0]

    def test_has_rule_name(self):
        m = self._make_match()
        assert m.rule_name == "email"

    def test_has_matched_value(self):
        m = self._make_match()
        assert m.matched_value == "mario@example.com"

    def test_has_start(self):
        m = self._make_match()
        assert isinstance(m.start, int)
        assert m.start >= 0

    def test_has_end(self):
        m = self._make_match()
        assert isinstance(m.end, int)
        assert m.end > m.start

    def test_repr(self):
        m = self._make_match()
        r = repr(m)
        assert "RuleMatch" in r
        assert "email" in r
        assert "mario@example.com" in r


# ── CustomRule ────────────────────────────────────────────────────────────────

class TestCustomRule:
    def test_create_valid(self):
        rule = CustomRule(name="secret", pattern=r"secret-\w+")
        assert rule.name == "secret"
        assert rule.pattern == r"secret-\w+"

    def test_invalid_pattern_raises(self):
        with pytest.raises(Exception):
            CustomRule(name="bad", pattern=r"[invalid")

    def test_repr(self):
        rule = CustomRule(name="secret", pattern=r"secret-\w+")
        assert "CustomRule" in repr(rule)
        assert "secret" in repr(rule)


# ── GuardChecker ──────────────────────────────────────────────────────────────

class TestGuardCheckerBuiltinRules:
    def test_email_match(self):
        checker = GuardChecker(rules=["email"])
        matches = checker.check("Send to alice@example.com")
        assert any(m.rule_name == "email" for m in matches)

    def test_phone_it_match(self):
        checker = GuardChecker(rules=["phone_it"])
        matches = checker.check("Chiamami al 333 1234567")
        assert any(m.rule_name == "phone_it" for m in matches)

    def test_url_match(self):
        checker = GuardChecker(rules=["url"])
        matches = checker.check("Visit https://example.com for info")
        assert any(m.rule_name == "url" for m in matches)

    def test_sql_match(self):
        checker = GuardChecker(rules=["sql_query"])
        matches = checker.check("SELECT * FROM users")
        assert any(m.rule_name == "sql_query" for m in matches)

    def test_ip_address_match(self):
        checker = GuardChecker(rules=["ip_address"])
        matches = checker.check("Server at 192.168.1.1 is down")
        assert any(m.rule_name == "ip_address" for m in matches)

    def test_no_match_clean_text(self):
        checker = GuardChecker(rules=["email", "phone_it"])
        matches = checker.check("The sky is blue")
        assert matches == []

    def test_unknown_rule_raises(self):
        with pytest.raises(Exception):
            GuardChecker(rules=["not_a_real_rule"])

    def test_empty_text_no_matches(self):
        checker = GuardChecker(rules=["email", "phone_it", "url"])
        assert checker.check("") == []

    def test_results_sorted_by_start(self):
        checker = GuardChecker(rules=["email", "url"])
        text = "Visit https://example.com or write to bob@test.com"
        matches = checker.check(text)
        starts = [m.start for m in matches]
        assert starts == sorted(starts)

    def test_multiple_rules_same_check(self):
        checker = GuardChecker(rules=["email", "phone_it"])
        matches = checker.check("mario@example.com and 333 1234567")
        rule_names = {m.rule_name for m in matches}
        assert "email" in rule_names
        assert "phone_it" in rule_names


class TestGuardCheckerCustomRules:
    def test_custom_rule_match(self):
        rule = CustomRule(name="secret_key", pattern=r"sk-[A-Za-z0-9]+")
        checker = GuardChecker(rules=[], custom_rules=[rule])
        matches = checker.check("token: sk-abcDEF123")
        assert any(m.rule_name == "secret_key" for m in matches)

    def test_custom_rule_no_match(self):
        rule = CustomRule(name="secret_key", pattern=r"sk-[A-Za-z0-9]+")
        checker = GuardChecker(rules=[], custom_rules=[rule])
        assert checker.check("nothing here") == []


class TestGuardCheckerContentRules:
    def test_keyword_match(self):
        checker = GuardChecker(
            rules=[],
            content_rules={"violence": ["kill", "attack"]},
        )
        matches = checker.check("I will attack the system")
        assert any(m.rule_name == "violence" for m in matches)

    def test_keyword_case_insensitive(self):
        checker = GuardChecker(
            rules=[],
            content_rules={"violence": ["Kill"]},
        )
        matches = checker.check("you should kill all processes")
        assert any(m.rule_name == "violence" for m in matches)

    def test_keyword_no_match(self):
        checker = GuardChecker(
            rules=[],
            content_rules={"violence": ["kill", "attack"]},
        )
        assert checker.check("everything is fine") == []

