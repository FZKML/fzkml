//! Research-only Pedersen VSS + private local-transition proof + durable authority.
//! Fixed three clients, three recipients, threshold two. No deployment audit or DP.
mod crypto;
mod demo;
mod durable;
pub use demo::{DemoReport, demo};
mod roles;
#[cfg(test)]
mod tests;
pub use crypto::{Parameters, Witness, local_update};
pub use durable::{Ledger, Observation, Released};
pub use roles::{AggregateShare, Availability, Client, Credential, Permit, Recipient};

use crate::ContractError;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

pub type Id = [u8; 32];
pub(crate) type Result<T> = std::result::Result<T, ContractError>;
pub(crate) fn ensure(ok: bool, code: &'static str) -> Result<()> {
    if ok { Ok(()) } else { Err(ContractError(code)) }
}
pub(crate) fn encoded<T: Serialize>(value: &T) -> Result<Vec<u8>> {
    serde_json::to_vec(value).map_err(|_| ContractError("canonical-json"))
}
pub fn hash<T: Serialize>(domain: &str, value: &T) -> Result<Id> {
    let mut h = Sha256::new();
    h.update(domain.as_bytes());
    h.update([0]);
    h.update(encoded(value)?);
    Ok(h.finalize().into())
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct State {
    pub version: u32,
    pub sequence: u32,
    pub model: i64,
    pub optimizer: String,
    pub momentum: Option<Vec<i64>>,
    pub error_feedback: Option<Vec<i64>>,
    pub preprocessing: Id,
    pub initialization: Id,
    pub local_steps: u32,
    pub policy: Id,
    pub value_kind: String,
}
impl State {
    pub fn new(model: i64) -> Self {
        Self {
            version: 1,
            sequence: 0,
            model,
            optimizer: "sgd-rne-v1".into(),
            momentum: None,
            error_feedback: None,
            preprocessing: [1; 32],
            initialization: [2; 32],
            local_steps: 1,
            policy: [3; 32],
            value_kind: "full-state".into(),
        }
    }
    pub fn validate(&self) -> Result<()> {
        ensure(
            self.version == 1
                && self.sequence <= 1000
                && (-80..=80).contains(&self.model)
                && self.optimizer == "sgd-rne-v1"
                && self.momentum.is_none()
                && self.error_feedback.is_none()
                && self.local_steps == 1
                && self.value_kind == "full-state",
            "unsupported-complete-state",
        )
    }
    pub fn id(&self) -> Result<Id> {
        self.validate()?;
        hash("complete-state-v1", self)
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Context {
    pub version: u32,
    pub session: Id,
    pub round: u32,
    pub parent: State,
    pub clients: [Id; 3],
    pub weights: [u32; 3],
    pub recipients: [[u8; 32]; 3],
    pub issuer: [u8; 32],
    pub authority: [u8; 32],
    pub proof_key: Id,
    pub dimensions: u32,
    pub encoding: String,
    pub max_corrupt_recipients: u32,
    pub max_unavailable_recipients: u32,
    pub max_contributions_per_entity: u32,
}
impl Context {
    pub fn validate(&self) -> Result<()> {
        self.parent.validate()?;
        ensure(
            self.version == 1
                && self.round < 1000
                && self.round == self.parent.sequence
                && (-32..=32).contains(&self.parent.model)
                && self.dimensions == 1
                && self.encoding == "dense-rne-offset80-v1"
                && self.max_corrupt_recipients <= 1
                && self.max_unavailable_recipients <= 1
                && self.max_contributions_per_entity == 1
                && self.weights.iter().all(|w| (1..=4).contains(w)),
            "unsupported-aggregation-model",
        )?;
        ensure(
            self.clients[0] < self.clients[1] && self.clients[1] < self.clients[2],
            "canonical-roster",
        )?;
        ensure(
            self.recipients[0] != self.recipients[1]
                && self.recipients[0] != self.recipients[2]
                && self.recipients[1] != self.recipients[2],
            "recipient-identity-duplicates",
        )
    }
    pub fn id(&self) -> Result<Id> {
        self.validate()?;
        hash("aggregation-context-v1", self)
    }
    pub fn index(&self, serial: Id) -> Result<usize> {
        self.clients
            .iter()
            .position(|x| *x == serial)
            .ok_or(ContractError("uninvited-credential"))
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Contribution {
    pub context: Id,
    pub credential: Credential,
    pub weight: u32,
    pub output: Vec<u8>,
    pub coefficient: Vec<u8>,
    pub data: Vec<u8>,
    pub child_state: Id,
    pub proof: Vec<u8>,
    pub signature: Vec<u8>,
}
impl Contribution {
    pub fn nullifier(&self, context: &Context) -> Result<Id> {
        hash(
            "admission-nullifier-v1",
            &(
                context.session,
                context.round,
                context.issuer,
                self.credential.serial,
            ),
        )
    }
    pub fn body(&self) -> Result<Id> {
        hash(
            "signed-contribution-v1",
            &(
                self.context,
                &self.credential,
                self.weight,
                &self.output,
                &self.coefficient,
                &self.data,
                self.child_state,
                &self.proof,
            ),
        )
    }
    pub fn child(&self, context: &Context) -> Result<Id> {
        hash(
            "complete-client-child-v1",
            &(
                context.parent.id()?,
                self.context,
                &self.output,
                context.parent.local_steps,
                &context.parent.optimizer,
                &context.parent.momentum,
                &context.parent.error_feedback,
                context.parent.preprocessing,
                context.parent.initialization,
                context.parent.policy,
                "full-state",
            ),
        )
    }
}
