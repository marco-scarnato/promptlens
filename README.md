# PromptLens

[![PyPI version](https://img.shields.io/pypi/v/promptlens.svg)](https://pypi.org/project/promptlens/)
[![Python versions](https://img.shields.io/pypi/pyversions/promptlens.svg)](https://pypi.org/project/promptlens/)
[![License](https://img.shields.io/pypi/l/promptlens.svg)](https://github.com/marco-scarnato/promptlens/blob/main/LICENSE)
[![CI](https://github.com/marco-scarnato/promptlens/actions/workflows/CI.yml/badge.svg)](https://github.com/marco-scarnato/promptlens/actions)

**PromptLens** is a Python library for LLM prompt analysis and protection.

- **Tokenizer** — fast token counting, context window usage and truncation (pure Python)
- **Guardrails** — PII detection and redaction with built-in and custom rules (Rust core via [PyO3](https://pyo3.rs))
- **Tracker** — log, query and export LLM interactions to JSON/CSV (pure Python)

---

## Installation

```bash
pip install promptlens
```

Python ≥ 3.8 required. No runtime dependencies.

---

---

## Quick start

```python
from promptlens import count_tokens, context_usage, truncate_to_limit
from promptlens import contains_pii, redact_pii, GuardChecker, CustomRule
from promptlens import Tracker

# --- Tokenizer ---
text = "The quick brown fox jumps over the lazy dog."

print(count_tokens(text))               # → 11
print(context_usage(text, 128_000))     # → 0.0085...

short = truncate_to_limit(text, max_tokens=5)
print(short)                            # → "The quick br"

# --- Guardrails ---
print(contains_pii("user@example.com"))          # → True
print(redact_pii("Call +39 333 1234567"))        # → "Call [REDACTED]"

checker = GuardChecker(
    rules=["email"],
    content_rules={"sensitive": ["confidential", "secret"]},
    custom_rules=[CustomRule("ticket", r"TKT-\d{5}")],
)
for m in checker.check("Send TKT-00123 to user@example.com"):
    print(m.rule_name, m.matched_value)

# --- Tracker ---
tracker = Tracker("interactions.json")
tracker.log(
    model="gpt-4o",
    template="Translate: {text}",
    params={"text": "Hello"},
    rendered="Translate: Hello",
    output="Ciao",
)
records = tracker.query(model="gpt-4o")
tracker.export("report.csv", format="csv")
```

---

## API reference

### Tokenizer

```python
from promptlens import count_tokens, context_usage, truncate_to_limit
```

Token count is approximated as `len(text) // 4` (one token ≈ 4 characters).

#### `count_tokens(text: str) -> int`

Returns the estimated number of tokens in `text`.

```python
count_tokens("Hello, world!")   # → 3
count_tokens("")                # → 0
```

#### `context_usage(text: str, context_window: int) -> float`

Returns the percentage of `context_window` used by `text`. Values above 100.0 indicate the text exceeds the window. Raises `ValueError` if `context_window` is 0.

```python
context_usage("Hello, world!", 128_000)   # → 0.002...
context_usage("A" * 512_000, 128_000)     # → 100.0+
```

#### `truncate_to_limit(text: str, max_tokens: int) -> str`

Returns `text` truncated so that `count_tokens(result) <= max_tokens`. Returns the original string unchanged if it already fits.

```python
truncate_to_limit("Hello, world! How are you?", max_tokens=3)
# → "Hello, wo"  (12 chars = 3 tokens × 4)
```

---

### Guardrails

```python
from promptlens import contains_pii, redact_pii, CustomRule, RuleMatch, GuardCore, GuardChecker
```

The guardrails engine is implemented in Rust using parallel regex matching via [rayon](https://github.com/rayon-rs/rayon).

#### `contains_pii(text: str) -> bool`

Returns `True` if `text` contains any detectable PII.

```python
contains_pii("mario@example.com")   # → True
contains_pii("The sky is blue")     # → False
```

#### `redact_pii(text: str) -> str`

Replaces all PII found in `text` with `[REDACTED]`.

```python
redact_pii("Call me at +39 333 1234567")
# → "Call me at [REDACTED]"
```

#### Built-in rules

| Rule name | Detects |
|---|---|
| `email` | Email addresses |
| `phone_it` | Italian phone numbers (landline and mobile) |
| `phone_international` | International numbers (`+XXXXXXXX` format) |
| `fiscal_code_it` | Italian fiscal codes |
| `credit_card` | Credit card numbers |
| `iban` | IBAN codes |
| `ip_address` | IPv4 addresses |
| `sql_query` | SQL statements (SELECT, INSERT, UPDATE, DELETE, DROP…) |
| `base64` | Base64 strings (≥ 20 characters) |
| `api_key` | Potential API keys (alphanumeric strings ≥ 20 characters) |
| `code_block` | Markdown code blocks (` ``` `) |
| `url` | `http://` and `https://` URLs |

#### `CustomRule(name: str, pattern: str)`

A custom regex-based rule. The pattern is validated at construction time and raises `ValueError` if invalid.

```python
rule = CustomRule(name="ticket_id", pattern=r"TKT-\d{5}")
```

#### `RuleMatch`

Returned by `GuardChecker.check()`. Read-only attributes:

| Attribute | Type | Description |
|---|---|---|
| `rule_name` | `str` | Name of the rule that matched |
| `matched_value` | `str` | The matched substring |
| `start` | `int` | Start byte offset |
| `end` | `int` | End byte offset |

#### `GuardChecker`

High-level Python facade around `GuardCore`. Supports built-in rules, keyword rules and custom regex rules. The `content_rules` argument accepts either a `dict` or a path to a JSON file with the same structure.

```python
checker = GuardChecker(rules=["email", "phone_it"])
matches = checker.check("Contact: mario@example.com, +39 333 1234567")
for m in matches:
    print(f"[{m.rule_name}] '{m.matched_value}' at {m.start}:{m.end}")
```

**Keyword rules:**

```python
checker = GuardChecker(
    rules=["email"],
    content_rules={
        "violence": ["kill", "attack", "destroy"],
        "hate":     ["hate", "slur"],
    },
)
matches = checker.check("I will kill the process")
```

**Custom regex rules:**

```python
checker = GuardChecker(
    rules=["email"],
    custom_rules=[CustomRule(name="ticket_id", pattern=r"TKT-\d{5}")],
)
matches = checker.check("Ref: TKT-00123 — mario@example.com")
```

#### `GuardCore`

The Rust class exposed directly. Equivalent to `GuardChecker` but without file-based loading for `content_rules`.

```python
from promptlens import GuardCore, CustomRule

core = GuardCore(
    rules=["email", "ip_address"],
    content_rules={"sensitive": ["confidential", "secret"]},
    custom_rules=[CustomRule("order_id", r"ORD-\d+")],
)
matches = core.check("SECRET order ORD-999 from 192.168.1.1")
```

---

### Tracker

```python
from promptlens import Tracker
```

Logs LLM interactions to a JSON file. Supports filtering by model and date range, and exporting to JSON or CSV.

#### Initialisation

```python
tracker = Tracker(filepath="interactions.json")
# File is created as an empty array if it does not exist.
# If the file exists but is corrupted, it is reset to [].
```

#### `log(model, template, params, rendered, output)`

Appends a new record. Each record receives a UUID `id` and a UTC ISO 8601 `timestamp`.

```python
tracker.log(
    model="gpt-4o",
    template="Translate: {text}",
    params={"text": "Hello"},
    rendered="Translate: Hello",
    output="Ciao",
)
```

Record structure:

```json
{
  "id": "a1b2c3d4-...",
  "timestamp": "2026-06-04T10:00:00.000000+00:00",
  "model": "gpt-4o",
  "template": "Translate: {text}",
  "params": {"text": "Hello"},
  "rendered": "Translate: Hello",
  "output": "Ciao"
}
```

#### `query(model=None, date_from=None, date_to=None) -> list`

Returns filtered records. All parameters are optional.

```python
all_records  = tracker.query()
gpt4_records = tracker.query(model="gpt-4o")
date_records = tracker.query(date_from="2026-01-01", date_to="2026-12-31")
```

#### `export(output_path, format="json")`

Exports all records to a file. Supported formats: `"json"` (default) and `"csv"`.

```python
tracker.export("backup.json")
tracker.export("report.csv", format="csv")
```

---

## Development

**Prerequisites:** Rust toolchain, Python ≥ 3.8, [maturin](https://www.maturin.rs).

```bash
git clone https://github.com/marco-scarnato/promptlens.git
cd promptlens

python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install maturin pytest
maturin develop          # compile Rust and install in editable mode
```

```bash
# Run tests
pytest tests/

# Check Rust without compiling (faster)
cargo check

# Release build
maturin develop --release
```

---

## Dependencies

**Rust** (guardrails core):
- [`pyo3`](https://pyo3.rs) — Python/Rust bindings
- [`regex`](https://docs.rs/regex) — regex engine for PII rules
- [`rayon`](https://docs.rs/rayon) — data-parallel matching
- [`once_cell`](https://docs.rs/once_cell) — lazy pattern initialisation

**Python**: no runtime dependencies.

---

## License

[Apache 2.0](LICENSE)
