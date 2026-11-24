//! Candidate private-witness relation. Hiding is conditional on the stated hash/
//! proof/setup assumptions; this module is not a reviewed production protocol.
use crate::proof::{arithmetic, bound, field};
use crate::{Batch, ContractError, Witness, evaluate};
use ark_bn254::{Bn254, Fr};
use ark_crypto_primitives::crh::sha256::constraints::Sha256Gadget;
use ark_ff::{AdditiveGroup, PrimeField};
use ark_groth16::{Groth16, PreparedVerifyingKey, Proof, ProvingKey, prepare_verifying_key};
use ark_r1cs_std::{
    alloc::{AllocVar, AllocationMode},
    convert::ToBitsGadget,
    eq::EqGadget,
    fields::fp::FpVar,
    uint8::UInt8,
};
use ark_relations::r1cs::{
    ConstraintSynthesizer, ConstraintSystem, ConstraintSystemRef, SynthesisError,
};
use ark_serialize::{CanonicalDeserialize, CanonicalSerialize};
use rand::{RngCore, rngs::OsRng};
use sha2::{Digest, Sha256};
use std::time::Instant;

pub const CONTEXT_BYTES: usize = 392;
pub const STATEMENT_BYTES: usize = 472;
pub const ENVELOPE_BYTES: usize = 652;
pub const MODEL_DOMAIN: &[u8; 8] = b"FZKMOD02";
pub const DATA_DOMAIN: &[u8; 8] = b"FZKDAT02";

pub fn hash(data: &[u8]) -> [u8; 32] {
    Sha256::digest(data).into()
}
pub fn numeric_id() -> [u8; 32] {
    hash(include_bytes!("../../../specs/numeric-contract-v1.json"))
}
pub fn contract_id() -> [u8; 32] {
    hash(include_bytes!("../../../specs/private-transition-v2.json"))
}
pub fn backend_id() -> [u8; 32] {
    hash(b"fzkml.backend.ark-groth16-0.5.0.bn254.private-v2.local-research")
}
pub fn model_id() -> [u8; 32] {
    hash(b"fzkml.model.linear-1x1.no-bias.v1")
}
pub fn initialization_id() -> [u8; 32] {
    hash(b"fzkml.initialization.authorized-parent-value.v1")
}
pub fn preprocessing_id() -> [u8; 32] {
    hash(b"fzkml.preprocessing.identity.v1")
}
pub fn data_policy_id() -> [u8; 32] {
    hash(b"fzkml.data.synthetic-identity-three-client.v1")
}
pub fn optimizer_id() -> [u8; 32] {
    hash(b"fzkml.optimizer.fixed16.sgd-1of4.v1")
}
fn domain() -> Fr {
    Fr::from_le_bytes_mod_order(&contract_id()[..31])
}

fn append(output: &mut [u8], offset: &mut usize, value: &[u8]) {
    output[*offset..*offset + value.len()].copy_from_slice(value);
    *offset += value.len();
}
fn take<const N: usize>(input: &[u8], offset: &mut usize) -> Result<[u8; N], ContractError> {
    let value = input
        .get(*offset..*offset + N)
        .ok_or(ContractError("truncated"))?
        .try_into()
        .map_err(|_| ContractError("truncated"))?;
    *offset += N;
    Ok(value)
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Context {
    pub session: [u8; 16],
    pub round: u64,
    /// Trusted previous full-state value; the circuit constrains its hidden input to it.
    pub parent_value: i64,
    pub parent: [u8; 32],
    pub roster: [[u8; 16]; 3],
    pub counts: [u32; 3],
    pub model_version: [u8; 32],
    pub preprocessing: [u8; 32],
    pub initialization: [u8; 32],
    pub local_step_count: u32,
    pub data_policy: [u8; 32],
    pub optimizer: [u8; 32],
    pub relation: [u8; 32],
    pub contract: [u8; 32],
    pub key_id: [u8; 32],
}
impl Context {
    /// Public test scenario; not authentication or authorization of a real client.
    pub fn synthetic(key_id: [u8; 32], counts: [u32; 3], parent_value: i64) -> Self {
        Self {
            session: [7; 16],
            round: 1,
            parent_value,
            parent: hash(b"synthetic-genesis"),
            roster: [[1; 16], [2; 16], [3; 16]],
            counts,
            model_version: model_id(),
            preprocessing: preprocessing_id(),
            initialization: initialization_id(),
            local_step_count: 1,
            data_policy: data_policy_id(),
            optimizer: optimizer_id(),
            relation: numeric_id(),
            contract: contract_id(),
            key_id,
        }
    }
    pub fn validate(&self) -> Result<(), ContractError> {
        if self.session == [0; 16]
            || self.round == 0
            || self.round > u64::from(u32::MAX)
            || !(-80..=80).contains(&self.parent_value)
            || self.roster.contains(&[0; 16])
            || self.roster[0] == self.roster[1]
            || self.roster[0] == self.roster[2]
            || self.roster[1] == self.roster[2]
            || self.counts.iter().any(|n| !(1..=4).contains(n))
            || self.local_step_count != 1
        {
            return Err(ContractError("context-shape-or-range"));
        }
        if self.model_version != model_id()
            || self.preprocessing != preprocessing_id()
            || self.initialization != initialization_id()
            || self.data_policy != data_policy_id()
            || self.optimizer != optimizer_id()
            || self.relation != numeric_id()
            || self.contract != contract_id()
        {
            return Err(ContractError("unsupported-configuration"));
        }
        Ok(())
    }
    pub fn encode(&self) -> [u8; CONTEXT_BYTES] {
        let mut output = [0; CONTEXT_BYTES];
        let mut p = 0;
        append(&mut output, &mut p, b"FZKCTX02");
        append(&mut output, &mut p, &self.session);
        append(&mut output, &mut p, &self.round.to_le_bytes());
        append(&mut output, &mut p, &self.parent_value.to_le_bytes());
        append(&mut output, &mut p, &self.parent);
        for id in self.roster {
            append(&mut output, &mut p, &id);
        }
        for n in self.counts {
            append(&mut output, &mut p, &n.to_le_bytes());
        }
        for id in [self.model_version, self.preprocessing, self.initialization] {
            append(&mut output, &mut p, &id);
        }
        append(&mut output, &mut p, &self.local_step_count.to_le_bytes());
        for id in [
            self.data_policy,
            self.optimizer,
            self.relation,
            self.contract,
            self.key_id,
        ] {
            append(&mut output, &mut p, &id);
        }
        output
    }
    pub fn decode(input: &[u8]) -> Result<Self, ContractError> {
        if input.len() != CONTEXT_BYTES || &input[..8] != b"FZKCTX02" {
            return Err(ContractError("context-canonical-length-or-version"));
        }
        let mut p = 8;
        let session = take(input, &mut p)?;
        let round = u64::from_le_bytes(take(input, &mut p)?);
        let parent_value = i64::from_le_bytes(take(input, &mut p)?);
        let parent = take(input, &mut p)?;
        let roster = [
            take(input, &mut p)?,
            take(input, &mut p)?,
            take(input, &mut p)?,
        ];
        let counts = [
            u32::from_le_bytes(take(input, &mut p)?),
            u32::from_le_bytes(take(input, &mut p)?),
            u32::from_le_bytes(take(input, &mut p)?),
        ];
        let model_version = take(input, &mut p)?;
        let preprocessing = take(input, &mut p)?;
        let initialization = take(input, &mut p)?;
        let local_step_count = u32::from_le_bytes(take(input, &mut p)?);
        let result = Self {
            session,
            round,
            parent_value,
            parent,
            roster,
            counts,
            model_version,
            preprocessing,
            initialization,
            local_step_count,
            data_policy: take(input, &mut p)?,
            optimizer: take(input, &mut p)?,
            relation: take(input, &mut p)?,
            contract: take(input, &mut p)?,
            key_id: take(input, &mut p)?,
        };
        result.validate()?;
        Ok(result)
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Statement {
    pub context: Context,
    pub model_commitment: [u8; 32],
    pub data_commitment: [u8; 32],
    pub output: i64,
}
impl Statement {
    pub fn encode(&self) -> [u8; STATEMENT_BYTES] {
        let mut out = [0; STATEMENT_BYTES];
        let mut p = 0;
        append(&mut out, &mut p, b"FZKSTA02");
        append(&mut out, &mut p, &self.context.encode());
        append(&mut out, &mut p, &self.model_commitment);
        append(&mut out, &mut p, &self.data_commitment);
        append(&mut out, &mut p, &self.output.to_le_bytes());
        out
    }
    pub fn decode(input: &[u8]) -> Result<Self, ContractError> {
        if input.len() != STATEMENT_BYTES || &input[..8] != b"FZKSTA02" {
            return Err(ContractError("statement-canonical-length-or-version"));
        }
        let context = Context::decode(&input[8..400])?;
        let mut p = 400;
        let model_commitment = take(input, &mut p)?;
        let data_commitment = take(input, &mut p)?;
        let output = i64::from_le_bytes(take(input, &mut p)?);
        if !(-80..=80).contains(&output) {
            return Err(ContractError("output-range"));
        }
        Ok(Self {
            context,
            model_commitment,
            data_commitment,
            output,
        })
    }
    pub fn precommit(&self) -> ExpectedTransition {
        ExpectedTransition {
            context: self.context.clone(),
            model_commitment: self.model_commitment,
            data_commitment: self.data_commitment,
        }
    }
}

/// Must come from a trusted precommit/configuration path, never the received proof.
#[derive(Clone, Debug)]
pub struct ExpectedTransition {
    pub context: Context,
    pub model_commitment: [u8; 32],
    pub data_commitment: [u8; 32],
}
impl ExpectedTransition {
    fn matches(&self, statement: &Statement) -> bool {
        self.context == statement.context
            && self.model_commitment == statement.model_commitment
            && self.data_commitment == statement.data_commitment
    }
}

struct AcceptedParent {
    context: Context,
    receipt: [u8; 32],
    output: i64,
}

/// In-memory sequential state gate for the v2 full-state relation. A deployment
/// must persist this atomically and protect it from rollback before using it.
pub struct TransitionChain {
    expected: ExpectedTransition,
    accepted: Option<AcceptedParent>,
    current_consumed: bool,
}
impl TransitionChain {
    /// `first` must be constructed from the authorized genesis state.
    pub fn new(first: ExpectedTransition) -> Result<Self, ContractError> {
        first.context.validate()?;
        Ok(Self {
            expected: first,
            accepted: None,
            current_consumed: false,
        })
    }

    /// Verifies and consumes the currently authorized transition once.
    pub fn accept(
        &mut self,
        session: &PrivateSession,
        proof: &[u8],
    ) -> Result<[u8; 32], ContractError> {
        if self.current_consumed {
            return Err(ContractError("lineage-transition-already-consumed"));
        }
        if !session.verify(&self.expected, proof)? {
            return Err(ContractError("lineage-transition-invalid"));
        }
        let statement = Envelope::decode(proof)?.statement;
        let receipt = hash(&statement.encode());
        self.accepted = Some(AcceptedParent {
            context: statement.context,
            receipt,
            output: statement.output,
        });
        self.current_consumed = true;
        Ok(receipt)
    }

    /// Derives the next expected statement from the last verified full state.
    /// Roster and algorithm identities are pinned for this local chain; counts
    /// may change per round but remain bounded by Context::validate.
    pub fn validate_next_context(&self, context: &Context) -> Result<(), ContractError> {
        let parent = self
            .accepted
            .as_ref()
            .ok_or(ContractError("lineage-parent-not-accepted"))?;
        context.validate()?;
        if !(-32..=32).contains(&parent.output) {
            return Err(ContractError("lineage-parent-outside-next-input-range"));
        }
        if !self.current_consumed
            || context.session != parent.context.session
            || context.round != parent.context.round + 1
            || context.parent != parent.receipt
            || context.parent_value != parent.output
            || context.roster != parent.context.roster
            || context.model_version != parent.context.model_version
            || context.preprocessing != parent.context.preprocessing
            || context.initialization != parent.context.initialization
            || context.local_step_count != parent.context.local_step_count
            || context.data_policy != parent.context.data_policy
            || context.optimizer != parent.context.optimizer
            || context.relation != parent.context.relation
            || context.contract != parent.context.contract
            || context.key_id != parent.context.key_id
        {
            return Err(ContractError("lineage-parent-round-or-configuration"));
        }
        Ok(())
    }

    /// Advances the authorization gate after the caller obtains the next
    /// transition's fresh public commitments and builds its ExpectedTransition.
    pub fn advance(&mut self, next: ExpectedTransition) -> Result<(), ContractError> {
        self.validate_next_context(&next.context)?;
        self.expected = next;
        self.current_consumed = false;
        Ok(())
    }
}

#[derive(Clone)]
struct Opening {
    batch: Batch,
    model_blinding: [u8; 32],
    data_blinding: [u8; 32],
}
fn data_bytes(batch: &Batch) -> [u8; 48] {
    let mut out = [0; 48];
    let mut p = 0;
    for i in 0..3 {
        append(&mut out, &mut p, &batch.x[i].to_le_bytes());
        append(&mut out, &mut p, &batch.y[i].to_le_bytes());
    }
    out
}
fn commit(prefix: &[u8; 8], blinding: &[u8; 32], context: &[u8; 32], message: &[u8]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prefix);
    h.update(blinding);
    h.update(context);
    h.update(message);
    h.finalize().into()
}
impl Opening {
    fn statement(&self, context: Context, output: i64) -> Statement {
        let ctx = hash(&context.encode());
        Statement {
            model_commitment: commit(
                MODEL_DOMAIN,
                &self.model_blinding,
                &ctx,
                &self.batch.w.to_le_bytes(),
            ),
            data_commitment: commit(
                DATA_DOMAIN,
                &self.data_blinding,
                &ctx,
                &data_bytes(&self.batch),
            ),
            context,
            output,
        }
    }
}

fn public_bytes(
    cs: ConstraintSystemRef<Fr>,
    input: &[u8],
) -> Result<Vec<UInt8<Fr>>, SynthesisError> {
    input
        .iter()
        .map(|value| {
            let scalar = FpVar::new_input(cs.clone(), || Ok(Fr::from(u64::from(*value))))?;
            Ok(UInt8::from_bits_le(&bound(
                cs.clone(),
                &scalar,
                i128::from(*value),
                0,
                255,
            )?))
        })
        .collect()
}
fn signed_bytes(
    cs: ConstraintSystemRef<Fr>,
    value: &FpVar<Fr>,
    bytes: &[u8; 8],
    enforce: bool,
) -> Result<Vec<UInt8<Fr>>, SynthesisError> {
    let encoded = UInt8::new_witness_vec(cs, bytes)?;
    let bits = encoded
        .iter()
        .map(ToBitsGadget::to_bits_le)
        .collect::<Result<Vec<_>, _>>()?;
    let mut unsigned = FpVar::Constant(Fr::ZERO);
    for (index, byte) in bits.iter().enumerate() {
        for (bit_index, bit) in byte.iter().enumerate() {
            unsigned += FpVar::from(bit.clone()) * field(1_i128 << (index * 8 + bit_index));
        }
    }
    if enforce {
        (unsigned - FpVar::from(bits[7][7].clone()) * field(1_i128 << 64)).enforce_equal(value)?;
    }
    Ok(encoded)
}

#[derive(Clone)]
struct PrivateCircuit {
    opening: Opening,
    witness: Witness,
    statement: Statement,
    #[cfg(test)]
    fault: Option<TestFault>,
}
impl PrivateCircuit {
    fn new(opening: Opening, witness: Witness, statement: Statement) -> Self {
        Self {
            opening,
            witness,
            statement,
            #[cfg(test)]
            fault: None,
        }
    }
}
impl ConstraintSynthesizer<Fr> for PrivateCircuit {
    fn generate_constraints(self, cs: ConstraintSystemRef<Fr>) -> Result<(), SynthesisError> {
        let version = FpVar::new_input(cs.clone(), || Ok(domain()))?;
        version.enforce_equal(&FpVar::Constant(domain()))?;
        let context = public_bytes(cs.clone(), &hash(&self.statement.context.encode()))?;
        let model_root = public_bytes(cs.clone(), &self.statement.model_commitment)?;
        let data_root = public_bytes(cs.clone(), &self.statement.data_commitment)?;
        let values = arithmetic(
            cs.clone(),
            &self.opening.batch,
            &self.witness,
            AllocationMode::Witness,
        )?;
        let parent_value = FpVar::new_input(cs.clone(), || {
            Ok(field(self.statement.context.parent_value.into()))
        })?;
        bound(
            cs.clone(),
            &parent_value,
            self.statement.context.parent_value.into(),
            -80,
            80,
        )?;
        #[cfg(not(test))]
        values.w.enforce_equal(&parent_value)?;
        #[cfg(test)]
        if !matches!(
            self.fault,
            Some(TestFault::DetachedModel(_)) | Some(TestFault::OmitParentEquality)
        ) {
            values.w.enforce_equal(&parent_value)?;
        }
        let model = self.opening.batch.w.to_le_bytes();
        let data = data_bytes(&self.opening.batch);
        #[cfg(test)]
        let model = if let Some(TestFault::DetachedModel(bytes)) = self.fault {
            bytes
        } else {
            model
        };
        #[cfg(test)]
        let data = if let Some(TestFault::DetachedData(bytes)) = self.fault {
            bytes
        } else {
            data
        };
        #[cfg(not(test))]
        let (model_link, data_link) = (true, true);
        #[cfg(test)]
        let (model_link, data_link) = (
            !matches!(self.fault, Some(TestFault::DetachedModel(_))),
            !matches!(self.fault, Some(TestFault::DetachedData(_))),
        );
        let mut model_message = UInt8::constant_vec(MODEL_DOMAIN);
        model_message.extend(UInt8::new_witness_vec(
            cs.clone(),
            &self.opening.model_blinding,
        )?);
        model_message.extend(context.clone());
        model_message.extend(signed_bytes(cs.clone(), &values.w, &model, model_link)?);
        Sha256Gadget::digest(&model_message)?
            .0
            .enforce_equal(&model_root)?;
        let mut data_message = UInt8::constant_vec(DATA_DOMAIN);
        data_message.extend(UInt8::new_witness_vec(
            cs.clone(),
            &self.opening.data_blinding,
        )?);
        data_message.extend(context);
        for i in 0..3 {
            let x: [u8; 8] = data[i * 16..i * 16 + 8]
                .try_into()
                .map_err(|_| SynthesisError::Unsatisfiable)?;
            let y: [u8; 8] = data[i * 16 + 8..i * 16 + 16]
                .try_into()
                .map_err(|_| SynthesisError::Unsatisfiable)?;
            data_message.extend(signed_bytes(cs.clone(), &values.x[i], &x, data_link)?);
            data_message.extend(signed_bytes(cs.clone(), &values.y[i], &y, data_link)?);
        }
        Sha256Gadget::digest(&data_message)?
            .0
            .enforce_equal(&data_root)?;
        let claimed = FpVar::new_input(cs.clone(), || Ok(field(self.statement.output.into())))?;
        bound(cs, &claimed, self.statement.output.into(), -80, 80)?;
        #[cfg(test)]
        if matches!(self.fault, Some(TestFault::OmitOutputEquality)) {
            return Ok(());
        }
        values.output.enforce_equal(&claimed)
    }
}

fn public_inputs(statement: &Statement) -> Vec<Fr> {
    let mut values = vec![domain()];
    for bytes in [
        hash(&statement.context.encode()),
        statement.model_commitment,
        statement.data_commitment,
    ] {
        values.extend(bytes.iter().map(|b| Fr::from(u64::from(*b))));
    }
    values.extend(
        statement
            .context
            .counts
            .iter()
            .map(|n| Fr::from(u64::from(*n))),
    );
    values.push(field(statement.context.parent_value.into()));
    values.push(field(statement.output.into()));
    values
}

pub struct Envelope {
    pub statement: Statement,
    proof: [u8; 128],
}
impl Envelope {
    pub fn encode(&self) -> [u8; ENVELOPE_BYTES] {
        let mut out = [0; ENVELOPE_BYTES];
        let mut p = 0;
        append(&mut out, &mut p, b"FZKPRF02\x02\x00\x00\x00");
        append(&mut out, &mut p, &backend_id());
        append(&mut out, &mut p, &(STATEMENT_BYTES as u32).to_le_bytes());
        append(&mut out, &mut p, &self.statement.encode());
        append(&mut out, &mut p, &128_u32.to_le_bytes());
        append(&mut out, &mut p, &self.proof);
        out
    }
    pub fn decode(input: &[u8]) -> Result<Self, ContractError> {
        if input.len() != ENVELOPE_BYTES || &input[..12] != b"FZKPRF02\x02\x00\x00\x00" {
            return Err(ContractError("envelope-canonical-length-or-version"));
        }
        let mut p = 12;
        if take::<32>(input, &mut p)? != backend_id()
            || u32::from_le_bytes(take(input, &mut p)?) != STATEMENT_BYTES as u32
        {
            return Err(ContractError("backend-or-statement-length"));
        }
        let statement = Statement::decode(&input[p..p + STATEMENT_BYTES])?;
        p += STATEMENT_BYTES;
        if u32::from_le_bytes(take(input, &mut p)?) != 128 {
            return Err(ContractError("proof-length"));
        }
        let proof = take(input, &mut p)?;
        // Reject noncanonical point encodings and subgroup-invalid points before verification.
        let parsed = Proof::<Bn254>::deserialize_compressed(proof.as_slice())
            .map_err(|_| ContractError("proof-encoding"))?;
        let mut canonical = Vec::with_capacity(128);
        parsed
            .serialize_compressed(&mut canonical)
            .map_err(|_| ContractError("proof-encoding"))?;
        if canonical.as_slice() != proof {
            return Err(ContractError("noncanonical-proof"));
        }
        Ok(Self { statement, proof })
    }
}

/// Opaque, non-Clone and consumed by prove. No API publishes its openings/nonces.
pub struct PreparedTransition {
    circuit: PrivateCircuit,
    pub witness_seconds: f64,
}
impl PreparedTransition {
    pub fn precommit(&self) -> ExpectedTransition {
        self.circuit.statement.precommit()
    }
    pub fn statement(&self) -> Statement {
        self.circuit.statement.clone()
    }
}
pub struct PrivateSession {
    pk: ProvingKey<Bn254>,
    vk: PreparedVerifyingKey<Bn254>,
    key_id: [u8; 32],
    parameters_id: [u8; 32],
    constraints: usize,
}
pub struct PrivateProof {
    pub bytes: [u8; ENVELOPE_BYTES],
    pub witness_seconds: f64,
    pub proving_seconds: f64,
}
impl PrivateSession {
    pub fn key_id(&self) -> [u8; 32] {
        self.key_id
    }
    pub fn parameters_id(&self) -> [u8; 32] {
        self.parameters_id
    }
    pub fn constraints(&self) -> usize {
        self.constraints
    }
    pub fn setup() -> Result<Self, ContractError> {
        let opening = Opening {
            batch: Batch::default(),
            model_blinding: [0; 32],
            data_blinding: [0; 32],
        };
        let statement = opening.statement(Context::synthetic([0; 32], [1; 3], 0), 0);
        let circuit = PrivateCircuit::new(opening, evaluate(&Batch::default())?, statement);
        let cs = ConstraintSystem::new_ref();
        circuit
            .clone()
            .generate_constraints(cs.clone())
            .map_err(|_| ContractError("constraint-setup"))?;
        if !cs
            .is_satisfied()
            .map_err(|_| ContractError("constraint-setup"))?
        {
            return Err(ContractError("constraint-setup"));
        }
        let constraints = cs.num_constraints();
        drop(cs);
        let pk = Groth16::<Bn254>::generate_random_parameters_with_reduction(circuit, &mut OsRng)
            .map_err(|_| ContractError("private-setup"))?;
        let mut vk_bytes = Vec::new();
        pk.vk
            .serialize_compressed(&mut vk_bytes)
            .map_err(|_| ContractError("key-encoding"))?;
        let mut pk_bytes = Vec::new();
        pk.serialize_compressed(&mut pk_bytes)
            .map_err(|_| ContractError("parameter-encoding"))?;
        let vk = prepare_verifying_key(&pk.vk);
        Ok(Self {
            pk,
            vk,
            key_id: hash(&vk_bytes),
            parameters_id: hash(&pk_bytes),
            constraints,
        })
    }
    pub fn prepare(
        &self,
        input: &[u8],
        context: Context,
    ) -> Result<PreparedTransition, ContractError> {
        let start = Instant::now();
        context.validate()?;
        if context.key_id != self.key_id {
            return Err(ContractError("wrong-key-id"));
        }
        let batch = Batch::decode(input)?;
        if context.counts != batch.counts {
            return Err(ContractError("count-substitution"));
        }
        if context.parent_value != batch.w {
            return Err(ContractError("parent-state-mismatch"));
        }
        let witness = evaluate(&batch)?;
        let mut opening = Opening {
            batch,
            model_blinding: [0; 32],
            data_blinding: [0; 32],
        };
        OsRng
            .try_fill_bytes(&mut opening.model_blinding)
            .map_err(|_| ContractError("entropy-unavailable"))?;
        OsRng
            .try_fill_bytes(&mut opening.data_blinding)
            .map_err(|_| ContractError("entropy-unavailable"))?;
        let statement = opening.statement(context, witness.output);
        Ok(PreparedTransition {
            circuit: PrivateCircuit::new(opening, witness, statement),
            witness_seconds: start.elapsed().as_secs_f64(),
        })
    }
    pub fn prove(&self, prepared: PreparedTransition) -> Result<PrivateProof, ContractError> {
        let statement = prepared.circuit.statement.clone();
        if statement.context.key_id != self.key_id {
            return Err(ContractError("wrong-key-id"));
        }
        let start = Instant::now();
        let proof = Groth16::<Bn254>::create_random_proof_with_reduction(
            prepared.circuit,
            &self.pk,
            &mut OsRng,
        )
        .map_err(|_| ContractError("private-proving"))?;
        let proving_seconds = start.elapsed().as_secs_f64();
        let mut encoded = Vec::with_capacity(128);
        proof
            .serialize_compressed(&mut encoded)
            .map_err(|_| ContractError("proof-encoding"))?;
        let proof = encoded
            .try_into()
            .map_err(|_| ContractError("proof-length"))?;
        Ok(PrivateProof {
            bytes: Envelope { statement, proof }.encode(),
            witness_seconds: prepared.witness_seconds,
            proving_seconds,
        })
    }
    pub fn verify(
        &self,
        expected: &ExpectedTransition,
        input: &[u8],
    ) -> Result<bool, ContractError> {
        expected.context.validate()?;
        if expected.context.key_id != self.key_id {
            return Err(ContractError("wrong-key-id"));
        }
        let envelope = Envelope::decode(input)?;
        if !expected.matches(&envelope.statement) {
            return Ok(false);
        }
        let proof = Proof::<Bn254>::deserialize_compressed(envelope.proof.as_slice())
            .map_err(|_| ContractError("proof-encoding"))?;
        Groth16::<Bn254>::verify_proof(&self.vk, &proof, &public_inputs(&envelope.statement))
            .map_err(|_| ContractError("private-verification"))
    }
}

/// Local one-transition state hook, deliberately not a durable consensus ledger.
pub struct ConsumptionState {
    expected: ExpectedTransition,
    receipt: Option<[u8; 32]>,
}
impl ConsumptionState {
    pub fn new(expected: ExpectedTransition) -> Self {
        Self {
            expected,
            receipt: None,
        }
    }
    pub fn accept(
        &mut self,
        session: &PrivateSession,
        proof: &[u8],
    ) -> Result<[u8; 32], ContractError> {
        if self.receipt.is_some() {
            return Err(ContractError("already-consumed"));
        }
        if !session.verify(&self.expected, proof)? {
            return Err(ContractError("invalid-transition"));
        }
        let receipt = hash(&Envelope::decode(proof)?.statement.encode());
        self.receipt = Some(receipt);
        Ok(receipt)
    }
    pub fn receipt(&self) -> Option<[u8; 32]> {
        self.receipt
    }
}

/// Actual private circuit audit against an independently supplied expected output.
pub fn constraint_audit(input: &[u8], expected: i64) -> Result<bool, ContractError> {
    Ok(constraint_audit_details(input, expected)?.0)
}
pub fn constraint_audit_details(
    input: &[u8],
    expected: i64,
) -> Result<(bool, usize, usize), ContractError> {
    let batch = Batch::decode(input)?;
    let witness = evaluate(&batch)?;
    let opening = Opening {
        batch,
        model_blinding: [11; 32],
        data_blinding: [19; 32],
    };
    // Publicly documented deterministic openings are restricted to this no-proof
    // conformance path. Production prepare() always obtains fresh OS entropy.
    let statement = opening.statement(Context::synthetic([0; 32], batch.counts, batch.w), expected);
    let cs = ConstraintSystem::new_ref();
    PrivateCircuit::new(opening, witness, statement)
        .generate_constraints(cs.clone())
        .map_err(|_| ContractError("constraint-audit"))?;
    Ok((
        cs.is_satisfied()
            .map_err(|_| ContractError("constraint-audit"))?,
        cs.num_constraints(),
        cs.num_instance_variables(),
    ))
}

#[cfg(test)]
#[derive(Clone, Copy)]
enum TestFault {
    DetachedModel([u8; 8]),
    DetachedData([u8; 48]),
    OmitOutputEquality,
    OmitParentEquality,
}

#[cfg(test)]
#[path = "private_transition/tests.rs"]
mod tests;
