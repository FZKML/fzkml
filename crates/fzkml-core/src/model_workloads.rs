//! Bounded research relations for the synthetic M5 model workloads.
use crate::{
    ContractError,
    proof::{bound, field, rounded},
    round_even,
};
use ark_bn254::{Bn254, Fr};
use ark_crypto_primitives::crh::sha256::constraints::Sha256Gadget;
use ark_groth16::{Groth16, PreparedVerifyingKey, Proof, ProvingKey, prepare_verifying_key};
use ark_r1cs_std::{
    alloc::AllocVar, boolean::Boolean, convert::ToBitsGadget, eq::EqGadget, fields::fp::FpVar,
    uint8::UInt8,
};
use ark_relations::r1cs::{
    ConstraintSynthesizer, ConstraintSystem, ConstraintSystemRef, SynthesisError,
};
use ark_serialize::{CanonicalDeserialize, CanonicalSerialize};
use rand::{RngCore, rngs::OsRng};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::time::Instant;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Relation {
    Median,
    Inference,
    Train,
}

impl Relation {
    fn tag(self) -> &'static [u8; 8] {
        match self {
            Self::Median => b"FZKM5MD1",
            Self::Inference => b"FZKM5IF1",
            Self::Train => b"FZKM5TR1",
        }
    }

    fn bounds(self) -> &'static [(i64, i64)] {
        match self {
            Self::Median => &[(-4, 4); 10],
            Self::Inference => &[(-4, 4), (-4, 4), (-4, 4), (-4, 4), (-2, 2)],
            Self::Train => &[(-4, 4), (-4, 4), (-4, 4), (-4, 4), (-2, 2), (-1, 1)],
        }
    }

    fn output_bounds(self) -> &'static [(i64, i64)] {
        match self {
            Self::Median => &[(-4, 4); 2],
            Self::Inference => &[(-64, 64)],
            Self::Train => &[(-134, 134); 4],
        }
    }

    /// Median expects five ordered pairs. The neural relations expect
    /// first-layer weights, second-layer weights, one feature, and (for Train) one label.
    pub fn evaluate(self, input: &[i64]) -> Result<Vec<i64>, ContractError> {
        if input.len() != self.bounds().len()
            || input
                .iter()
                .zip(self.bounds())
                .any(|(v, (a, b))| v < a || v > b)
        {
            return Err(ContractError("m5-input-range-or-shape"));
        }
        if self == Self::Median {
            for pair in input.chunks_exact(2) {
                if pair[0] * pair[0] + pair[1] * pair[1] > 16 {
                    return Err(ContractError("m5-update-norm"));
                }
            }
            return Ok((0..2)
                .map(|axis| {
                    let mut column = [0; 5];
                    for (row, value) in column.iter_mut().enumerate() {
                        *value = input[2 * row + axis];
                    }
                    column.sort_unstable();
                    column[2]
                })
                .collect());
        }
        let [a, b, c, d, x] = input[..5]
            .try_into()
            .map_err(|_| ContractError("m5-input-shape"))?;
        let z: [i64; 2] = [a * x, b * x];
        let h = z.map(|value| value.max(0));
        let score = c * h[0] + d * h[1];
        if self == Self::Inference {
            return Ok(vec![score]);
        }
        let error = score - input[5];
        let gradients = [
            error * c * x * i64::from(z[0] > 0),
            error * d * x * i64::from(z[1] > 0),
            error * h[0],
            error * h[1],
        ];
        input[..4]
            .iter()
            .zip(gradients)
            .map(|(&w, g)| {
                let step = i64::try_from(round_even(i128::from(g), 4)?)
                    .map_err(|_| ContractError("m5-training-overflow"))?;
                w.checked_sub(step)
                    .ok_or(ContractError("m5-training-overflow"))
            })
            .collect()
    }

    fn bytes(self, input: &[i64]) -> Vec<u8> {
        input
            .iter()
            .zip(self.bounds())
            .map(|(v, (low, _))| {
                u8::try_from(v - low).expect("validated input shifted into one byte")
            })
            .collect()
    }

    fn commitment(self, input: &[i64], blind: &[u8; 32]) -> [u8; 32] {
        let mut hash = Sha256::new();
        hash.update(self.tag());
        hash.update(blind);
        hash.update(self.bytes(input));
        hash.finalize().into()
    }
}

type Cs = ConstraintSystemRef<Fr>;

/// The integer component supplies witness assignments. Only the field expression
/// participates in constraints; each comparison and rounding witness is checked.
#[derive(Clone)]
struct Wire {
    integer: i64,
    var: FpVar<Fr>,
}

impl Wire {
    fn allocate(cs: Cs, integer: i64) -> Result<Self, SynthesisError> {
        let var = FpVar::new_witness(cs, || Ok(field(integer.into())))?;
        Ok(Self { integer, var })
    }

    fn add(&self, rhs: &Self) -> Self {
        Self {
            integer: self.integer + rhs.integer,
            var: &self.var + &rhs.var,
        }
    }

    fn sub(&self, rhs: &Self) -> Self {
        Self {
            integer: self.integer - rhs.integer,
            var: &self.var - &rhs.var,
        }
    }

    fn mul(&self, rhs: &Self) -> Self {
        Self {
            integer: self.integer * rhs.integer,
            var: &self.var * &rhs.var,
        }
    }

    fn range(&self, cs: Cs, low: i64, high: i64) -> Result<(), SynthesisError> {
        bound(cs, &self.var, self.integer.into(), low.into(), high.into())?;
        Ok(())
    }

    fn divide_four(&self, cs: Cs) -> Result<Self, SynthesisError> {
        let var = rounded(
            cs,
            &self.var,
            self.integer.into(),
            &FpVar::Constant(field(4)),
            4,
            4,
        )?;
        let integer = i64::try_from(
            round_even(self.integer.into(), 4).map_err(|_| SynthesisError::Unsatisfiable)?,
        )
        .map_err(|_| SynthesisError::Unsatisfiable)?;
        Ok(Self { integer, var })
    }
}

// Equivalent witnesses on a tie produce identical sorted values. No source
// identity or input permutation is published.
fn ordered(cs: Cs, a: &Wire, b: &Wire) -> Result<(Wire, Wire), SynthesisError> {
    let swap = Boolean::new_witness(cs.clone(), || Ok(a.integer > b.integer))?;
    let low = Wire {
        integer: a.integer.min(b.integer),
        var: swap.select(&b.var, &a.var)?,
    };
    let high = Wire {
        integer: a.integer.max(b.integer),
        var: swap.select(&a.var, &b.var)?,
    };
    high.sub(&low).range(cs, 0, 8)?;
    Ok((low, high))
}

fn median(cs: Cs, input: &[Wire]) -> Result<Vec<Wire>, SynthesisError> {
    for pair in input.chunks_exact(2) {
        pair[0]
            .mul(&pair[0])
            .add(&pair[1].mul(&pair[1]))
            .range(cs.clone(), 0, 16)?;
    }
    (0..2)
        .map(|axis| {
            let mut column: Vec<_> = input.iter().skip(axis).step_by(2).cloned().collect();
            for end in (1..column.len()).rev() {
                for i in 0..end {
                    let (low, high) = ordered(cs.clone(), &column[i], &column[i + 1])?;
                    column[i] = low;
                    column[i + 1] = high;
                }
            }
            Ok(column[2].clone())
        })
        .collect()
}

fn relu(cs: Cs, input: &Wire) -> Result<(Wire, Wire), SynthesisError> {
    let active = Wire {
        integer: i64::from(input.integer > 0),
        var: FpVar::from(Boolean::new_witness(cs.clone(), || Ok(input.integer > 0))?),
    };
    let value = active.mul(input);
    // Active implies z >= 1. Inactive implies z <= 0, including the kink.
    value.sub(&active).range(cs.clone(), 0, 7)?;
    input.sub(&value).range(cs, -8, 0)?;
    Ok((value, active))
}

fn neural(cs: Cs, relation: Relation, x: &[Wire]) -> Result<Vec<Wire>, SynthesisError> {
    let (h0, active0) = relu(cs.clone(), &x[0].mul(&x[4]))?;
    let (h1, active1) = relu(cs.clone(), &x[1].mul(&x[4]))?;
    let score = h0.mul(&x[2]).add(&h1.mul(&x[3]));
    if relation == Relation::Inference {
        return Ok(vec![score]);
    }
    let error = score.sub(&x[5]);
    let gradients = [
        error.mul(&x[2]).mul(&x[4]).mul(&active0),
        error.mul(&x[3]).mul(&x[4]).mul(&active1),
        error.mul(&h0),
        error.mul(&h1),
    ];
    x.iter()
        .take(4)
        .zip(gradients)
        .map(|(w, g)| Ok(w.sub(&g.divide_four(cs.clone())?)))
        .collect()
}

#[derive(Clone)]
struct Workload {
    relation: Relation,
    input: Vec<i64>,
    blind: [u8; 32],
    statement: Statement,
}

#[derive(Clone, Debug)]
pub struct Statement {
    pub commitment: [u8; 32],
    pub output: Vec<i64>,
}

impl Statement {
    fn fields(&self) -> Vec<Fr> {
        self.commitment
            .iter()
            .map(|v| field(i128::from(*v)))
            .chain(self.output.iter().map(|v| field(i128::from(*v))))
            .collect()
    }
}

impl ConstraintSynthesizer<Fr> for Workload {
    fn generate_constraints(self, cs: Cs) -> Result<(), SynthesisError> {
        if self.input.len() != self.relation.bounds().len()
            || self.statement.output.len() != self.relation.output_bounds().len()
        {
            return Err(SynthesisError::Unsatisfiable);
        }
        let root = self
            .statement
            .commitment
            .iter()
            .map(|&byte| {
                let byte_var = FpVar::new_input(cs.clone(), || Ok(field(byte.into())))?;
                Ok(UInt8::from_bits_le(&bound(
                    cs.clone(),
                    &byte_var,
                    byte.into(),
                    0,
                    255,
                )?))
            })
            .collect::<Result<Vec<_>, SynthesisError>>()?;
        let mut message = UInt8::constant_vec(self.relation.tag());
        message.extend(UInt8::new_witness_vec(cs.clone(), &self.blind)?);
        let mut input_vars = Vec::with_capacity(self.input.len());
        for ((integer, &(low, high)), byte) in self
            .input
            .iter()
            .zip(self.relation.bounds())
            .zip(self.relation.bytes(&self.input))
        {
            let wire = Wire::allocate(cs.clone(), *integer)?;
            wire.range(cs.clone(), low, high)?;
            let byte_var = UInt8::new_witness(cs.clone(), || Ok(byte))?;
            Boolean::le_bits_to_fp(&byte_var.to_bits_le()?)?
                .enforce_equal(&(&wire.var - field(low.into())))?;
            message.push(byte_var);
            input_vars.push(wire);
        }
        Sha256Gadget::digest(&message)?.0.enforce_equal(&root)?;

        let result = match self.relation {
            Relation::Median => median(cs.clone(), &input_vars)?,
            r => neural(cs.clone(), r, &input_vars)?,
        };
        for ((wire, value), &(low, high)) in result
            .iter()
            .zip(self.statement.output)
            .zip(self.relation.output_bounds())
        {
            let public = FpVar::new_input(cs.clone(), || Ok(field(value.into())))?;
            bound(cs.clone(), &public, value.into(), low.into(), high.into())?;
            wire.var.enforce_equal(&public)?;
        }
        Ok(())
    }
}

impl Workload {
    fn new(relation: Relation, input: &[i64], blind: [u8; 32]) -> Result<Self, ContractError> {
        let output = relation.evaluate(input)?;
        let statement = Statement {
            commitment: relation.commitment(input, &blind),
            output,
        };
        Ok(Self {
            relation,
            input: input.to_vec(),
            blind,
            statement,
        })
    }
}

/// A verifier holds only the pinned prepared key and relation. Callers must trust
/// the public statement (including its precommitted payload root) independently.
pub struct Verifier {
    relation: Relation,
    key: PreparedVerifyingKey<Bn254>,
}

impl Verifier {
    pub fn verify(&self, statement: &Statement, proof_bytes: &[u8]) -> Result<bool, ContractError> {
        if proof_bytes.len() != 128
            || statement.output.len() != self.relation.output_bounds().len()
            || statement
                .output
                .iter()
                .zip(self.relation.output_bounds())
                .any(|(v, (a, b))| v < a || v > b)
        {
            return Ok(false);
        }
        let proof = Proof::<Bn254>::deserialize_compressed(proof_bytes)
            .map_err(|_| ContractError("m5-proof-encoding"))?;
        let mut canonical = Vec::new();
        proof
            .serialize_compressed(&mut canonical)
            .map_err(|_| ContractError("m5-proof-encoding"))?;
        if canonical != proof_bytes {
            return Ok(false);
        }
        Groth16::<Bn254>::verify_proof(&self.key, &proof, &statement.fields())
            .map_err(|_| ContractError("m5-verification"))
    }
}

pub struct Prover {
    relation: Relation,
    key: ProvingKey<Bn254>,
    pub constraints: usize,
}

impl Prover {
    /// Generates a new circuit-specific key using OS entropy for local research.
    pub fn setup(relation: Relation) -> Result<(Self, Verifier), ContractError> {
        let empty = vec![0; relation.bounds().len()];
        let circuit = Workload::new(relation, &empty, [0; 32])?;
        let cs = ConstraintSystem::new_ref();
        circuit
            .clone()
            .generate_constraints(cs.clone())
            .map_err(|_| ContractError("m5-synthesis"))?;
        let constraints = cs.num_constraints();
        drop(cs);
        let key = Groth16::<Bn254>::generate_random_parameters_with_reduction(circuit, &mut OsRng)
            .map_err(|_| ContractError("m5-setup"))?;
        let verifier = Verifier {
            relation,
            key: prepare_verifying_key(&key.vk),
        };
        Ok((
            Self {
                relation,
                key,
                constraints,
            },
            verifier,
        ))
    }

    pub fn prove(&self, input: &[i64]) -> Result<(Statement, Vec<u8>), ContractError> {
        let mut blind = [0; 32];
        OsRng
            .try_fill_bytes(&mut blind)
            .map_err(|_| ContractError("m5-entropy"))?;
        let circuit = Workload::new(self.relation, input, blind)?;
        let statement = circuit.statement.clone();
        let proof =
            Groth16::<Bn254>::create_random_proof_with_reduction(circuit, &self.key, &mut OsRng)
                .map_err(|_| ContractError("m5-proving"))?;
        let mut proof_bytes = Vec::new();
        proof
            .serialize_compressed(&mut proof_bytes)
            .map_err(|_| ContractError("m5-proof-encoding"))?;
        Ok((statement, proof_bytes))
    }
}

pub const MEDIAN_INPUT: [i64; 10] = [1, 0, 1, 1, 0, 1, 1, 0, -4, 0];
pub const NEURAL_INPUT: [i64; 6] = [1, 1, -2, 1, 2, 1];

#[derive(Debug, Serialize)]
pub struct Measurement {
    pub output: Vec<i64>,
    pub constraint_count: usize,
    pub setup_seconds: f64,
    pub witness_and_proving_seconds: f64,
    pub verification_seconds: f64,
    pub proof_bytes: usize,
    pub modified_statement_rejected: bool,
    pub modified_commitment_rejected: bool,
    pub invalid_proof_rejected: bool,
}

/// Measures one successful CPU execution and checks its public input binding.
pub fn measure(relation: Relation, input: &[i64]) -> Result<Measurement, ContractError> {
    let start = Instant::now();
    let (prover, verifier) = Prover::setup(relation)?;
    let setup_seconds = start.elapsed().as_secs_f64();
    let start = Instant::now();
    let (statement, proof) = prover.prove(input)?;
    let witness_and_proving_seconds = start.elapsed().as_secs_f64();
    let start = Instant::now();
    if !verifier.verify(&statement, &proof)? {
        return Err(ContractError("m5-honest-proof-rejected"));
    }
    let verification_seconds = start.elapsed().as_secs_f64();
    let mut changed = statement.clone();
    changed.output[0] += 1;
    let modified_statement_rejected = !verifier.verify(&changed, &proof)?;
    changed = statement.clone();
    changed.commitment[0] ^= 1;
    let modified_commitment_rejected = !verifier.verify(&changed, &proof)?;
    let invalid_proof_rejected = !verifier.verify(&statement, &[255; 128]).unwrap_or(false);
    if !(modified_statement_rejected && modified_commitment_rejected && invalid_proof_rejected) {
        return Err(ContractError("m5-mutant-accepted"));
    }
    Ok(Measurement {
        output: statement.output,
        constraint_count: prover.constraints,
        setup_seconds,
        witness_and_proving_seconds,
        verification_seconds,
        proof_bytes: proof.len(),
        modified_statement_rejected,
        modified_commitment_rejected,
        invalid_proof_rejected,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn independent_golden_outputs_have_real_proofs() {
        for (relation, input, output) in [
            (Relation::Median, MEDIAN_INPUT.as_slice(), vec![1, 0]),
            (Relation::Inference, &NEURAL_INPUT[..5], vec![-2]),
            (Relation::Train, NEURAL_INPUT.as_slice(), vec![-2, 3, 0, 3]),
        ] {
            assert_eq!(relation.evaluate(input).unwrap(), output);
            assert_eq!(measure(relation, input).unwrap().output, output);
        }
    }

    #[test]
    fn invalid_norm_and_shape_are_rejected() {
        let mut updates = MEDIAN_INPUT;
        updates[0] = 4;
        updates[1] = 4;
        assert!(Relation::Median.evaluate(&updates).is_err());
        assert!(Relation::Train.evaluate(&NEURAL_INPUT[..5]).is_err());
    }

    #[test]
    fn arbitrary_relu_or_training_output_is_rejected_in_the_circuit() {
        let cs = ConstraintSystem::new_ref();
        let zero = Wire::allocate(cs.clone(), 0).unwrap();
        let (_, active) = relu(cs.clone(), &zero).unwrap();
        active
            .var
            .enforce_equal(&FpVar::Constant(field(1)))
            .unwrap();
        assert!(!cs.is_satisfied().unwrap());

        let cs = ConstraintSystem::new_ref();
        let mut training = Workload::new(Relation::Train, &NEURAL_INPUT, [27; 32]).unwrap();
        training.statement.output[0] += 1;
        training.generate_constraints(cs.clone()).unwrap();
        assert!(!cs.is_satisfied().unwrap());
    }
}
