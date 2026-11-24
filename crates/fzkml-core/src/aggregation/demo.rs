//! Original public synthetic fixture; private messages never enter the report.
use super::*;
use ed25519_dalek::SigningKey;
use rand::rngs::OsRng;
use serde::Serialize;
use std::{collections::BTreeMap, path::Path, time::Instant};

#[derive(Serialize)]
pub struct DemoReport {
    pub version: &'static str,
    pub model: i64,
    pub weighted_sum: i64,
    pub denominator: u32,
    pub reference_match: bool,
    pub accepted_clients: usize,
    pub recipients: usize,
    pub threshold: usize,
    pub seconds: BTreeMap<&'static str, f64>,
    pub application_bytes: usize,
    pub parameters_id: Id,
    pub key_id: Id,
    pub relation_id: Id,
    pub release_id: Id,
    pub accepted_root: Id,
    pub observation: Observation,
    pub limitations: Vec<&'static str>,
}

/// Uses a caller-owned private temporary directory. All roles share this process;
/// the fixture checks API separation, not network isolation or production security.
pub fn demo(path: &Path) -> Result<DemoReport> {
    let mut seconds = BTreeMap::new();
    let authority = SigningKey::generate(&mut OsRng);
    let issuer = SigningKey::generate(&mut OsRng);
    let mut recipients: Vec<_> = (1..=3)
        .map(|i| Recipient::new(i, SigningKey::generate(&mut OsRng)))
        .collect::<Result<_>>()?;
    let mut clients = Vec::new();
    for i in 1..=3u8 {
        let key = SigningKey::generate(&mut OsRng);
        let credential = Credential::issue(
            &issuer,
            [i; 32],
            [i + 10; 32],
            key.verifying_key().to_bytes(),
            0,
            1000,
        )?;
        clients.push(Client::new(key, credential)?);
    }
    let start = Instant::now();
    let parameters = Parameters::setup()?;
    seconds.insert("setup", start.elapsed().as_secs_f64());
    let context = Context {
        version: 1,
        session: [8; 32],
        round: 0,
        parent: State::new(8),
        clients: [[1; 32], [2; 32], [3; 32]],
        weights: [1, 2, 1],
        recipients: std::array::from_fn(|i| recipients[i].public_key()),
        issuer: issuer.verifying_key().to_bytes(),
        authority: authority.verifying_key().to_bytes(),
        proof_key: parameters.key_id,
        dimensions: 1,
        encoding: "dense-rne-offset80-v1".into(),
        max_corrupt_recipients: 1,
        max_unavailable_recipients: 1,
        max_contributions_per_entity: 1,
    };
    let mut ledger = Ledger::open(path, authority, context.issuer, &context.parent)?;
    ledger.begin(&context)?;
    let inputs = [(16, 16), (-8, -16), (24, 8)];
    // The public reference path is independent of the private relation's local_update.
    let start = Instant::now();
    let reference = crate::evaluate(&crate::Batch {
        w: 8,
        x: [16, -8, 24],
        y: [16, -16, 8],
        counts: [1, 2, 1],
    })?;
    seconds.insert("train", start.elapsed().as_secs_f64());
    let mut application_bytes = 0;
    for (i, (x, y)) in inputs.into_iter().enumerate() {
        let start = Instant::now();
        let witness = Witness::new(x, y);
        *seconds.entry("witness").or_default() += start.elapsed().as_secs_f64();
        let start = Instant::now();
        let (contribution, packets) = clients[i].contribute(&context, &parameters, witness)?;
        *seconds.entry("prove").or_default() += start.elapsed().as_secs_f64();
        // Four public-envelope deliveries plus three logical private messages.
        // A private message has three 32-byte IDs, one role byte and two scalars.
        let start = Instant::now();
        application_bytes += 4 * encoded(&contribution)?.len() + 3 * (3 * 32 + 1 + 2 * 32);
        *seconds.entry("communicate").or_default() += start.elapsed().as_secs_f64();
        let start = Instant::now();
        let acks: Vec<_> = packets
            .into_iter()
            .enumerate()
            .map(|(j, packet)| recipients[j].receive(&context, &parameters, &contribution, packet))
            .collect::<Result<_>>()?;
        ledger.admit(&context, &parameters, &contribution, &acks)?;
        *seconds.entry("verify").or_default() += start.elapsed().as_secs_f64();
        application_bytes += encoded(&acks)?.len();
    }
    let start = Instant::now();
    let (root, accepted) = ledger.freeze(&context)?;
    let permit = ledger.reserve(&context, root, [1; 32])?;
    seconds.insert("prepare", start.elapsed().as_secs_f64());
    let start = Instant::now();
    let shares = recipients
        .iter()
        .map(|node| node.aggregate(&context, &permit, &accepted))
        .collect::<Result<Vec<_>>>()?;
    seconds.insert("aggregate", start.elapsed().as_secs_f64());
    application_bytes += 3 * encoded(&permit)?.len() + encoded(&shares)?.len();
    let start = Instant::now();
    let result = ledger.finish(&context, &permit, &shares[..2], [1; 32])?;
    seconds.insert("release", start.elapsed().as_secs_f64());
    application_bytes += encoded(&result)?.len();
    ensure(
        result.model == reference.output
            && result.model == 9
            && result.weighted_sum == 36
            && result.denominator == 4,
        "synthetic-reference-mismatch",
    )?;
    ensure(ledger.release_count()? == 1, "duplicate-demo-release")?;
    Ok(DemoReport {
        version: "v0.2-protected-aggregation",
        model: result.model,
        weighted_sum: result.weighted_sum,
        denominator: result.denominator,
        reference_match: true,
        accepted_clients: 3,
        recipients: 3,
        threshold: 2,
        seconds,
        application_bytes,
        parameters_id: parameters.parameters_id,
        key_id: parameters.key_id,
        relation_id: Parameters::relation_id()?,
        release_id: result.release_id,
        accepted_root: result.accepted_root,
        observation: ledger
            .observation(&context)?
            .ok_or(ContractError("missing-observation"))?,
        limitations: vec![
            "Original synthetic scalar fixture; all roles share one native process, authenticated private delivery is an API assumption, no network isolation demonstrated.",
            "One measurement is not a performance study. Prove includes circuit witness synthesis, commitments, signatures and share construction; witness is host input/blinding creation only.",
            "Communication counts logical application fields and public canonical JSON with delivery multiplicity; excludes context/key distribution, transport, TLS, retransmission and storage traffic. Communicate time covers initial envelope encoding only, not a network measurement.",
            "Peak memory is the joint process RSS including all roles, SQLite and setup. No per-role memory attribution.",
            "Local randomized Groth16 setup, custom Pedersen generator derivation and composition require independent review; no production or 128-bit security claim.",
            "Privacy tolerates at most one colluding recipient plus an honest-but-curious coordinator, conditioned on the permitted clean aggregate. No DP guarantee or personhood claim.",
            "All three availability receipts required before freeze; two verified recipients needed after freeze. Trusted non-rollbackable authority/storage and issuer; no unconditional liveness.",
        ],
    })
}
