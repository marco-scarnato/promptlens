use pyo3::prelude::*;

mod guardrails;

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    guardrails::register(m)?;
    Ok(())
}
