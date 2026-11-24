//! Fixed public fixture runner and bounded audit; never logs commitment openings.
use fzkml_core::{Batch, ContractError, private::*};
use rand::{RngCore, SeedableRng, rngs::StdRng};
use std::{
    io::{self, Read},
    time::Instant,
};

fn hex(data: &[u8]) -> String {
    let digits = b"0123456789abcdef";
    let mut result = String::with_capacity(data.len() * 2);
    for b in data {
        result.push(char::from(digits[usize::from(b >> 4)]));
        result.push(char::from(digits[usize::from(b & 15)]));
    }
    result
}
fn unhex(text: &str) -> Result<[u8; 84], ContractError> {
    if text.len() != 168
        || !text
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    {
        return Err(ContractError("canonical-hex"));
    }
    let mut out = [0; 84];
    for i in 0..84 {
        out[i] = u8::from_str_radix(&text[i * 2..i * 2 + 2], 16)
            .map_err(|_| ContractError("canonical-hex"))?;
    }
    Ok(out)
}
fn require(value: bool, code: &'static str) -> Result<(), ContractError> {
    if value {
        Ok(())
    } else {
        Err(ContractError(code))
    }
}

fn smoke(fuzz_cases: usize) -> Result<(), ContractError> {
    let start = Instant::now();
    let session = PrivateSession::setup()?;
    let setup_s = start.elapsed().as_secs_f64();
    let batch = Batch {
        w: 8,
        x: [16, -8, 24],
        y: [16, -16, 8],
        counts: [1, 2, 1],
    };
    let input = batch.encode()?;
    let context = Context::synthetic(session.key_id(), batch.counts);
    let prepared = session.prepare(&input, context.clone())?;
    let expected = prepared.precommit();
    let repeated_opening = session.prepare(&input, context.clone())?;
    require(
        prepared.statement().model_commitment != repeated_opening.statement().model_commitment
            && prepared.statement().data_commitment != repeated_opening.statement().data_commitment,
        "fresh-opening-reused",
    )?;
    require(
        prepared.statement().output == 9,
        "reference-function-mismatch",
    )?;
    let proved = session.prove(prepared)?;
    let start = Instant::now();
    let valid = session.verify(&expected, &proved.bytes)?;
    let verification_s = start.elapsed().as_secs_f64();
    require(valid, "honest-proof-rejected")?;
    let start = Instant::now();
    let original = Envelope::decode(&proved.bytes)?;
    let mut substitutions = 0;
    for field in 0..12 {
        let mut changed = Envelope::decode(&proved.bytes)?;
        match field {
            0 => changed.statement.model_commitment[0] ^= 1,
            1 => changed.statement.data_commitment[0] ^= 1,
            2 => changed.statement.context.session[0] ^= 1,
            3 => changed.statement.context.round += 1,
            4 => changed.statement.context.parent[0] ^= 1,
            5 => changed.statement.context.roster.swap(0, 1),
            6 => changed.statement.context.counts[0] = 2,
            7 => changed.statement.output += 1,
            8 => changed.statement.context.model_version[0] ^= 1,
            9 => changed.statement.context.data_policy[0] ^= 1,
            10 => changed.statement.context.optimizer[0] ^= 1,
            _ => changed.statement.context.key_id[0] ^= 1,
        }
        require(
            !session
                .verify(&expected, &changed.encode())
                .unwrap_or(false),
            "substitution-accepted",
        )?;
        // Check cryptographic/configuration binding, beyond the expected-record check.
        require(
            !session
                .verify(&changed.statement.precommit(), &changed.encode())
                .unwrap_or(false),
            "proof-reuse-accepted",
        )?;
        substitutions += 1;
    }
    let mut unsupported = context.clone();
    unsupported.optimizer[0] ^= 1;
    require(
        session.prepare(&input, unsupported).is_err(),
        "unsupported-optimizer-accepted",
    )?;
    let mut wrong_key = context.clone();
    wrong_key.key_id[0] ^= 1;
    require(
        session.prepare(&input, wrong_key).is_err(),
        "wrong-key-accepted",
    )?;
    let mut other_context = context;
    other_context.session[0] ^= 1;
    let other_prepared = session.prepare(&input, other_context)?;
    let other_expected = other_prepared.precommit();
    require(
        other_expected.model_commitment != expected.model_commitment
            && other_expected.data_commitment != expected.data_commitment,
        "context-domain-separation-failed",
    )?;
    let fresh = session.prove(other_prepared)?;
    require(
        session.verify(&other_expected, &fresh.bytes)?,
        "fresh-approved-proof-rejected",
    )?;
    require(
        !session.verify(&expected, &fresh.bytes)?,
        "fresh-wrong-statement-accepted",
    )?;
    let mut state = ConsumptionState::new(expected.clone());
    let receipt = state.accept(&session, &proved.bytes)?;
    require(
        session.verify(&expected, &proved.bytes)?,
        "validity-confused-with-consumption",
    )?;
    require(
        state.accept(&session, &proved.bytes).is_err() && state.receipt() == Some(receipt),
        "replay-consumed-twice",
    )?;
    let mut rng = StdRng::seed_from_u64(20261124);
    for _ in 0..fuzz_cases {
        let mut mutated = proved.bytes;
        let index = rng.next_u32() as usize % mutated.len();
        mutated[index] ^= 1 << (rng.next_u32() % 8);
        if let Ok(parsed) = Envelope::decode(&mutated) {
            require(parsed.encode() == mutated, "noncanonical-envelope-accepted")?;
        }
        require(
            !session.verify(&expected, &mutated).unwrap_or(false),
            "fuzz-mutant-accepted",
        )?;
    }
    for offset in [0, 8, 10, 12, 44, 444] {
        let mut mutated = proved.bytes;
        mutated[offset] ^= 1;
        require(
            Envelope::decode(&mutated).is_err(),
            "framing-mutation-accepted",
        )?;
    }
    let validation_s = start.elapsed().as_secs_f64();
    println!(
        "{{\"contract_version\":\"fzk-private-1.0.0\",\"numeric_contract\":\"fzknum-1.0.0\",\"verified\":true,\"output\":9,\"proof_bytes\":128,\"envelope_bytes\":576,\"constraints\":{},\"public_field_count\":101,\"setup_seconds\":{},\"witness_seconds\":{},\"proving_seconds\":{},\"verification_seconds\":{},\"validation_seconds\":{},\"key_id\":\"{}\",\"parameters_id\":\"{}\",\"statement_digest\":\"{}\",\"substitutions_rejected\":{},\"fuzz_cases\":{},\"fresh_allowed_proof_verified\":true,\"wrong_expected_rejected\":true,\"replay_rejected\":true}}",
        session.constraints(),
        setup_s,
        proved.witness_seconds,
        proved.proving_seconds,
        verification_s,
        validation_s,
        hex(&session.key_id()),
        hex(&session.parameters_id()),
        hex(&hash(&original.statement.encode())),
        substitutions,
        fuzz_cases
    );
    Ok(())
}
fn audit() -> Result<(), ContractError> {
    let mut text = String::new();
    io::stdin()
        .take(819_201)
        .read_to_string(&mut text)
        .map_err(|_| ContractError("audit-input"))?;
    if text.len() > 819_200 {
        return Err(ContractError("audit-input-limit"));
    }
    let mut count = 0;
    let mut constraints = 0;
    for line in text.lines() {
        if line.len() > 200 || count == 4096 {
            return Err(ContractError("audit-case-limit"));
        }
        let (encoded, output) = line.split_once(' ').ok_or(ContractError("audit-record"))?;
        let expected: i64 = output.parse().map_err(|_| ContractError("audit-output"))?;
        if !(-80..=80).contains(&expected) {
            return Err(ContractError("audit-output"));
        }
        let (satisfied, n, public) = constraint_audit_details(&unhex(encoded)?, expected)?;
        require(
            satisfied && public == 102,
            "private-circuit-oracle-mismatch",
        )?;
        if count != 0 {
            require(constraints == n, "value-dependent-circuit-shape")?;
        }
        constraints = n;
        count += 1;
    }
    require(count > 0, "empty-audit")?;
    println!(
        "{{\"contract_version\":\"fzk-private-1.0.0\",\"fixture_version\":\"numeric-v1\",\"cases\":{count},\"constraints\":{constraints},\"public_field_count\":101,\"all_satisfied\":true}}"
    );
    Ok(())
}
fn main() {
    let args: Vec<_> = std::env::args().take(4).collect();
    let result = match args.get(1).map(String::as_str) {
        Some("audit") if args.len() == 2 => audit(),
        Some("smoke") if args.len() == 2 => smoke(256),
        Some("smoke") if args.len() == 3 => args[2]
            .parse::<usize>()
            .ok()
            .filter(|n| *n <= 16384)
            .ok_or(ContractError("fuzz-budget"))
            .and_then(smoke),
        _ => Err(ContractError(
            "usage: fzkml-private smoke [0..16384] | audit",
        )),
    };
    if let Err(error) = result {
        eprintln!("{error}");
        std::process::exit(2);
    }
}
