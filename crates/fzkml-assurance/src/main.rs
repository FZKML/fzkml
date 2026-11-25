//! CI adapters over the existing implementation. No alternative cryptographic
//! relation, imported verifier key, production setup or security claim.
use ark_bn254::Fr;
use ark_ff::PrimeField;
use ark_serialize::CanonicalSerialize;
use fzkml_core::{Batch, proof::ResearchSession};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::time::Instant;

fn hex(bytes: &[u8]) -> String {
    let digits = b"0123456789abcdef";
    let mut result = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        result.push(char::from(digits[usize::from(b >> 4)]));
        result.push(char::from(digits[usize::from(b & 15)]));
    }
    result
}
fn sha(bytes: &[u8]) -> String {
    hex(&Sha256::digest(bytes))
}
fn field(value: i64) -> Result<Value, String> {
    let scalar = if value >= 0 {
        Fr::from(value as u64)
    } else {
        -Fr::from(value.unsigned_abs())
    };
    let mut bytes = Vec::new();
    scalar
        .serialize_compressed(&mut bytes)
        .map_err(|_| "field-encoding")?;
    Ok(json!({"integer":value,"modulus":Fr::MODULUS.to_string(),
              "field_decimal":scalar.into_bigint().to_string(),"field_le_hex":hex(&bytes),
              "signed_le_hex":hex(&value.to_le_bytes())}))
}

#[derive(Clone)]
struct Receipt {
    mode: String,
    status: String,
    key: String,
    output: i64,
    proof: Vec<u8>,
    nominal_exit: i32,
}
fn gate(authority: &ResearchSession, data: &[u8], receipt: &Receipt) -> (bool, bool) {
    if receipt.nominal_exit != 0
        || receipt.mode != "research-real"
        || receipt.status != "executed"
        || receipt.key != authority.key_id
    {
        return (false, false);
    }
    // The verifier/key is owned by the controller; receipt-supplied identities
    // cannot replace it. A true/zero-exit receipt is never a verifier verdict.
    (
        authority
            .verify(data, receipt.output, &receipt.proof)
            .unwrap_or(false),
        true,
    )
}
const CASES: [&str; 11] = [
    "positive",
    "development",
    "mock",
    "substituted-key",
    "forged-key-tag",
    "fake-proof",
    "changed-output",
    "trailing-byte",
    "skipped",
    "unsupported",
    "canceled",
];
fn auth(candidate: &str) -> Result<Value, String> {
    if !CASES.contains(&candidate) {
        return Err("unknown-case".into());
    }
    let data = Batch {
        w: 8,
        x: [16, -8, 24],
        y: [16, -16, 8],
        counts: [1, 2, 1],
    }
    .encode()
    .map_err(|_| "fixture")?;
    let start = Instant::now();
    let authority = ResearchSession::setup().map_err(|_| "setup")?;
    let setup_seconds = start.elapsed().as_secs_f64();
    let generated = authority.prove(&data).map_err(|_| "prove")?;
    let start = Instant::now();
    let other = ResearchSession::setup().map_err(|_| "negative-setup")?;
    let unrelated = other.prove(&data).map_err(|_| "negative-prove")?;
    let negative_setup_and_prove_seconds = start.elapsed().as_secs_f64();
    let good = Receipt {
        mode: "research-real".into(),
        status: "executed".into(),
        key: authority.key_id.clone(),
        output: generated.output,
        proof: generated.proof.clone(),
        nominal_exit: 0,
    };
    let mut rows = Vec::new();
    for name in CASES {
        let mut receipt = good.clone();
        match name {
            "development" => receipt.mode = "development".into(),
            "mock" => receipt.mode = "mock".into(),
            "substituted-key" => {
                receipt.key = other.key_id.clone();
                receipt.proof = unrelated.proof.clone();
            }
            "forged-key-tag" => receipt.proof = unrelated.proof.clone(),
            "fake-proof" => receipt.proof = vec![0; 128],
            "changed-output" => receipt.output += 1,
            "trailing-byte" => receipt.proof.push(0),
            "skipped" | "unsupported" | "canceled" => receipt.status = name.into(),
            _ => {}
        }
        let start = Instant::now();
        let (accepted, called) = gate(&authority, &data, &receipt);
        rows.push(json!({"case":name,"nominal_exit_code":0,"mode":receipt.mode,
            "status":receipt.status,"accepted":accepted,"native_verifier_called":called,
            "verification_seconds":start.elapsed().as_secs_f64(),"proof_bytes":receipt.proof.len(),
            "declared_key_digest":receipt.key,"key_matches_controller":receipt.key==authority.key_id}));
    }
    let selected = rows
        .iter()
        .find(|v| v["case"].as_str() == Some(candidate))
        .ok_or("case")?;
    // This producer intentionally exits zero even for an invalid candidate.
    // The independent Python/CI gate must reject candidate_accepted=false.
    Ok(json!({"version":1,"backend":"ark-groth16-0.5.0-bn254",
        "backend_mode":"research-real","candidate":candidate,"nominal_exit_code":0,
        "candidate_accepted":selected["accepted"],"controller_key_digest":authority.key_id,
        "parameters_digest":authority.parameters_id,"actual_output":generated.output,
        "actual_proof_bytes":generated.proof.len(),"cases":rows,"setup_seconds":setup_seconds,
        "witness_seconds":generated.witness_seconds,"prove_seconds":generated.proving_seconds,
        "negative_setup_and_prove_seconds":negative_setup_and_prove_seconds,
        "contract_digest":sha(include_bytes!("../../../specs/numeric-contract-v1.json")),
        "program_digest":sha(include_bytes!("main.rs")),
        "core_digest":sha(&[include_bytes!("../../fzkml-core/src/lib.rs").as_slice(),
                           include_bytes!("../../fzkml-core/src/proof.rs").as_slice()].concat()),
        "dependency_digest":sha(include_bytes!("../../../Cargo.lock")),
        "limitations":["Public arithmetic fixture; no private/full-training/protocol/DP assurance.",
          "Fresh local research setup, no production ceremony or independent review.",
          "Controller-owned key is scoped to this process; no imported-key authorization is inferred."]}))
}
fn execute() -> Result<Value, String> {
    let args = std::env::args().skip(1).take(4).collect::<Vec<_>>();
    match args.as_slice() {
        [mode, n] if mode == "field" => field(n.parse().map_err(|_| "signed-i64-required")?),
        [mode, case] if mode == "auth" => auth(case),
        _ => Err("fixed-command-required".into()),
    }
}
fn main() {
    match execute() {
        Ok(v) => println!("{v}"),
        Err(_) => {
            eprintln!("assurance-adapter-failed");
            std::process::exit(2);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn signed_encoding_and_modular_embedding_are_not_conflated() {
        let minus = field(-1).unwrap();
        assert_eq!(minus["signed_le_hex"], "ffffffffffffffff");
        assert_ne!(minus["field_le_hex"], minus["signed_le_hex"]);
        assert_eq!(field(i64::MIN).unwrap()["integer"], i64::MIN);
        assert_eq!(field(0).unwrap()["field_decimal"], "0");
    }
}
