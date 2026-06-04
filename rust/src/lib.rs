use pyo3::prelude::*;

mod tokenizer;
mod guardrails;

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    tokenizer::register(m)?;
    guardrails::register(m)?;
    Ok(())
}
