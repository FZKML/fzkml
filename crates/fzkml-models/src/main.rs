//! Genuine, fixed-shape research proofs. Public statistics reveal information;
//! these circuits do not instantiate protected vector aggregation or DP.
use ark_bn254::{Bn254, Fr};
use ark_crypto_primitives::crh::sha256::constraints::Sha256Gadget;
use ark_ff::AdditiveGroup;
use ark_groth16::{Groth16, PreparedVerifyingKey, Proof, VerifyingKey, prepare_verifying_key};
use ark_r1cs_std::{
    alloc::AllocVar, convert::ToBitsGadget, eq::EqGadget, fields::fp::FpVar, uint8::UInt8,
};
use ark_relations::r1cs::{
    ConstraintSynthesizer, ConstraintSystem, ConstraintSystemRef, SynthesisError,
};
use ark_serialize::{CanonicalDeserialize, CanonicalSerialize};
use rand::{RngCore, rngs::OsRng};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::io::{self, Read};
use std::time::Instant;

fn hash(bytes: &[u8]) -> [u8; 32] {
    Sha256::digest(bytes).into()
}
fn hex(bytes: &[u8]) -> String {
    let digits = b"0123456789abcdef";
    let mut result = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        result.push(char::from(digits[usize::from(byte >> 4)]));
        result.push(char::from(digits[usize::from(byte & 15)]));
    }
    result
}
fn unhex(value: &Value, maximum: usize) -> Result<Vec<u8>, String> {
    let text = value.as_str().ok_or("hex-type")?;
    if text.len() > 2 * maximum
        || text.len() % 2 != 0
        || !text
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    {
        return Err("hex-length-or-encoding".into());
    }
    (0..text.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&text[i..i + 2], 16).map_err(|_| "hex".into()))
        .collect()
}
fn field(value: i64) -> Fr {
    if value >= 0 {
        Fr::from(value as u64)
    } else {
        -Fr::from(value.unsigned_abs())
    }
}
fn byte_value(byte: &UInt8<Fr>) -> Result<FpVar<Fr>, SynthesisError> {
    let mut value = FpVar::Constant(Fr::ZERO);
    for (i, bit) in byte.to_bits_le()?.into_iter().enumerate() {
        value += FpVar::from(bit) * Fr::from(1_u64 << i);
    }
    Ok(value)
}
fn public_bytes(
    cs: ConstraintSystemRef<Fr>,
    bytes: &[u8],
) -> Result<Vec<UInt8<Fr>>, SynthesisError> {
    bytes
        .iter()
        .map(|b| {
            let input = FpVar::new_input(cs.clone(), || Ok(Fr::from(*b)))?;
            let byte = UInt8::new_witness(cs.clone(), || Ok(*b))?;
            byte_value(&byte)?.enforce_equal(&input)?;
            Ok(byte)
        })
        .collect()
}
fn bounded(value: &FpVar<Fr>, min: i64, max: i64) -> Result<(), SynthesisError> {
    // Small fixed ranges: the product has precisely these roots over Fr.
    // Ranges/intermediate magnitudes are far below the BN254 scalar modulus.
    let mut polynomial = FpVar::Constant(Fr::from(1_u64));
    for k in min..=max {
        polynomial *= value - field(k);
    }
    polynomial.enforce_equal(&FpVar::Constant(Fr::ZERO))
}

#[derive(Clone, Copy)]
enum Kind {
    Ridge,
    Adapter,
}
impl Kind {
    fn name(self) -> &'static str {
        match self {
            Self::Ridge => "ridge-statistics-v1",
            Self::Adapter => "fixed-factor-v1",
        }
    }
    fn domain(self) -> Vec<u8> {
        let mut value = b"FZK-MODELS-RESEARCH-V1\0".to_vec();
        value.extend(self.name().as_bytes());
        value
    }
}

#[derive(Clone)]
struct Circuit {
    kind: Kind,
    encoded: Vec<u8>,
    nonce: [u8; 32],
    context: [u8; 32],
    commitment: [u8; 32],
    outputs: Vec<i64>,
}
impl Circuit {
    fn fixture(kind: Kind) -> Self {
        let (values, outputs): (Vec<i64>, Vec<i64>) = match kind {
            // Two records, two identity features, one label; public weights1,2.
            Kind::Ridge => (vec![1, 0, 2, 0, 1, 3], vec![1, 0, 2, 2, 6, 1, 1, 2, 0, 0]),
            // B1=(1,0), B2=(1,2), fixed A=(1,0), equal weights.
            Kind::Adapter => (vec![1, 0, 1, 2], vec![2, 2, 2, 0, 2, 0, 9, 2]),
        };
        let mut nonce = [0; 32];
        OsRng.fill_bytes(&mut nonce);
        let context = hash(include_bytes!(
            "../../../specs/models/model-capacity-v1.json"
        ));
        let mut result = Self {
            kind,
            encoded: values.iter().map(|v| (v + 4) as u8).collect(),
            nonce,
            context,
            commitment: [0; 32],
            outputs,
        };
        result.commitment = result.root();
        result
    }
    fn root(&self) -> [u8; 32] {
        let mut bytes = self.kind.domain();
        bytes.extend(self.context);
        bytes.extend(self.nonce);
        bytes.extend(&self.encoded);
        hash(&bytes)
    }
    fn inputs(&self) -> Vec<Fr> {
        self.context
            .iter()
            .chain(self.commitment.iter())
            .map(|b| Fr::from(*b))
            .chain(self.outputs.iter().map(|x| field(*x)))
            .collect()
    }
}
impl ConstraintSynthesizer<Fr> for Circuit {
    fn generate_constraints(self, cs: ConstraintSystemRef<Fr>) -> Result<(), SynthesisError> {
        let context = public_bytes(cs.clone(), &self.context)?;
        let commitment = public_bytes(cs.clone(), &self.commitment)?;
        let encoded = UInt8::new_witness_vec(cs.clone(), &self.encoded)?;
        let mut message = UInt8::constant_vec(&self.kind.domain());
        message.extend(context);
        message.extend(UInt8::new_witness_vec(cs.clone(), &self.nonce)?);
        message.extend(encoded.clone());
        Sha256Gadget::digest(&message)?
            .0
            .enforce_equal(&commitment)?;
        let mut x = Vec::new();
        for byte in &encoded {
            let q = byte_value(byte)?;
            bounded(&q, 0, 8)?;
            x.push(q - Fr::from(4_u64));
        }
        let out = self
            .outputs
            .iter()
            .map(|v| FpVar::new_input(cs.clone(), || Ok(field(*v))))
            .collect::<Result<Vec<_>, _>>()?;
        match self.kind {
            Kind::Ridge => {
                // S=Z^T diag(1,2) Z; T=Z^T diag(1,2)y.
                (&x[0] * &x[0] + &x[3] * &x[3] * Fr::from(2_u64)).enforce_equal(&out[0])?;
                (&x[0] * &x[1] + &x[3] * &x[4] * Fr::from(2_u64)).enforce_equal(&out[1])?;
                (&x[1] * &x[1] + &x[4] * &x[4] * Fr::from(2_u64)).enforce_equal(&out[2])?;
                (&x[0] * &x[2] + &x[3] * &x[5] * Fr::from(2_u64)).enforce_equal(&out[3])?;
                (&x[1] * &x[2] + &x[4] * &x[5] * Fr::from(2_u64)).enforce_equal(&out[4])?;
                out[5].enforce_equal(&FpVar::Constant(Fr::from(1_u64)))?;
                bounded(&out[6], -8, 8)?;
                bounded(&out[7], -8, 8)?;
                ((&out[0] + &out[5]) * &out[6] + &out[1] * &out[7] - &out[3])
                    .enforce_equal(&out[8])?;
                (&out[1] * &out[6] + (&out[2] + &out[5]) * &out[7] - &out[4])
                    .enforce_equal(&out[9])?;
                out[8].enforce_equal(&FpVar::Constant(Fr::ZERO))?;
                out[9].enforce_equal(&FpVar::Constant(Fr::ZERO))?;
            }
            Kind::Adapter => {
                (&x[0] + &x[2]).enforce_equal(&out[0])?;
                (&x[1] + &x[3]).enforce_equal(&out[1])?;
                out[0].enforce_equal(&out[2])?;
                out[1].enforce_equal(&out[4])?;
                out[3].enforce_equal(&FpVar::Constant(Fr::ZERO))?;
                out[5].enforce_equal(&FpVar::Constant(Fr::ZERO))?;
                out[6].enforce_equal(&FpVar::Constant(Fr::from(9_u64)))?;
                out[7].enforce_equal(&FpVar::Constant(Fr::from(2_u64)))?;
                for i in [0, 2] {
                    let slack = &out[6] - (&x[i] * &x[i] + &x[i + 1] * &x[i + 1]);
                    bounded(&slack, 0, 9)?;
                }
            }
        }
        Ok(())
    }
}

fn serialized<T: CanonicalSerialize>(item: &T) -> Result<Vec<u8>, String> {
    let mut result = Vec::new();
    item.serialize_compressed(&mut result)
        .map_err(|_| "serialization".to_string())?;
    Ok(result)
}
fn verifies(key: &PreparedVerifyingKey<Bn254>, statement: &Circuit, bytes: &[u8]) -> bool {
    if bytes.len() != 128 {
        return false;
    }
    let Ok(proof) = Proof::<Bn254>::deserialize_compressed(bytes) else {
        return false;
    };
    Groth16::<Bn254>::verify_proof(key, &proof, &statement.inputs()).unwrap_or(false)
}
fn smoke(kind: Kind) -> Result<Value, String> {
    let circuit = Circuit::fixture(kind);
    let cs = ConstraintSystem::new_ref();
    circuit
        .clone()
        .generate_constraints(cs.clone())
        .map_err(|_| "constraints")?;
    if !cs.is_satisfied().map_err(|_| "constraints")? {
        return Err("unsatisfied".into());
    }
    let constraints = cs.num_constraints();
    let start = Instant::now();
    let pk =
        Groth16::<Bn254>::generate_random_parameters_with_reduction(circuit.clone(), &mut OsRng)
            .map_err(|_| "setup")?;
    let setup_seconds = start.elapsed().as_secs_f64();
    let key = prepare_verifying_key(&pk.vk);
    let vk = serialized(&pk.vk)?;
    let parameters = serialized(&pk)?;
    let start = Instant::now();
    let proof =
        Groth16::<Bn254>::create_random_proof_with_reduction(circuit.clone(), &pk, &mut OsRng)
            .map_err(|_| "prove")?;
    let prove_seconds = start.elapsed().as_secs_f64();
    let proof = serialized(&proof)?;
    let start = Instant::now();
    if !verifies(&key, &circuit, &proof) {
        return Err("honest-proof-rejected".into());
    }
    let verify_seconds = start.elapsed().as_secs_f64();
    let mut negatives = 0;
    for index in 0..circuit.outputs.len() {
        let mut changed = circuit.clone();
        changed.outputs[index] += 1;
        if verifies(&key, &changed, &proof) {
            return Err("output-substitution".into());
        }
        negatives += 1;
    }
    for context in [true, false] {
        let mut changed = circuit.clone();
        if context {
            changed.context[0] ^= 1;
        } else {
            changed.commitment[0] ^= 1;
        }
        if verifies(&key, &changed, &proof) {
            return Err("lineage-substitution".into());
        }
        negatives += 1;
    }
    let mut trailing = proof.clone();
    trailing.push(0);
    if verifies(&key, &circuit, &trailing) || verifies(&key, &circuit, &[0; 128]) {
        return Err("malformed-proof".into());
    }
    negatives += 2;
    let start = Instant::now();
    let other =
        Groth16::<Bn254>::generate_random_parameters_with_reduction(circuit.clone(), &mut OsRng)
            .map_err(|_| "negative-setup")?;
    let negative_setup_seconds = start.elapsed().as_secs_f64();
    if verifies(&prepare_verifying_key(&other.vk), &circuit, &proof) {
        return Err("wrong-key".into());
    }
    negatives += 1;
    Ok(
        json!({"relation":kind.name(),"verified":true,"backend":"ark-groth16-0.5.0-bn254",
        "proof_mode":"research-real","constraints":constraints,"outputs":circuit.outputs,
        "proof_bytes":proof.len(),"proof_hex":hex(&proof),"key_digest":hex(&hash(&vk)),
        "verifying_key_chunks":vk.chunks(256).map(hex).collect::<Vec<_>>(),
        "parameters_digest":hex(&hash(&parameters)),"context_digest":hex(&circuit.context),
        "data_commitment":hex(&circuit.commitment),"negatives_rejected":negatives,
        "setup_seconds":setup_seconds,"prove_seconds":prove_seconds,"verify_seconds":verify_seconds,
        "negative_setup_seconds":negative_setup_seconds,
        "limitations":["Fresh local setup; no production ceremony or independent cryptographic review.",
          "Fixed two-record/two-client synthetic relations; not arbitrary model training.",
          "Ridge statistics and adapter sums are public; no protected-vector or DP guarantee.",
          "Feature extraction/authenticity and authorization are external assumptions."]}),
    )
}
fn verify_artifact(value: &Value) -> Result<(), String> {
    let records = value["proofs"].as_array().ok_or("proof-array")?;
    if records.len() != 2 {
        return Err("proof-count".into());
    }
    for (kind, record) in [Kind::Ridge, Kind::Adapter].into_iter().zip(records) {
        let expected = match kind {
            Kind::Ridge => 10,
            Kind::Adapter => 8,
        };
        if record["relation"].as_str() != Some(kind.name()) {
            return Err("relation".into());
        }
        let chunks = record["verifying_key_chunks"]
            .as_array()
            .ok_or("key-chunks")?;
        if chunks.is_empty() || chunks.len() > 32 {
            return Err("key-size".into());
        }
        let mut bytes = Vec::new();
        for chunk in chunks {
            bytes.extend(unhex(chunk, 256)?);
        }
        // Pinned ark-serialize0.5 VK layout: four fixed compressed points, then
        // u64 vector length. Bound it before Vec deserialization can allocate.
        let gamma_count = 64 + expected + 1;
        if bytes.len() != 232 + gamma_count * 32
            || u64::from_le_bytes(bytes[224..232].try_into().map_err(|_| "key-prefix")?)
                != gamma_count as u64
        {
            return Err("key-input-count".into());
        }
        if record["key_digest"].as_str() != Some(hex(&hash(&bytes)).as_str()) {
            return Err("key-digest".into());
        }
        let mut remaining = bytes.as_slice();
        let vk =
            VerifyingKey::<Bn254>::deserialize_compressed(&mut remaining).map_err(|_| "key")?;
        if !remaining.is_empty() || serialized(&vk)? != bytes {
            return Err("noncanonical-key".into());
        }
        let mut circuit = Circuit::fixture(kind);
        let context = unhex(&record["context_digest"], 32)?;
        circuit.context = context.try_into().map_err(|_| "context-length")?;
        if circuit.context
            != hash(include_bytes!(
                "../../../specs/models/model-capacity-v1.json"
            ))
        {
            return Err("context".into());
        }
        circuit.commitment = unhex(&record["data_commitment"], 32)?
            .try_into()
            .map_err(|_| "commitment-length")?;
        circuit.outputs = record["outputs"]
            .as_array()
            .ok_or("outputs")?
            .iter()
            .map(|x| x.as_i64().ok_or("output-type"))
            .collect::<Result<Vec<_>, _>>()?;
        if circuit.outputs.len() != expected {
            return Err("output-shape".into());
        }
        let proof = unhex(&record["proof_hex"], 128)?;
        if !verifies(&prepare_verifying_key(&vk), &circuit, &proof) {
            return Err("artifact-proof-invalid".into());
        }
    }
    Ok(())
}
fn main() {
    let result = (|| -> Result<Value, String> {
        let args = std::env::args().skip(1).collect::<Vec<_>>();
        if args == ["--verify"] {
            let mut text = String::new();
            io::stdin()
                .take(64_001)
                .read_to_string(&mut text)
                .map_err(|_| "read")?;
            if text.len() > 64_000 {
                return Err("input-bound".into());
            }
            let value: Value = serde_json::from_str(&text).map_err(|_| "json")?;
            verify_artifact(&value)?;
            return Ok(
                json!({"cryptographically_verified":true,"key_authorization":"external-assumption"}),
            );
        }
        if !args.is_empty() {
            return Err("no-unreviewed-inputs".into());
        }
        let value = json!({"version":1,
            "contract_digest":hex(&hash(include_bytes!("../../../specs/models/model-capacity-v1.json"))),
            "program_digest":hex(&hash(include_bytes!("main.rs"))),
            "dependency_digest":hex(&hash(include_bytes!("../../../Cargo.lock"))),
            "proofs":[smoke(Kind::Ridge)?,smoke(Kind::Adapter)?]});
        verify_artifact(&value)?;
        let mut altered = value.clone();
        altered["proofs"][0]["proof_hex"] = Value::String("00".repeat(128));
        if verify_artifact(&altered).is_ok() {
            return Err("artifact-mutation-accepted".into());
        }
        Ok(value)
    })();
    match result {
        Ok(value) => println!("{value}"),
        Err(_) => {
            eprintln!("genuine-model-proof-failed");
            std::process::exit(1);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn satisfied(c: Circuit) -> bool {
        let cs = ConstraintSystem::new_ref();
        c.generate_constraints(cs.clone()).unwrap();
        cs.is_satisfied().unwrap()
    }
    #[test]
    fn actual_constraints_bind_statistics_factor_and_residual() {
        for kind in [Kind::Ridge, Kind::Adapter] {
            let c = Circuit::fixture(kind);
            assert!(satisfied(c.clone()));
            for index in 0..c.outputs.len() {
                let mut bad = c.clone();
                bad.outputs[index] += 1;
                assert!(!satisfied(bad));
            }
            let mut detached = c.clone();
            detached.encoded[0] += 1;
            assert!(!satisfied(detached));
            let mut context = c.clone();
            context.context[0] ^= 1;
            assert!(!satisfied(context));
        }
    }
    #[test]
    fn private_coordinate_and_delivered_clip_ranges_are_constrained() {
        let mut out_of_range = Circuit::fixture(Kind::Ridge);
        // A perfectly consistent integer normal equation, except for Z00=5
        // outside [-4,4]. Other arithmetic/commitment checks cannot mask it.
        out_of_range.encoded = vec![9, 4, 4, 4, 5, 7];
        out_of_range.outputs = vec![25, 0, 2, 0, 6, 1, 0, 2, 0, 0];
        out_of_range.commitment = out_of_range.root();
        assert!(!satisfied(out_of_range));
        let mut unclipped = Circuit::fixture(Kind::Adapter);
        unclipped.encoded = vec![8, 8, 8, 8];
        unclipped.commitment = unclipped.root();
        unclipped.outputs = vec![8, 8, 8, 0, 8, 0, 9, 2];
        assert!(!satisfied(unclipped));
    }
}
