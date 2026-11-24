use super::{Context, Contribution, Id, Result, ensure, hash};
use crate::{
    ContractError,
    proof::{bound, field, rounded},
    round_even,
};
use ark_bn254::{Bn254, Fr as CircuitField};
use ark_ec::{AffineRepr, CurveGroup, PrimeGroup};
use ark_ed_on_bn254::{
    EdwardsAffine, EdwardsProjective as Point, Fr as Scalar, constraints::EdwardsVar,
};
use ark_ff::{AdditiveGroup, BigInteger, PrimeField, UniformRand};
use ark_groth16::{Groth16, PreparedVerifyingKey, Proof, ProvingKey, prepare_verifying_key};
use ark_r1cs_std::{
    alloc::AllocVar, boolean::Boolean, eq::EqGadget, fields::fp::FpVar, groups::CurveVar,
    prelude::ToBitsGadget,
};
use ark_relations::r1cs::{ConstraintSynthesizer, ConstraintSystemRef, SynthesisError};
use ark_serialize::{CanonicalDeserialize, CanonicalSerialize};
use rand::rngs::OsRng;
use sha2::{Digest, Sha256};

/// Domain-separated try-and-increment map; ROM/unknown-discrete-log assumption.
/// This is not an RFC 9380 suite and requires independent parameter review.
pub(crate) fn h_generator() -> Point {
    for counter in 0u32..1024 {
        let mut hash = Sha256::new();
        hash.update(b"FZKML/Pedersen/H/BabyJubJub/v1");
        hash.update(counter.to_le_bytes());
        let y = CircuitField::from_le_bytes_mod_order(&hash.finalize());
        if let Some(point) = EdwardsAffine::get_point_from_y_unchecked(y, false) {
            let point = point.clear_cofactor();
            if !point.is_zero() && point != Point::generator().into_affine() {
                return point.into_group();
            }
        }
    }
    unreachable!("fixed generator derivation exhausted")
}
pub(crate) fn commit(value: Scalar, blind: Scalar) -> Point {
    Point::generator() * value + h_generator() * blind
}
pub(crate) fn encode_point(point: Point) -> Result<Vec<u8>> {
    let mut out = Vec::new();
    point
        .into_affine()
        .serialize_compressed(&mut out)
        .map_err(|_| ContractError("point-encoding"))?;
    Ok(out)
}
pub(crate) fn decode_point(bytes: &[u8]) -> Result<Point> {
    ensure(bytes.len() == 32, "point-length")?;
    EdwardsAffine::deserialize_compressed(bytes)
        .map(|p| p.into_group())
        .map_err(|_| ContractError("point-subgroup-encoding"))
}
pub(crate) fn scalar_bytes(value: Scalar) -> Result<Vec<u8>> {
    let mut out = Vec::new();
    value
        .serialize_compressed(&mut out)
        .map_err(|_| ContractError("scalar-encoding"))?;
    Ok(out)
}
pub(crate) fn scalar_decode(bytes: &[u8]) -> Result<Scalar> {
    ensure(bytes.len() == 32, "scalar-length")?;
    Scalar::deserialize_compressed(bytes).map_err(|_| ContractError("noncanonical-scalar"))
}
pub(crate) fn context_scalar(context: &Context) -> Result<Scalar> {
    Ok(Scalar::from_le_bytes_mod_order(&context.id()?[..31]))
}
fn context_field(context: &Context) -> Result<CircuitField> {
    Ok(CircuitField::from_le_bytes_mod_order(&context.id()?[..31]))
}

pub fn local_update(w: i64, x: i64, y: i64) -> Result<i64> {
    ensure(
        [w, x, y].iter().all(|v| (-32..=32).contains(v)),
        "local-input-range",
    )?;
    let prediction = round_even(i128::from(w) * i128::from(x), 16)?;
    let gradient = round_even((prediction - i128::from(y)) * i128::from(x), 16)?;
    let value = i128::from(w) - round_even(gradient, 4)?;
    ensure((-80..=80).contains(&value), "local-output-range")?;
    i64::try_from(value).map_err(|_| ContractError("local-output-range"))
}
/// Private witness deliberately has neither Debug nor Serialize.
pub struct Witness {
    pub x: i64,
    pub y: i64,
    pub(crate) blind: Scalar,
    pub(crate) data_blind: Scalar,
}
impl Witness {
    pub fn new(x: i64, y: i64) -> Self {
        Self {
            x,
            y,
            blind: Scalar::rand(&mut OsRng),
            data_blind: Scalar::rand(&mut OsRng),
        }
    }
}

#[derive(Clone)]
struct Circuit {
    context: CircuitField,
    w: i64,
    x: i64,
    y: i64,
    blind: Scalar,
    data_blind: Scalar,
    output: Point,
    data: Point,
}
fn private_bits(
    cs: ConstraintSystemRef<CircuitField>,
    value: Scalar,
) -> std::result::Result<Vec<Boolean<CircuitField>>, SynthesisError> {
    value
        .into_bigint()
        .to_bits_le()
        .into_iter()
        .map(|bit| Boolean::new_witness(cs.clone(), || Ok(bit)))
        .collect()
}
impl ConstraintSynthesizer<CircuitField> for Circuit {
    fn generate_constraints(
        self,
        cs: ConstraintSystemRef<CircuitField>,
    ) -> std::result::Result<(), SynthesisError> {
        let context = FpVar::new_input(cs.clone(), || Ok(self.context))?;
        let context_bits = context.to_bits_le()?;
        for bit in &context_bits[248..] {
            bit.enforce_equal(&Boolean::FALSE)?;
        }
        let w = FpVar::new_input(cs.clone(), || Ok(field(self.w.into())))?;
        bound(cs.clone(), &w, self.w.into(), -32, 32)?;
        let x = FpVar::new_witness(cs.clone(), || Ok(field(self.x.into())))?;
        let y = FpVar::new_witness(cs.clone(), || Ok(field(self.y.into())))?;
        bound(cs.clone(), &x, self.x.into(), -32, 32)?;
        bound(cs.clone(), &y, self.y.into(), -32, 32)?;
        let p = round_even(i128::from(self.w) * i128::from(self.x), 16)
            .map_err(|_| SynthesisError::Unsatisfiable)?;
        let prediction = rounded(
            cs.clone(),
            &(&w * &x),
            i128::from(self.w) * i128::from(self.x),
            &FpVar::Constant(field(16)),
            16,
            16,
        )?;
        bound(cs.clone(), &prediction, p, -64, 64)?;
        let g = round_even((p - i128::from(self.y)) * i128::from(self.x), 16)
            .map_err(|_| SynthesisError::Unsatisfiable)?;
        let residual = prediction - y.clone();
        bound(cs.clone(), &residual, p - i128::from(self.y), -96, 96)?;
        let gradient = rounded(
            cs.clone(),
            &(residual * &x),
            (p - i128::from(self.y)) * i128::from(self.x),
            &FpVar::Constant(field(16)),
            16,
            16,
        )?;
        bound(cs.clone(), &gradient, g, -192, 192)?;
        let update = &w - rounded(cs.clone(), &gradient, g, &FpVar::Constant(field(4)), 4, 4)?;
        let update_value =
            local_update(self.w, self.x, self.y).map_err(|_| SynthesisError::Unsatisfiable)?;
        let message_bits = bound(
            cs.clone(),
            &(&update + field(80)),
            i128::from(update_value) + 80,
            0,
            160,
        )?;
        let data_value = i128::from(self.x) + 32 + 65 * (i128::from(self.y) + 32);
        let data_bits = bound(
            cs.clone(),
            &(x + field(32) + (y + field(32)) * field(65)),
            data_value,
            0,
            4224,
        )?;
        let g = EdwardsVar::new_constant(cs.clone(), Point::generator())?;
        let h = EdwardsVar::new_constant(cs.clone(), h_generator())?;
        let output = EdwardsVar::new_input(cs.clone(), || Ok(self.output))?;
        let data = EdwardsVar::new_input(cs.clone(), || Ok(self.data))?;
        let expected = g.scalar_mul_le(message_bits.iter())?
            + h.scalar_mul_le(private_bits(cs.clone(), self.blind)?.iter())?
            + g.scalar_mul_le(context_bits[..248].iter())?;
        output.enforce_equal(&expected)?;
        data.enforce_equal(
            &(g.scalar_mul_le(data_bits.iter())?
                + h.scalar_mul_le(private_bits(cs, self.data_blind)?.iter())?),
        )
    }
}

pub(crate) struct Proved {
    pub output: Vec<u8>,
    pub data: Vec<u8>,
    pub proof: Vec<u8>,
    pub value: Scalar,
}

pub struct Parameters {
    pk: ProvingKey<Bn254>,
    vk: PreparedVerifyingKey<Bn254>,
    pub key_id: Id,
    pub parameters_id: Id,
}
impl Parameters {
    pub fn setup() -> Result<Self> {
        let circuit = Circuit {
            context: CircuitField::ZERO,
            w: 0,
            x: 0,
            y: 0,
            blind: Scalar::ZERO,
            data_blind: Scalar::ZERO,
            output: commit(Scalar::from(80u64), Scalar::ZERO),
            data: commit(Scalar::from(2112u64), Scalar::ZERO),
        };
        let pk = Groth16::<Bn254>::generate_random_parameters_with_reduction(circuit, &mut OsRng)
            .map_err(|_| ContractError("aggregation-research-setup"))?;
        let mut bytes = Vec::new();
        pk.vk
            .serialize_compressed(&mut bytes)
            .map_err(|_| ContractError("key-encoding"))?;
        let key_id = Sha256::digest(bytes).into();
        let mut bytes = Vec::new();
        pk.serialize_compressed(&mut bytes)
            .map_err(|_| ContractError("parameter-encoding"))?;
        Ok(Self {
            vk: prepare_verifying_key(&pk.vk),
            pk,
            key_id,
            parameters_id: Sha256::digest(bytes).into(),
        })
    }
    pub(crate) fn prove(&self, context: &Context, witness: &Witness) -> Result<Proved> {
        ensure(context.proof_key == self.key_id, "unregistered-proof-key")?;
        let value = local_update(context.parent.model, witness.x, witness.y)?;
        let encoded = Scalar::from((value + 80) as u64);
        let output = commit(encoded, witness.blind) + Point::generator() * context_scalar(context)?;
        let packed = (witness.x + 32) + 65 * (witness.y + 32);
        let data = commit(Scalar::from(packed as u64), witness.data_blind);
        let circuit = Circuit {
            context: context_field(context)?,
            w: context.parent.model,
            x: witness.x,
            y: witness.y,
            blind: witness.blind,
            data_blind: witness.data_blind,
            output,
            data,
        };
        let proof =
            Groth16::<Bn254>::create_random_proof_with_reduction(circuit, &self.pk, &mut OsRng)
                .map_err(|_| ContractError("private-transition-proving"))?;
        let mut bytes = Vec::new();
        proof
            .serialize_compressed(&mut bytes)
            .map_err(|_| ContractError("proof-encoding"))?;
        Ok(Proved {
            output: encode_point(output)?,
            data: encode_point(data)?,
            proof: bytes,
            value: encoded,
        })
    }
    pub fn verify(&self, context: &Context, contribution: &Contribution) -> Result<bool> {
        context.validate()?;
        ensure(
            context.proof_key == self.key_id && contribution.context == context.id()?,
            "proof-context",
        )?;
        ensure(contribution.proof.len() == 128, "proof-length")?;
        let output = decode_point(&contribution.output)?.into_affine();
        let data = decode_point(&contribution.data)?.into_affine();
        let proof = Proof::<Bn254>::deserialize_compressed(contribution.proof.as_slice())
            .map_err(|_| ContractError("proof-canonical-encoding"))?;
        let public = vec![
            context_field(context)?,
            field(context.parent.model.into()),
            output.x,
            output.y,
            data.x,
            data.y,
        ];
        Groth16::<Bn254>::verify_proof(&self.vk, &proof, &public)
            .map_err(|_| ContractError("private-transition-verification"))
    }
    pub fn relation_id() -> Result<Id> {
        hash(
            "protected-relation-v1",
            &include_str!("../../../../specs/aggregation-v1.json"),
        )
    }
}

#[cfg(test)]
mod constraint_tests {
    use super::*;
    use ark_relations::r1cs::ConstraintSystem;
    #[test]
    fn private_relation_rejects_forged_output_and_data() {
        let blind = Scalar::from(17u64);
        let rd = Scalar::from(23u64);
        let c = Circuit {
            context: CircuitField::from(5u64),
            w: 8,
            x: 16,
            y: 16,
            blind,
            data_blind: rd,
            output: commit(Scalar::from(95u64), blind),
            data: commit(Scalar::from(48 + 65 * 48u64), rd),
        };
        for mutation in 0..4 {
            let mut changed = c.clone();
            match mutation {
                1 => changed.output += Point::generator(),
                2 => changed.data += Point::generator(),
                3 => changed.x = 15,
                _ => {}
            }
            let cs = ConstraintSystem::new_ref();
            changed.generate_constraints(cs.clone()).unwrap();
            assert_eq!(cs.is_satisfied().unwrap(), mutation == 0);
        }
    }
}
