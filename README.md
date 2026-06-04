# PromptGuard

Libreria Python/Rust per l'analisi e la protezione dei prompt LLM.

Il core computazionale è scritto in **Rust** (tramite [PyO3](https://pyo3.rs)) e compilato come estensione nativa con [maturin](https://www.maturin.rs). Il layer Python espone un'API pulita, la logica di tracking e (in futuro) CLI e versioning.

---

## Struttura del progetto

```
promptlens/
│
├── Cargo.toml              # Manifest Rust (crate: promptguard)
├── pyproject.toml          # Config Python/maturin (pacchetto: promptguard)
│
├── rust/                   # Codice Rust — core computazionale
│   └── src/
│       ├── lib.rs          # Entry point PyO3: registra il modulo `_core`
│       ├── tokenizer.rs    # Conteggio token, context usage, truncate
│       └── guardrails.rs   # Rilevamento e redazione PII, regole custom
│
├── python/
│   └── promptguard/        # Pacchetto Python installabile
│       ├── __init__.py     # Re-esporta le API pubbliche
│       ├── tokens.py       # Wrapper Python → _core (tokenizer)
│       ├── guardrails.py   # Wrapper Python → _core (guardrails) + GuardChecker
│       ├── tracker.py      # Logging interazioni LLM (puro Python)
│       ├── prompt.py       # TODO: versioning prompt
│       └── cli.py          # TODO: CLI via Typer
│
├── tests/
│   ├── test_tokens.py      # Test tokenizer
│   ├── test_guardrails.py  # Test PII e regole custom
│   └── test_prompt.py      # Test Tracker
│
└── benchmarks/
    └── bench_tokenizer.py  # TODO: confronto Python puro vs Rust
```

---

## Architettura

```
Python user code
      │
      ▼
promptguard (Python)              ← API, Tracker, GuardChecker
      │
      ▼
promptguard._core (Rust/PyO3)    ← tokenizer, guardrails (parallelizzati con rayon)
```

Il modulo `_core` viene compilato da Rust e installato come shared library (`.pyd` su Windows, `.so` su Linux/macOS). Non va mai importato direttamente: i wrapper in `python/promptguard/` espongono tutto quello che serve.

---

## Setup

**Prerequisiti:** Rust toolchain, Python ≥ 3.8, maturin.

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# oppure: source .venv/bin/activate

pip install maturin pytest
maturin develop               # compila Rust e installa il pacchetto in editable mode
```

---

## API reference

### Tokenizer

```python
from promptguard import count_tokens, context_usage, truncate_to_limit
```

#### `count_tokens(text: str) -> int`

Restituisce il numero di token nel testo (approssimazione: ~4 caratteri Unicode per token).

```python
count_tokens("Hello, world!")   # → 3
count_tokens("")                # → 0
```

#### `context_usage(text: str, context_window: int) -> float`

Restituisce la percentuale della context window occupata dal testo. Valori > 100.0 indicano overflow.

```python
context_usage("Hello, world!", 128_000)   # → 0.002...
context_usage("A" * 4000, 1000)           # → 100.0
```

Lancia `ValueError` se `context_window == 0`.

#### `truncate_to_limit(text: str, max_tokens: int) -> str`

Tronca il testo in modo che `count_tokens(result) <= max_tokens`. Se il testo è già entro il limite, viene restituito invariato.

```python
truncate_to_limit("Hello, world! How are you?", max_tokens=3)
# → "Hello, wo"  (12 chars = 3 tokens * 4)
```

---

### Guardrails

```python
from promptguard import contains_pii, redact_pii, CustomRule, RuleMatch, GuardCore, GuardChecker
```

#### `contains_pii(text: str) -> bool`

Rileva se il testo contiene PII (email, telefono IT, codice fiscale, carta di credito, IBAN, IP, SQL, base64, API key, URL, code block).

```python
contains_pii("mario@example.com")      # → True
contains_pii("The sky is blue")        # → False
```

#### `redact_pii(text: str) -> str`

Sostituisce tutte le PII trovate con `[REDACTED]`.

```python
redact_pii("Call me at +39 333 1234567")
# → "Call me at [REDACTED]"

redact_pii("The sky is blue")
# → "The sky is blue"
```

#### Regole built-in disponibili

| Nome | Cosa rileva |
|---|---|
| `email` | Indirizzi email |
| `phone_it` | Numeri di telefono italiani (fissi e mobili) |
| `phone_international` | Numeri internazionali (formato `+XXXXXXXX`) |
| `fiscal_code_it` | Codici fiscali italiani |
| `credit_card` | Numeri di carta di credito |
| `iban` | Codici IBAN |
| `ip_address` | Indirizzi IPv4 |
| `sql_query` | Query SQL (SELECT, INSERT, UPDATE, DELETE, DROP…) |
| `base64` | Stringhe Base64 (≥ 20 caratteri) |
| `api_key` | Possibili API key (stringhe alfanumeriche ≥ 20 caratteri) |
| `code_block` | Blocchi di codice Markdown (` ``` `) |
| `url` | URL `http://` e `https://` |

#### `CustomRule(name: str, pattern: str)`

Regola personalizzata basata su regex. Il pattern viene validato alla costruzione (lancia `ValueError` se non è valido).

```python
rule = CustomRule(name="ticket_id", pattern=r"TKT-\d{5}")
```

#### `RuleMatch`

Oggetto restituito da `GuardChecker.check()`. Attributi in sola lettura:

| Attributo | Tipo | Descrizione |
|---|---|---|
| `rule_name` | `str` | Nome della regola che ha prodotto il match |
| `matched_value` | `str` | Sottostringa che ha fatto match |
| `start` | `int` | Indice di inizio (byte offset) |
| `end` | `int` | Indice di fine (byte offset) |

```python
match.rule_name      # "email"
match.matched_value  # "mario@example.com"
match.start          # 10
match.end            # 27
```

#### `GuardChecker`

Facade Python di alto livello attorno a `GuardCore`. Supporta regole built-in, regole keyword e regole regex personalizzate.

```python
checker = GuardChecker(rules=["email", "phone_it"])
matches = checker.check("Contact: mario@example.com, +39 333 1234567")
for m in matches:
    print(f"[{m.rule_name}] '{m.matched_value}' at {m.start}:{m.end}")
```

**Regole keyword (content_rules):**

Passa un dict `{categoria: [parole_chiave]}` o il path a un file JSON con la stessa struttura.

```python
checker = GuardChecker(
    rules=["email"],
    content_rules={
        "violence": ["kill", "attack", "destroy"],
        "hate":     ["hate", "slur"],
    },
)
matches = checker.check("I will kill the process")
# → RuleMatch(rule='violence', value='kill', ...)
```

**Regole regex custom:**

```python
checker = GuardChecker(
    rules=["email"],
    custom_rules=[
        CustomRule(name="ticket_id", pattern=r"TKT-\d{5}"),
    ],
)
matches = checker.check("Ref: TKT-00123 — mario@example.com")
```

#### `GuardCore`

Classe Rust esposta direttamente. Equivalente a `GuardChecker` ma senza il supporto al caricamento di `content_rules` da file.

```python
from promptguard import GuardCore, CustomRule

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
from promptguard import Tracker
```

Traccia le interazioni LLM su file JSON. Supporta query per modello e intervallo di date, ed export in JSON o CSV.

#### Inizializzazione

```python
tracker = Tracker(filepath="interactions.json")
# Il file viene creato se non esiste.
# Se esiste ma è corrotto o non è una lista JSON, viene resettato a [].
```

#### `log(model, template, params, rendered, output)`

Aggiunge un record al log. Ogni record ha un `id` UUID e un `timestamp` ISO 8601 (UTC).

```python
tracker.log(
    model="gpt-4o",
    template="Traduci: {text}",
    params={"text": "Hello"},
    rendered="Traduci: Hello",
    output="Ciao",
)
```

Struttura di ogni record nel file JSON:

```json
{
  "id": "a1b2c3d4-...",
  "timestamp": "2026-06-03T10:00:00.000000",
  "model": "gpt-4o",
  "template": "Traduci: {text}",
  "params": {"text": "Hello"},
  "rendered": "Traduci: Hello",
  "output": "Ciao"
}
```

#### `query(model=None, date_from=None, date_to=None) -> list`

Restituisce i record filtrati. Tutti i parametri sono opzionali.

```python
# Tutti i record
all_records = tracker.query()

# Solo gpt-4o
gpt4_records = tracker.query(model="gpt-4o")

# In un intervallo di date (ISO 8601)
records = tracker.query(date_from="2026-01-01", date_to="2026-06-30")
```

#### `export(output_path, format="json")`

Esporta tutti i record in un file. Formati supportati: `"json"` (default) e `"csv"`.

```python
tracker.export("backup.json")
tracker.export("report.csv", format="csv")
```

---

## Comandi utili

### Compilazione

```bash
# Compila Rust e installa il pacchetto in editable mode (debug)
maturin develop

# Con ottimizzazioni release (più lento da compilare, più veloce a runtime)
maturin develop --release

# Build wheel distribuibile (output in dist/)
maturin build --release

# Verifica errori Rust senza compilare (molto più veloce)
cargo check
```

### Test

```bash
# Tutti i test
pytest tests/

# Con output verboso
pytest tests/ -v

# Singolo file
pytest tests/test_tokens.py
pytest tests/test_guardrails.py
pytest tests/test_prompt.py
```

### Pulizia

```bash
# Artefatti Rust
cargo clean

# Windows — cache Python e file compilati
Remove-Item -Recurse -Force python\promptguard\__pycache__
Remove-Item python\promptguard\*.pdb

# Linux/macOS
find python -name "__pycache__" -exec rm -rf {} +

# Pulizia completa (Rust + dist + cache pytest)
cargo clean ; Remove-Item -Recurse -Force dist, .pytest_cache  # Windows
```

---

## Stato dei moduli

| Modulo | Stato | Descrizione |
|---|---|---|
| `tokenizer` | ✅ Implementato | `count_tokens`, `context_usage`, `truncate_to_limit` (Rust) |
| `guardrails` | ✅ Implementato | `contains_pii`, `redact_pii`, `GuardCore`, `GuardChecker`, `CustomRule`, `RuleMatch` (Rust + Python) |
| `tracker` | ✅ Implementato | `Tracker` — logging interazioni LLM su JSON (Python) |
| `prompt` | 🔲 TODO | Versioning e metadati prompt |
| `cli` | 🔲 TODO | Interfaccia a riga di comando (Typer) |
| `diff` | 🔲 TODO | Diff riga per riga tra versioni di prompt |
| `benchmarks` | 🔲 TODO | Confronto Python puro vs Rust tokenizer |

---

## Dipendenze

**Rust** (`Cargo.toml`):
- `pyo3` — binding Python/Rust
- `regex` — motore regex per le guardrails
- `rayon` — parallelismo data-parallel sui match
- `once_cell` — inizializzazione lazy dei pattern compilati

**Python** (`pyproject.toml`):
- nessuna dipendenza runtime
- dev: `pytest`, `maturin`
