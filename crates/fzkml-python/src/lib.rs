//! One bounded immutable byte batch per crossing. No input values are logged.
use fzkml_core::{Batch, ContractError, INPUT_BYTES, evaluate, proof};
use pyo3::{
    exceptions::{PyRuntimeError, PyValueError},
    prelude::*,
    types::PyBytes,
};
use std::panic::{AssertUnwindSafe, catch_unwind};

fn failure(error: ContractError) -> PyErr {
    PyValueError::new_err(error.0)
}
fn safe<T>(operation: impl FnOnce() -> Result<T, ContractError>) -> PyResult<T> {
    catch_unwind(AssertUnwindSafe(operation))
        .map_err(|_| PyRuntimeError::new_err("Rust operation failed; no input details logged"))?
        .map_err(failure)
}
fn batch_copy(input: &Bound<'_, PyBytes>) -> PyResult<Vec<u8>> {
    if input.as_bytes().len() != INPUT_BYTES {
        return Err(PyValueError::new_err("canonical-length"));
    }
    Ok(input.as_bytes().to_vec())
}

#[pyfunction]
fn evaluate_batch(input: &Bound<'_, PyBytes>) -> PyResult<i64> {
    let data = batch_copy(input)?;
    safe(|| evaluate(&Batch::decode(&data)?).map(|v| v.output))
}

#[pyclass(frozen)]
struct ResearchSession {
    inner: proof::ResearchSession,
}
#[pymethods]
impl ResearchSession {
    #[new]
    fn new(py: Python<'_>) -> PyResult<Self> {
        py.allow_threads(|| safe(|| proof::ResearchSession::setup().map(|inner| Self { inner })))
    }
    #[getter]
    fn key_id(&self) -> String {
        self.inner.key_id.clone()
    }
    #[getter]
    fn parameters_id(&self) -> String {
        self.inner.parameters_id.clone()
    }
    fn prove<'py>(
        &self,
        py: Python<'py>,
        input: &Bound<'py, PyBytes>,
    ) -> PyResult<(i64, Bound<'py, PyBytes>, f64, f64)> {
        let data = batch_copy(input)?;
        let result = py.allow_threads(|| safe(|| self.inner.prove(&data)))?;
        Ok((
            result.output,
            PyBytes::new(py, &result.proof),
            result.witness_seconds,
            result.proving_seconds,
        ))
    }
    fn verify(
        &self,
        py: Python<'_>,
        input: &Bound<'_, PyBytes>,
        output: i64,
        proof: &Bound<'_, PyBytes>,
    ) -> PyResult<bool> {
        let data = batch_copy(input)?;
        if proof.as_bytes().len() != 128 {
            return Err(PyValueError::new_err("proof-length"));
        }
        let proof_data = proof.as_bytes().to_vec();
        py.allow_threads(|| safe(|| self.inner.verify(&data, output, &proof_data)))
    }
}

#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(evaluate_batch, m)?)?;
    m.add_class::<ResearchSession>()?;
    m.add("CONTRACT_VERSION", fzkml_core::CONTRACT_VERSION)?;
    m.add("CONTRACT_SHA256", fzkml_core::contract_digest())?;
    Ok(())
}
