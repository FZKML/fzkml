use super::crypto::{commit, decode_point, scalar_decode};
use super::roles::{Packet, accepted_root};
use super::*;
use ark_ed_on_bn254::Fr as Scalar;
use ark_ff::Field;
use ed25519_dalek::SigningKey;
use rand::{RngCore, rngs::OsRng};
use std::{path::PathBuf, sync::Arc, time::Instant};

struct Directory(PathBuf);
impl Directory {
    fn new() -> Self {
        let mut id = [0u8; 16];
        OsRng.fill_bytes(&mut id);
        let path =
            std::env::temp_dir().join(format!("fzkml-aggregation-{:x}", u128::from_le_bytes(id)));
        std::fs::create_dir(&path).unwrap();
        Self(path)
    }
    fn db(&self) -> PathBuf {
        self.0.join("ledger.sqlite")
    }
}
impl Drop for Directory {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

struct Fixture {
    context: Context,
    parameters: Arc<Parameters>,
    authority: SigningKey,
    issuer: SigningKey,
    clients: Vec<Client>,
    recipients: Vec<Recipient>,
    recipient_keys: Vec<SigningKey>,
}
impl Fixture {
    fn new() -> Self {
        let authority = SigningKey::generate(&mut OsRng);
        let issuer = SigningKey::generate(&mut OsRng);
        let recipient_keys: Vec<_> = (0..3).map(|_| SigningKey::generate(&mut OsRng)).collect();
        let recipients: Vec<_> = recipient_keys
            .iter()
            .enumerate()
            .map(|(i, key)| Recipient::new((i + 1) as u8, key.clone()).unwrap())
            .collect();
        let clients = (1u8..=3)
            .map(|i| {
                let key = SigningKey::generate(&mut OsRng);
                let credential = Credential::issue(
                    &issuer,
                    [i; 32],
                    [i + 10; 32],
                    key.verifying_key().to_bytes(),
                    0,
                    1000,
                )
                .unwrap();
                Client::new(key, credential).unwrap()
            })
            .collect();
        let parameters = Arc::new(Parameters::setup().unwrap());
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
        Self {
            context,
            parameters,
            authority,
            issuer,
            clients,
            recipients,
            recipient_keys,
        }
    }
    fn ledger(&self, path: &std::path::Path) -> Ledger {
        Ledger::open(
            path,
            self.authority.clone(),
            self.context.issuer,
            &self.context.parent,
        )
        .unwrap()
    }
    fn contribution(&self, index: usize) -> (Contribution, [Packet; 3]) {
        let values = [(16, 16), (-8, -16), (24, 8)];
        self.clients[index]
            .contribute(
                &self.context,
                &self.parameters,
                &Witness::new(values[index].0, values[index].1),
            )
            .unwrap()
    }
    fn deliver(&mut self, c: &Contribution, packets: [Packet; 3]) -> Vec<Availability> {
        packets
            .into_iter()
            .enumerate()
            .map(|(i, packet)| {
                self.recipients[i]
                    .receive(&self.context, &self.parameters, c, packet)
                    .unwrap()
            })
            .collect()
    }
}

#[test]
fn actual_proof_bound_three_client_aggregate_and_adversaries() {
    let start = Instant::now();
    let mut f = Fixture::new();
    let directory = Directory::new();
    let mut ledger = f.ledger(&directory.db());
    ledger.begin(&f.context).unwrap();
    let (c0, mut packets) = f.contribution(0);
    assert!(f.parameters.verify(&f.context, &c0).unwrap());
    // D.2: keep a valid proof but replace the exact delivered share.
    packets[0].share += Scalar::ONE;
    let [bad, _, _] = packets;
    assert!(
        f.recipients[0]
            .receive(&f.context, &f.parameters, &c0, bad)
            .is_err()
    );
    let (c0, packets) = f.contribution(0);
    let acks = f.deliver(&c0, packets);
    let (equivocated, packets) = f.contribution(0);
    let [packet, _, _] = packets;
    assert!(
        f.recipients[0]
            .receive(&f.context, &f.parameters, &equivocated, packet)
            .is_err()
    );
    let mut substituted = c0.clone();
    substituted.output = c0.data.clone();
    assert!(!f.parameters.verify(&f.context, &substituted).unwrap());
    let mut wrong = f.context.clone();
    wrong.session = [9; 32];
    assert!(f.parameters.verify(&wrong, &c0).is_err());
    wrong = f.context.clone();
    wrong.parent.model = 7;
    assert!(f.parameters.verify(&wrong, &c0).is_err());
    wrong = f.context.clone();
    wrong.encoding = "low-rank-norm-only".into();
    assert!(wrong.validate().is_err());
    wrong = f.context.clone();
    wrong.parent.optimizer = "momentum".into();
    wrong.parent.momentum = Some(vec![1]);
    assert!(wrong.validate().is_err());
    wrong = f.context.clone();
    wrong.parent.value_kind = "delta".into();
    assert!(wrong.validate().is_err());
    wrong = f.context.clone();
    wrong.max_corrupt_recipients = 2;
    assert!(wrong.validate().is_err());
    assert!(
        ledger
            .admit(&f.context, &f.parameters, &c0, &acks[..2])
            .is_err()
    );
    ledger.admit(&f.context, &f.parameters, &c0, &acks).unwrap();
    assert!(ledger.admit(&f.context, &f.parameters, &c0, &acks).is_err());
    assert!(ledger.freeze(&f.context).is_err());
    for i in 1..3 {
        let (c, packets) = f.contribution(i);
        let acks = f.deliver(&c, packets);
        ledger.admit(&f.context, &f.parameters, &c, &acks).unwrap();
    }
    let (root, accepted) = ledger.freeze(&f.context).unwrap();
    assert!(ledger.observation(&f.context).unwrap().is_none());
    let permit = ledger.reserve(&f.context, root, [1; 32]).unwrap();
    assert_eq!(
        ledger.observation(&f.context).unwrap().unwrap().kind,
        "possibly-exposed-clean-sum"
    );
    let shares: Vec<_> = f
        .recipients
        .iter()
        .map(|node| node.aggregate(&f.context, &permit, &accepted).unwrap())
        .collect();
    // One missing/malicious recipient is tolerable; two are not.
    assert!(
        ledger
            .finish(&f.context, &permit, &shares[..1], [1; 32])
            .is_err()
    );
    let mut tampered = shares[0].clone();
    tampered.share[0] ^= 1;
    assert!(tampered.verify(&f.context, &permit, &accepted).is_err());
    let mut unauthorized = permit.clone();
    unauthorized.signature[0] ^= 1;
    assert!(
        f.recipients[0]
            .aggregate(&f.context, &unauthorized, &accepted)
            .is_err()
    );
    let mut omitted = accepted.clone();
    omitted.pop();
    assert!(
        f.recipients[0]
            .aggregate(&f.context, &permit, &omitted)
            .is_err()
    );
    let mut duplicated = accepted.clone();
    duplicated[1] = duplicated[0].clone();
    assert!(accepted_root(&f.context, &duplicated).is_err());
    let mut weights = accepted.clone();
    weights[0].weight += 1;
    assert!(accepted_root(&f.context, &weights).is_err());
    assert!(
        ledger
            .finish(
                &f.context,
                &permit,
                &[shares[0].clone(), shares[0].clone()],
                [1; 32]
            )
            .is_err()
    );
    let result = ledger
        .finish(&f.context, &permit, &shares[1..], [1; 32])
        .unwrap();
    assert_eq!(
        (result.weighted_sum, result.denominator, result.model),
        (36, 4, 9)
    );
    assert_eq!(result.child.sequence, 1);
    assert_eq!(
        ledger
            .finish(&f.context, &permit, &shares[..2], [2; 32])
            .unwrap(),
        result
    );
    assert_eq!(ledger.release_count().unwrap(), 1);
    assert!(ledger.abort(&f.context, [3; 32]).is_err());
    drop(ledger);
    let recovered = f.ledger(&directory.db());
    assert_eq!(recovered.recovered(&f.context).unwrap(), Some(result));
    assert_eq!(recovered.release_count().unwrap(), 1);
    drop(recovered);
    let mut recovered = f.ledger(&directory.db());
    assert!(recovered.begin(&f.context).is_err());
    let mut replay = f.context.clone();
    replay.round = 1;
    replay.parent.sequence = 1;
    assert!(recovered.admit(&replay, &f.parameters, &c0, &acks).is_err());
    assert_eq!(
        recovered.observation(&f.context).unwrap().unwrap().kind,
        "exposed-clean-sum"
    );
    eprintln!(
        "protected fixture elapsed seconds {:.3}",
        start.elapsed().as_secs_f64()
    );
}

#[test]
fn concurrent_admission_and_abort_accounting() {
    let mut f = Fixture::new();
    let directory = Directory::new();
    let mut ledger = f.ledger(&directory.db());
    ledger.begin(&f.context).unwrap();
    let (c, packets) = f.contribution(0);
    let acks = f.deliver(&c, packets);
    let mut revoked_credential = c.credential.clone();
    revoked_credential.signature[0] ^= 1;
    assert!(revoked_credential.verify(&f.context).is_err());
    let expired = Credential::issue(
        &f.issuer,
        c.credential.serial,
        c.credential.entity,
        c.credential.public_key,
        1,
        2,
    )
    .unwrap();
    assert!(expired.verify(&f.context).is_err());
    let joins: Vec<_> = (0..4)
        .map(|_| {
            let path = directory.db();
            let context = f.context.clone();
            let parameters = f.parameters.clone();
            let authority = f.authority.clone();
            let c = c.clone();
            let acks = acks.clone();
            std::thread::spawn(move || {
                let mut db =
                    Ledger::open(&path, authority, context.issuer, &context.parent).unwrap();
                db.admit(&context, &parameters, &c, &acks).is_ok()
            })
        })
        .collect();
    assert_eq!(
        joins
            .into_iter()
            .filter_map(|join| join.join().ok())
            .filter(|x| *x)
            .count(),
        1
    );
    ledger.abort(&f.context, [4; 32]).unwrap();
    assert!(ledger.observation(&f.context).unwrap().is_none());
    // Same session/round cannot be reinterpreted with changed weight/roster metadata.
    let mut different = f.context.clone();
    different.weights = [1, 1, 1];
    assert!(ledger.begin(&different).is_err());
    let directory = Directory::new();
    let mut ledger = f.ledger(&directory.db());
    ledger.begin(&f.context).unwrap();
    ledger.admit(&f.context, &f.parameters, &c, &acks).unwrap();
    for i in 1..3 {
        let (c, packets) = f.contribution(i);
        let acks = f.deliver(&c, packets);
        ledger.admit(&f.context, &f.parameters, &c, &acks).unwrap();
    }
    let (root, accepted) = ledger.freeze(&f.context).unwrap();
    let permit = ledger.reserve(&f.context, root, [5; 32]).unwrap();
    let shares: Vec<_> = f
        .recipients
        .iter()
        .take(2)
        .map(|node| node.aggregate(&f.context, &permit, &accepted).unwrap())
        .collect();
    assert_eq!(
        ledger
            .observe_sum(&f.context, &permit, &shares, [5; 32])
            .unwrap()
            .0,
        36
    );
    ledger.abort(&f.context, [5; 32]).unwrap();
    drop(ledger);
    let mut ledger = f.ledger(&directory.db());
    assert_eq!(
        ledger.observation(&f.context).unwrap().unwrap().release_id,
        permit.release_id
    );
    assert_eq!(
        ledger.observation(&f.context).unwrap().unwrap().kind,
        "exposed-clean-sum"
    );
    assert!(ledger.reserve(&f.context, root, [6; 32]).is_err());
    assert_eq!(ledger.release_count().unwrap(), 0);
}

#[test]
fn vss_threshold_privacy_and_malformed_boundaries() {
    // Independent small algebra oracle: one share admits every possible secret;
    // two shares reconstruct it. This is not a proof of the full composition.
    for value in 0..160u64 {
        let s = Scalar::from(19u64);
        let a = s - Scalar::from(value);
        assert_eq!(Scalar::from(value) + a, s);
    }
    let value = Scalar::from(90u64);
    let a = Scalar::from(7u64);
    let blind = Scalar::from(11u64);
    let b = Scalar::from(13u64);
    let c0 = commit(value, blind);
    let c1 = commit(a, b);
    for j in 1..=3u64 {
        let x = Scalar::from(j);
        assert_eq!(commit(value + x * a, blind + x * b), c0 + c1 * x);
    }
    assert!(decode_point(&[255; 32]).is_err());
    assert!(scalar_decode(&[255; 32]).is_err());
    assert!(local_update(33, 0, 0).is_err());
    let mut state = State::new(8);
    let old = state.id().unwrap();
    state.preprocessing = [9; 32];
    assert_ne!(old, state.id().unwrap());
    state.error_feedback = Some(vec![1]);
    assert!(state.id().is_err());
}

#[derive(serde::Serialize, serde::Deserialize)]
struct CrashInput {
    authority: [u8; 32],
    context: Context,
    root: Id,
    permit: Option<Permit>,
    shares: Vec<AggregateShare>,
}
fn private_input(path: &std::path::Path, input: &CrashInput) {
    use std::io::Write;
    let mut options = std::fs::OpenOptions::new();
    options.create_new(true).write(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options.open(path).unwrap();
    file.write_all(&encoded(input).unwrap()).unwrap();
    file.sync_all().unwrap();
}

// Subprocess entry point: ordinary test discovery performs no protocol operation.
#[test]
fn crash_worker() {
    let Ok(path) = std::env::var("FZKML_PRIVATE_CRASH_INPUT") else {
        return;
    };
    let input: CrashInput = serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
    let db = PathBuf::from(path).parent().unwrap().join("ledger.sqlite");
    let mut ledger = Ledger::open(
        &db,
        SigningKey::from_bytes(&input.authority),
        input.context.issuer,
        &input.context.parent,
    )
    .unwrap();
    if let Some(permit) = input.permit {
        ledger
            .finish(&input.context, &permit, &input.shares, [21; 32])
            .unwrap();
        std::process::exit(78); // outbox committed, delivery acknowledgment lost
    }
    ledger
        .reserve(&input.context, input.root, [20; 32])
        .unwrap();
    std::process::exit(77); // reservation committed, computation/delivery may not occur
}

#[test]
fn actual_process_crash_reservation_and_lost_delivery_recovery() {
    let mut f = Fixture::new();
    let directory = Directory::new();
    let mut ledger = f.ledger(&directory.db());
    ledger.begin(&f.context).unwrap();
    for i in 0..3 {
        let (c, packets) = f.contribution(i);
        let acks = f.deliver(&c, packets);
        ledger.admit(&f.context, &f.parameters, &c, &acks).unwrap();
    }
    let (root, accepted) = ledger.freeze(&f.context).unwrap();
    drop(ledger);
    let input = directory.0.join("reserve-private.json");
    private_input(
        &input,
        &CrashInput {
            authority: f.authority.to_bytes(),
            context: f.context.clone(),
            root,
            permit: None,
            shares: vec![],
        },
    );
    let status = std::process::Command::new(std::env::current_exe().unwrap())
        .args(["--exact", "aggregation::tests::crash_worker", "--nocapture"])
        .env("FZKML_PRIVATE_CRASH_INPUT", &input)
        .status()
        .unwrap();
    assert_eq!(status.code(), Some(77));
    let mut ledger = f.ledger(&directory.db());
    assert_eq!(
        ledger.observation(&f.context).unwrap().unwrap().kind,
        "possibly-exposed-clean-sum"
    );
    let permit = ledger.reserve(&f.context, root, [21; 32]).unwrap();
    let shares: Vec<_> = f
        .recipients
        .iter()
        .take(2)
        .map(|node| node.aggregate(&f.context, &permit, &accepted).unwrap())
        .collect();
    drop(ledger);
    let input = directory.0.join("finish-private.json");
    private_input(
        &input,
        &CrashInput {
            authority: f.authority.to_bytes(),
            context: f.context.clone(),
            root,
            permit: Some(permit.clone()),
            shares: shares.clone(),
        },
    );
    let status = std::process::Command::new(std::env::current_exe().unwrap())
        .args(["--exact", "aggregation::tests::crash_worker", "--nocapture"])
        .env("FZKML_PRIVATE_CRASH_INPUT", &input)
        .status()
        .unwrap();
    assert_eq!(status.code(), Some(78));
    let mut ledger = f.ledger(&directory.db());
    let recovered = ledger.recovered(&f.context).unwrap().unwrap();
    assert_eq!(recovered.model, 9);
    assert_eq!(ledger.release_count().unwrap(), 1);
    assert_eq!(
        ledger
            .finish(&f.context, &permit, &shares, [22; 32])
            .unwrap(),
        recovered
    );
    assert_eq!(ledger.release_count().unwrap(), 1);
}

#[test]
fn issuer_entity_quota_revocation_and_unavailable_storage() {
    let mut f = Fixture::new();
    let directory = Directory::new();
    let mut ledger = f.ledger(&directory.db());
    ledger.begin(&f.context).unwrap();
    let (c0, packets) = f.contribution(0);
    let acks = f.deliver(&c0, packets);
    ledger.admit(&f.context, &f.parameters, &c0, &acks).unwrap();
    let key = SigningKey::generate(&mut OsRng);
    let credential = Credential::issue(
        &f.issuer,
        [2; 32],
        c0.credential.entity,
        key.verifying_key().to_bytes(),
        0,
        1000,
    )
    .unwrap();
    let second = Client::new(key, credential).unwrap();
    let (c1, packets) = second
        .contribute(&f.context, &f.parameters, &Witness::new(-8, -16))
        .unwrap();
    let acks = f.deliver(&c1, packets);
    assert!(ledger.admit(&f.context, &f.parameters, &c1, &acks).is_err());
    let (c2, packets) = f.contribution(2);
    let acks = f.deliver(&c2, packets);
    ledger.revoke(c2.credential.serial).unwrap();
    assert!(ledger.admit(&f.context, &f.parameters, &c2, &acks).is_err());
    let missing = Recipient::new(1, SigningKey::generate(&mut OsRng)).unwrap();
    let fake = Permit {
        context: f.context.id().unwrap(),
        accepted_root: [0; 32],
        release_id: [0; 32],
        signature: vec![0; 64],
    };
    assert!(missing.aggregate(&f.context, &fake, &[c0, c1, c2]).is_err());
}

#[test]
fn conflicting_disclosures_and_lost_recipient_storage() {
    let mut f = Fixture::new();
    let directory = Directory::new();
    let mut ledger = f.ledger(&directory.db());
    ledger.begin(&f.context).unwrap();
    for i in 0..3 {
        let (c, packets) = f.contribution(i);
        let acks = f.deliver(&c, packets);
        ledger.admit(&f.context, &f.parameters, &c, &acks).unwrap();
    }
    let (root, accepted) = ledger.freeze(&f.context).unwrap();
    let permit = ledger.reserve(&f.context, root, [30; 32]).unwrap();
    let missing = Recipient::new(1, f.recipient_keys[0].clone()).unwrap();
    assert!(missing.aggregate(&f.context, &permit, &accepted).is_err());
    let old = f.context.clone();
    ledger.abort(&old, [30; 32]).unwrap();
    f.context.session = [99; 32];
    ledger.begin(&f.context).unwrap();
    for i in 0..3 {
        let (c, packets) = f.contribution(i);
        let acks = f.deliver(&c, packets);
        ledger.admit(&f.context, &f.parameters, &c, &acks).unwrap();
    }
    let (root, _) = ledger.freeze(&f.context).unwrap();
    assert!(ledger.reserve(&f.context, root, [31; 32]).is_err());
    assert_eq!(
        ledger.observation(&old).unwrap().unwrap().kind,
        "possibly-exposed-clean-sum"
    );
    assert_eq!(ledger.release_count().unwrap(), 0);
}
