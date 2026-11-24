//! Local randomized Groth16 setup; all tiny-scenario inputs are PUBLIC.
use crate::{Batch, ContractError, Witness, evaluate};
use ark_bn254::{Bn254, Fr};
use ark_ff::{AdditiveGroup, Field, PrimeField};
use ark_groth16::{Groth16, PreparedVerifyingKey, Proof, ProvingKey, prepare_verifying_key};
use ark_r1cs_std::{alloc::AllocVar, boolean::Boolean, eq::EqGadget, fields::fp::FpVar};
use ark_relations::r1cs::{ConstraintSynthesizer, ConstraintSystemRef, SynthesisError};
use ark_serialize::{CanonicalDeserialize, CanonicalSerialize};
use rand::rngs::OsRng;
use sha2::{Digest, Sha256};
use std::time::Instant;

fn domain() -> Fr {
    let digest = Sha256::digest(include_bytes!("../../../specs/numeric-contract-v1.json"));
    Fr::from_le_bytes_mod_order(&digest[..31])
}
fn field(v: i128) -> Fr {
    if v >= 0 {
        Fr::from(v as u128)
    } else {
        -Fr::from(v.unsigned_abs())
    }
}

/// Bound both v-low and high-v by nonnegative bit sums; no field ordering.
fn bound(
    cs: ConstraintSystemRef<Fr>,
    v: &FpVar<Fr>,
    value: i128,
    low: i128,
    high: i128,
) -> Result<Vec<Boolean<Fr>>, SynthesisError> {
    let width = 128 - (high - low).leading_zeros();
    let mut first = Vec::new();
    for (difference, expression) in [
        (value - low, v - field(low)),
        (high - value, FpVar::Constant(field(high)) - v),
    ] {
        let mut sum = FpVar::Constant(Fr::ZERO);
        let mut bits = Vec::new();
        for i in 0..width {
            let bit = Boolean::new_witness(cs.clone(), || Ok(((difference >> i) & 1) != 0))?;
            sum += FpVar::from(bit.clone()) * field(1_i128 << i);
            bits.push(bit);
        }
        sum.enforce_equal(&expression)?;
        if first.is_empty() {
            first = bits;
        }
    }
    Ok(first)
}

fn rounded(
    cs: ConstraintSystemRef<Fr>,
    n: &FpVar<Fr>,
    n_value: i128,
    d: &FpVar<Fr>,
    d_value: i128,
    max_d: i128,
) -> Result<FpVar<Fr>, SynthesisError> {
    let q_value = n_value.div_euclid(d_value);
    let r_value = n_value.rem_euclid(d_value);
    let q = FpVar::new_witness(cs.clone(), || Ok(field(q_value)))?;
    let parity = bound(cs.clone(), &q, q_value, -1024, 1024)?[0].clone();
    let r = FpVar::new_witness(cs.clone(), || Ok(field(r_value)))?;
    bound(cs.clone(), &r, r_value, 0, max_d - 1)?;
    bound(
        cs.clone(),
        &(d - field(1) - &r),
        d_value - 1 - r_value,
        0,
        max_d - 1,
    )?;
    n.enforce_equal(&(d * &q + &r))?;
    let delta_value = 2 * r_value - d_value;
    let delta = &r * field(2) - d;
    let less = Boolean::new_witness(cs.clone(), || Ok(delta_value < 0))?;
    let equal = Boolean::new_witness(cs.clone(), || Ok(delta_value == 0))?;
    let greater = Boolean::new_witness(cs.clone(), || Ok(delta_value > 0))?;
    let l = FpVar::from(less);
    let e = FpVar::from(equal.clone());
    let g = FpVar::from(greater.clone());
    (&l + &e + &g).enforce_equal(&FpVar::Constant(Fr::ONE))?;
    let gap_value = (delta_value.abs() - 1).max(0);
    let gap = FpVar::new_witness(cs.clone(), || Ok(field(gap_value)))?;
    bound(cs, &gap, gap_value, 0, max_d - 1)?;
    ((&delta + field(1) + &gap) * l).enforce_equal(&FpVar::Constant(Fr::ZERO))?;
    (&delta * e).enforce_equal(&FpVar::Constant(Fr::ZERO))?;
    ((delta - field(1) - gap) * g).enforce_equal(&FpVar::Constant(Fr::ZERO))?;
    let increment = greater | (equal & parity);
    Ok(q + FpVar::from(increment))
}

#[derive(Clone)]
struct Circuit {
    batch: Batch,
    witness: Witness,
    claimed: i64,
}
impl ConstraintSynthesizer<Fr> for Circuit {
    fn generate_constraints(self, cs: ConstraintSystemRef<Fr>) -> Result<(), SynthesisError> {
        let domain_input = FpVar::new_input(cs.clone(), || Ok(domain()))?;
        domain_input.enforce_equal(&FpVar::Constant(domain()))?;
        let w = FpVar::new_input(cs.clone(), || Ok(field(self.batch.w.into())))?;
        bound(cs.clone(), &w, self.batch.w.into(), -32, 32)?;
        let mut numerator = FpVar::Constant(Fr::ZERO);
        let mut denominator = FpVar::Constant(Fr::ZERO);
        let mut num_value = 0_i128;
        let mut den_value = 0_i128;
        for i in 0..3 {
            let xv = i128::from(self.batch.x[i]);
            let yv = i128::from(self.batch.y[i]);
            let cv = i128::from(self.batch.counts[i]);
            let x = FpVar::new_input(cs.clone(), || Ok(field(xv)))?;
            let y = FpVar::new_input(cs.clone(), || Ok(field(yv)))?;
            let count = FpVar::new_input(cs.clone(), || Ok(field(cv)))?;
            bound(cs.clone(), &x, xv, -32, 32)?;
            bound(cs.clone(), &y, yv, -32, 32)?;
            bound(cs.clone(), &count, cv, 1, 4)?;
            let prediction = rounded(
                cs.clone(),
                &(&w * &x),
                i128::from(self.batch.w) * xv,
                &FpVar::Constant(field(16)),
                16,
                16,
            )?;
            bound(
                cs.clone(),
                &prediction,
                self.witness.predictions[i].into(),
                -64,
                64,
            )?;
            let residual = prediction - y;
            let residual_value = i128::from(self.witness.predictions[i]) - yv;
            bound(cs.clone(), &residual, residual_value, -96, 96)?;
            let gradient = rounded(
                cs.clone(),
                &(residual * x),
                residual_value * xv,
                &FpVar::Constant(field(16)),
                16,
                16,
            )?;
            bound(
                cs.clone(),
                &gradient,
                self.witness.gradients[i].into(),
                -192,
                192,
            )?;
            let update = &w
                - rounded(
                    cs.clone(),
                    &gradient,
                    self.witness.gradients[i].into(),
                    &FpVar::Constant(field(4)),
                    4,
                    4,
                )?;
            bound(cs.clone(), &update, self.witness.updates[i].into(), -80, 80)?;
            numerator += update * &count;
            denominator += count;
            num_value += i128::from(self.witness.updates[i]) * cv;
            den_value += cv;
        }
        let output = rounded(
            cs.clone(),
            &numerator,
            num_value,
            &denominator,
            den_value,
            12,
        )?;
        let claimed = FpVar::new_input(cs.clone(), || Ok(field(self.claimed.into())))?;
        bound(cs, &claimed, self.claimed.into(), -80, 80)?;
        output.enforce_equal(&claimed)
    }
}

fn public_inputs(batch: &Batch, output: i64) -> Vec<Fr> {
    let mut inputs = vec![domain(), field(batch.w.into())];
    for i in 0..3 {
        inputs.extend([
            field(batch.x[i].into()),
            field(batch.y[i].into()),
            field(batch.counts[i].into()),
        ]);
    }
    inputs.push(field(output.into()));
    inputs
}

/// Check the constrained witness against an independently supplied expected result.
pub fn check_constraints(input: &[u8], expected: i64) -> Result<bool, ContractError> {
    let batch = Batch::decode(input)?;
    let witness = evaluate(&batch)?;
    let cs = ark_relations::r1cs::ConstraintSystem::new_ref();
    Circuit {
        batch,
        witness,
        claimed: expected,
    }
    .generate_constraints(cs.clone())
    .map_err(|_| ContractError("constraint-synthesis"))?;
    cs.is_satisfied()
        .map_err(|_| ContractError("constraint-check"))
}

pub struct ResearchSession {
    pk: ProvingKey<Bn254>,
    vk: PreparedVerifyingKey<Bn254>,
    pub key_id: String,
    pub parameters_id: String,
}
pub struct Proved {
    pub output: i64,
    pub proof: Vec<u8>,
    pub witness_seconds: f64,
    pub proving_seconds: f64,
}
impl ResearchSession {
    pub fn setup() -> Result<Self, ContractError> {
        let batch = Batch::default();
        let circuit = Circuit {
            witness: evaluate(&batch)?,
            batch,
            claimed: 0,
        };
        let pk = Groth16::<Bn254>::generate_random_parameters_with_reduction(circuit, &mut OsRng)
            .map_err(|_| ContractError("research-setup-failed"))?;
        let vk = prepare_verifying_key(&pk.vk);
        let mut encoded = Vec::new();
        pk.vk
            .serialize_compressed(&mut encoded)
            .map_err(|_| ContractError("key-encoding"))?;
        let key_id = format!("{:x}", Sha256::digest(encoded));
        let mut parameters = Vec::new();
        pk.serialize_compressed(&mut parameters)
            .map_err(|_| ContractError("parameter-encoding"))?;
        let parameters_id = format!("{:x}", Sha256::digest(parameters));
        Ok(Self {
            pk,
            vk,
            key_id,
            parameters_id,
        })
    }
    pub fn prove(&self, input: &[u8]) -> Result<Proved, ContractError> {
        let start = Instant::now();
        let batch = Batch::decode(input)?;
        let witness = evaluate(&batch)?;
        let output = witness.output;
        let circuit = Circuit {
            batch,
            witness,
            claimed: output,
        };
        let witness_seconds = start.elapsed().as_secs_f64();
        let start = Instant::now();
        let proof =
            Groth16::<Bn254>::create_random_proof_with_reduction(circuit, &self.pk, &mut OsRng)
                .map_err(|_| ContractError("research-proving-failed"))?;
        let proving_seconds = start.elapsed().as_secs_f64();
        let mut bytes = Vec::new();
        proof
            .serialize_compressed(&mut bytes)
            .map_err(|_| ContractError("proof-encoding"))?;
        Ok(Proved {
            output,
            proof: bytes,
            witness_seconds,
            proving_seconds,
        })
    }
    pub fn verify(&self, input: &[u8], output: i64, proof: &[u8]) -> Result<bool, ContractError> {
        let batch = Batch::decode(input)?;
        if !(-80..=80).contains(&output) || proof.len() != 128 {
            return Err(ContractError("proof-or-output-range"));
        }
        let proof = Proof::<Bn254>::deserialize_compressed(proof)
            .map_err(|_| ContractError("invalid-proof-encoding"))?;
        Groth16::<Bn254>::verify_proof(&self.vk, &proof, &public_inputs(&batch, output))
            .map_err(|_| ContractError("verification-failed"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ark_relations::r1cs::ConstraintSystem;
    #[test]
    fn constraints_reject_changed_output_and_witness() {
        let batch = Batch {
            w: 8,
            x: [16, -8, 24],
            y: [16, -16, 8],
            counts: [1, 2, 1],
        };
        for altered in 0..3 {
            let mut witness = evaluate(&batch).expect("fixture");
            let claimed = if altered == 1 {
                witness.output + 1
            } else {
                witness.output
            };
            if altered == 2 {
                witness.gradients[1] += 1;
            }
            let cs = ConstraintSystem::new_ref();
            Circuit {
                batch,
                witness,
                claimed,
            }
            .generate_constraints(cs.clone())
            .expect("synthesize");
            assert_eq!(cs.is_satisfied().expect("check"), altered == 0);
        }
    }
    #[test]
    fn proof_roundtrip_rejects_other_public_statement_and_key() {
        let session = ResearchSession::setup().expect("research setup");
        let input = Batch::default().encode().expect("encode");
        let proved = session.prove(&input).expect("prove");
        assert!(
            session
                .verify(&input, proved.output, &proved.proof)
                .expect("verify")
        );
        assert!(
            !session
                .verify(&input, proved.output + 1, &proved.proof)
                .expect("verify")
        );
        let changed = Batch {
            counts: [2, 1, 1],
            ..Batch::default()
        }
        .encode()
        .expect("encode");
        assert!(
            !session
                .verify(&changed, proved.output, &proved.proof)
                .expect("verify")
        );
        let other = ResearchSession::setup().expect("other setup");
        assert!(
            !other
                .verify(&input, proved.output, &proved.proof)
                .expect("verify")
        );
        assert!(session.verify(&input, 0, &[0; 129]).is_err());
    }
}
