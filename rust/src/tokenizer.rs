use pyo3::prelude::*;

// Logica interna condivisa: ~4 caratteri Unicode per token (floor).
fn token_count(text: &str) -> usize {
    text.chars().count() / 4
}

// ── count_tokens ─────────────────────────────────────────────────────────────
#[pyfunction]
pub fn count_tokens(text: &str) -> usize {
    token_count(text)
}

// ── context_usage ─────────────────────────────────────────────────────────────
// Restituisce la percentuale di context window occupata dal testo (0.0–100.0+).
// Errore se context_window == 0 (divisione per zero).
#[pyfunction]
pub fn context_usage(text: &str, context_window: usize) -> PyResult<f64> {
    if context_window == 0 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "context_window must be greater than 0",
        ));
    }
    Ok((token_count(text) as f64 / context_window as f64) * 100.0)
}

// ── truncate_to_limit ─────────────────────────────────────────────────────────
// Tronca il testo in modo che count_tokens(result) <= max_tokens.
// Con la regola 4-chars/token: mantiene i primi max_tokens * 4 codepoint.
// Se il testo è già entro il limite lo restituisce invariato.
#[pyfunction]
pub fn truncate_to_limit(text: &str, max_tokens: usize) -> String {
    let max_chars = max_tokens * 4;
    if text.chars().count() <= max_chars {
        return text.to_string();
    }
    text.chars().take(max_chars).collect()
}

// ── register ──────────────────────────────────────────────────────────────────
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(count_tokens, m)?)?;
    m.add_function(wrap_pyfunction!(context_usage, m)?)?;
    m.add_function(wrap_pyfunction!(truncate_to_limit, m)?)?;
    Ok(())
}
