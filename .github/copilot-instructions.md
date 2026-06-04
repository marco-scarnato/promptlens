# PromptGuard — Copilot Instructions

## Contesto del progetto

Libreria Python/Rust per l'analisi e la protezione di prompt LLM.
- **Core computazionale**: Rust, esposto a Python tramite PyO3
- **Layer Python**: wrapper, logica di versioning, CLI
- **Build tool**: maturin (compila Rust + installa il pacchetto Python)

## Struttura

```
rust/src/lib.rs          ← entry point PyO3, registra il modulo _core
rust/src/tokenizer.rs    ← conteggio token
rust/src/diff.rs         ← diff tra prompt
rust/src/guardrails.rs   ← rilevamento/redazione PII
python/promptguard/      ← pacchetto Python (python-source = "python")
tests/                   ← pytest
benchmarks/              ← benchmark Python vs Rust
```

## Convenzioni

- Il modulo Rust si chiama `_core` (prefisso `_` = interno, non importare direttamente)
- Ogni file Rust espone una funzione `pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()>`
  che viene chiamata da `lib.rs`
- I wrapper Python in `tokens.py` e `guardrails.py` re-esportano da `_core`
- `__init__.py` espone solo l'API pubblica finale
- File `TODO`-only = non ancora implementato, non aggiungere logica senza che sia richiesta

## Comandi chiave

```bash
maturin develop           # compila Rust + installa editable (da fare dopo ogni modifica .rs)
maturin develop --release # con ottimizzazioni
pytest tests/             # esegui i test
cargo check               # verifica errori Rust senza compilare (più veloce)
cargo clean               # pulisce target/
```

## Dipendenze

- **Rust**: solo `pyo3 = { version = "0.28.3", features = ["extension-module"] }`
- **Python runtime**: nessuna per ora (typer va aggiunto quando si implementa il CLI)
- **Python dev**: `pytest`

## Pattern PyO3 da seguire

```rust
use pyo3::prelude::*;

#[pyfunction]
pub fn mia_funzione(input: &str) -> String {
    // logica
    input.to_uppercase()
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(mia_funzione, m)?)?;
    Ok(())
}
```

## Note operative

- Non aggiungere implementazioni nei file Rust/Python se non esplicitamente richiesto:
  i file TODO devono restare vuoti finché non si lavora su quel modulo
- Dopo ogni modifica a file `.rs` ricordare di eseguire `maturin develop`
- Il file `.pyd` in `python/promptguard/` è generato, non va mai modificato né committato
- I file `.rust-clarify.md` e `.python-library-clarify.md` sono note locali, non sono nel repo
