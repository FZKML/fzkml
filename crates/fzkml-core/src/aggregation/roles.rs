use super::crypto::{
    commit, context_scalar, decode_point, encode_point, scalar_bytes, scalar_decode,
};
use super::{Context, Contribution, Id, Parameters, Result, Witness, encoded, ensure, hash};
use crate::ContractError;
use ark_ec::PrimeGroup;
use ark_ed_on_bn254::{EdwardsProjective as Point, Fr as Scalar};
use ark_ff::{AdditiveGroup, Field, UniformRand};
use ed25519_dalek::{Signature, Signer, SigningKey, VerifyingKey};
use rand::rngs::OsRng;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub(crate) fn sign(key: &SigningKey, body: Id) -> Vec<u8> {
    key.sign(&body).to_bytes().to_vec()
}
pub(crate) fn verify_signature(key: [u8; 32], body: Id, signature: &[u8]) -> Result<()> {
    ensure(signature.len() == 64, "signature-length")?;
    let public = VerifyingKey::from_bytes(&key).map_err(|_| ContractError("credential-key"))?;
    let signature =
        Signature::from_slice(signature).map_err(|_| ContractError("signature-encoding"))?;
    public
        .verify_strict(&body, &signature)
        .map_err(|_| ContractError("authentication-failed"))
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Credential {
    pub serial: Id,
    pub entity: Id,
    pub public_key: [u8; 32],
    pub first_round: u32,
    pub last_round: u32,
    pub signature: Vec<u8>,
}
impl Credential {
    pub fn issue(
        issuer: &SigningKey,
        serial: Id,
        entity: Id,
        public_key: [u8; 32],
        first: u32,
        last: u32,
    ) -> Result<Self> {
        ensure(first <= last && last <= 1000, "credential-validity")?;
        let mut credential = Self {
            serial,
            entity,
            public_key,
            first_round: first,
            last_round: last,
            signature: vec![],
        };
        credential.signature = sign(issuer, credential.body()?);
        Ok(credential)
    }
    fn body(&self) -> Result<Id> {
        hash(
            "issuer-credential-v1",
            &(
                self.serial,
                self.entity,
                self.public_key,
                self.first_round,
                self.last_round,
            ),
        )
    }
    pub fn verify(&self, context: &Context) -> Result<()> {
        ensure(
            self.first_round <= context.round
                && context.round <= self.last_round
                && self.last_round <= 1000,
            "credential-expired",
        )?;
        context.index(self.serial)?;
        verify_signature(context.issuer, self.body()?, &self.signature)
    }
}

/// Per-recipient private payload. Never Serialize/Debug or send to the coordinator.
#[derive(Clone)]
pub struct Packet {
    pub(crate) context: Id,
    pub(crate) serial: Id,
    pub(crate) body: Id,
    pub(crate) recipient: u8,
    pub(crate) share: Scalar,
    pub(crate) blind: Scalar,
}
pub struct Client {
    key: SigningKey,
    pub credential: Credential,
}
impl Client {
    pub fn new(key: SigningKey, credential: Credential) -> Result<Self> {
        ensure(
            key.verifying_key().to_bytes() == credential.public_key,
            "credential-secret-key",
        )?;
        Ok(Self { key, credential })
    }
    /// Consumes the private witness so its commitment blindings cannot be reused.
    /// Retry delivery with the original contribution/packets, not a new proof.
    ///
    /// ```compile_fail,E0382
    /// use fzkml_core::aggregation::{Client, Context, Parameters, Witness};
    /// fn reuse(client: &Client, context: &Context, parameters: &Parameters) {
    ///     let witness = Witness::new(16, 16);
    ///     let _ = client.contribute(context, parameters, witness);
    ///     let _ = client.contribute(context, parameters, witness);
    /// }
    /// ```
    pub fn contribute(
        &self,
        context: &Context,
        parameters: &Parameters,
        witness: Witness,
    ) -> Result<(Contribution, [Packet; 3])> {
        self.credential.verify(context)?;
        let index = context.index(self.credential.serial)?;
        let proved = parameters.prove(context, &witness)?;
        let a = Scalar::rand(&mut OsRng);
        let b = Scalar::rand(&mut OsRng);
        let mut contribution = Contribution {
            context: context.id()?,
            credential: self.credential.clone(),
            weight: context.weights[index],
            output: proved.output,
            coefficient: encode_point(commit(a, b))?,
            data: proved.data,
            child_state: [0; 32],
            proof: proved.proof,
            signature: vec![],
        };
        contribution.child_state = contribution.child(context)?;
        let body = contribution.body()?;
        contribution.signature = sign(&self.key, body);
        let packets = std::array::from_fn(|i| {
            let x = Scalar::from((i + 1) as u64);
            Packet {
                context: contribution.context,
                serial: self.credential.serial,
                body,
                recipient: (i + 1) as u8,
                share: proved.value + a * x,
                blind: witness.blind + b * x,
            }
        });
        Ok((contribution, packets))
    }
}

pub(crate) fn validate_contribution(
    context: &Context,
    parameters: &Parameters,
    c: &Contribution,
) -> Result<()> {
    context.validate()?;
    c.credential.verify(context)?;
    ensure(
        c.context == context.id()?
            && c.weight == context.weights[context.index(c.credential.serial)?]
            && c.child_state == c.child(context)?,
        "contribution-lineage-weight",
    )?;
    ensure(
        c.output.len() == 32
            && c.data.len() == 32
            && c.coefficient.len() == 32
            && c.proof.len() == 128,
        "contribution-size",
    )?;
    let _ = decode_point(&c.coefficient)?;
    verify_signature(c.credential.public_key, c.body()?, &c.signature)?;
    ensure(
        parameters.verify(context, c)?,
        "invalid-private-transition-proof",
    )
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Availability {
    pub context: Id,
    pub contribution: Id,
    pub recipient: u8,
    pub signature: Vec<u8>,
}
impl Availability {
    fn body(&self) -> Result<Id> {
        hash(
            "recipient-availability-v1",
            &(self.context, self.contribution, self.recipient),
        )
    }
    pub(crate) fn verify(&self, context: &Context, contribution: &Contribution) -> Result<()> {
        ensure(
            (1..=3).contains(&self.recipient)
                && self.context == context.id()?
                && self.contribution == contribution.body()?,
            "availability-scope",
        )?;
        verify_signature(
            context.recipients[self.recipient as usize - 1],
            self.body()?,
            &self.signature,
        )
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Permit {
    pub context: Id,
    pub accepted_root: Id,
    pub release_id: Id,
    pub signature: Vec<u8>,
}
impl Permit {
    pub(crate) fn issue(key: &SigningKey, context: Id, root: Id) -> Result<Self> {
        let mut permit = Self {
            context,
            accepted_root: root,
            release_id: hash("one-release-v1", &(context, root))?,
            signature: vec![],
        };
        permit.signature = sign(key, permit.body()?);
        Ok(permit)
    }
    fn body(&self) -> Result<Id> {
        hash(
            "release-permit-v1",
            &(self.context, self.accepted_root, self.release_id),
        )
    }
    pub(crate) fn verify(&self, context: &Context) -> Result<()> {
        ensure(
            self.context == context.id()?
                && self.release_id == hash("one-release-v1", &(self.context, self.accepted_root))?,
            "release-permit-scope",
        )?;
        verify_signature(context.authority, self.body()?, &self.signature)
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AggregateShare {
    pub context: Id,
    pub accepted_root: Id,
    pub release_id: Id,
    pub recipient: u8,
    pub share: Vec<u8>,
    pub blind: Vec<u8>,
    pub signature: Vec<u8>,
}
impl AggregateShare {
    fn body(&self) -> Result<Id> {
        hash(
            "aggregate-share-v1",
            &(
                self.context,
                self.accepted_root,
                self.release_id,
                self.recipient,
                &self.share,
                &self.blind,
            ),
        )
    }
    pub(crate) fn verify(
        &self,
        context: &Context,
        permit: &Permit,
        accepted: &[Contribution],
    ) -> Result<()> {
        permit.verify(context)?;
        ensure(
            (1..=3).contains(&self.recipient)
                && self.context == permit.context
                && self.accepted_root == permit.accepted_root
                && self.release_id == permit.release_id,
            "aggregate-share-scope",
        )?;
        let x = Scalar::from(self.recipient as u64);
        let mut expected = Point::ZERO;
        for c in accepted {
            expected += (decode_point(&c.output)? - Point::generator() * context_scalar(context)?
                + decode_point(&c.coefficient)? * x)
                * Scalar::from(c.weight as u64);
        }
        ensure(
            commit(scalar_decode(&self.share)?, scalar_decode(&self.blind)?) == expected,
            "aggregate-conservation",
        )?;
        verify_signature(
            context.recipients[self.recipient as usize - 1],
            self.body()?,
            &self.signature,
        )
    }
}

pub struct Recipient {
    index: u8,
    key: SigningKey,
    stored: BTreeMap<(Id, Id), (Contribution, Packet)>,
}
impl Recipient {
    pub fn new(index: u8, key: SigningKey) -> Result<Self> {
        ensure((1..=3).contains(&index), "recipient-index")?;
        Ok(Self {
            index,
            key,
            stored: BTreeMap::new(),
        })
    }
    pub fn public_key(&self) -> [u8; 32] {
        self.key.verifying_key().to_bytes()
    }
    pub fn receive(
        &mut self,
        context: &Context,
        parameters: &Parameters,
        c: &Contribution,
        packet: Packet,
    ) -> Result<Availability> {
        validate_contribution(context, parameters, c)?;
        ensure(
            self.public_key() == context.recipients[self.index as usize - 1]
                && packet.recipient == self.index
                && packet.context == context.id()?
                && packet.serial == c.credential.serial
                && packet.body == c.body()?,
            "private-payload-routing",
        )?;
        let expected = decode_point(&c.output)? - Point::generator() * context_scalar(context)?
            + decode_point(&c.coefficient)? * Scalar::from(self.index as u64);
        ensure(
            commit(packet.share, packet.blind) == expected,
            "proved-payload-substitution",
        )?;
        let key = (packet.context, packet.serial);
        if let Some((previous, _)) = self.stored.get(&key) {
            ensure(previous.body()? == c.body()?, "recipient-equivocation")?;
        } else {
            self.stored.insert(key, (c.clone(), packet));
        }
        let mut ack = Availability {
            context: context.id()?,
            contribution: c.body()?,
            recipient: self.index,
            signature: vec![],
        };
        ack.signature = sign(&self.key, ack.body()?);
        Ok(ack)
    }
    /// Called only after the authority durably reserves possible disclosure.
    pub fn aggregate(
        &self,
        context: &Context,
        permit: &Permit,
        accepted: &[Contribution],
    ) -> Result<AggregateShare> {
        permit.verify(context)?;
        ensure(
            accepted_root(context, accepted)? == permit.accepted_root,
            "recipient-accepted-set",
        )?;
        let mut share = Scalar::ZERO;
        let mut blind = Scalar::ZERO;
        for c in accepted {
            let (stored, packet) = self
                .stored
                .get(&(context.id()?, c.credential.serial))
                .ok_or(ContractError("committed-payload-unavailable"))?;
            ensure(stored.body()? == c.body()?, "recipient-payload-version")?;
            share += packet.share * Scalar::from(c.weight as u64);
            blind += packet.blind * Scalar::from(c.weight as u64);
        }
        let mut result = AggregateShare {
            context: context.id()?,
            accepted_root: permit.accepted_root,
            release_id: permit.release_id,
            recipient: self.index,
            share: scalar_bytes(share)?,
            blind: scalar_bytes(blind)?,
            signature: vec![],
        };
        result.signature = sign(&self.key, result.body()?);
        Ok(result)
    }
}

pub(crate) fn accepted_root(context: &Context, accepted: &[Contribution]) -> Result<Id> {
    ensure(accepted.len() == 3, "accepted-set-incomplete")?;
    for (i, c) in accepted.iter().enumerate() {
        ensure(
            c.context == context.id()?
                && c.credential.serial == context.clients[i]
                && c.weight == context.weights[i],
            "accepted-set-order-weight-or-duplicate",
        )?;
    }
    hash("accepted-set-v1", &(context.id()?, encoded(&accepted)?))
}

pub(crate) fn reconstruct(shares: &[AggregateShare]) -> Result<Scalar> {
    ensure((2..=3).contains(&shares.len()), "threshold-unavailable")?;
    let mut total = Scalar::ZERO;
    for (i, share) in shares.iter().enumerate() {
        ensure(
            !shares[..i].iter().any(|s| s.recipient == share.recipient),
            "duplicate-recipient",
        )?;
        let xi = Scalar::from(share.recipient as u64);
        let mut weight = Scalar::ONE;
        for (j, other) in shares.iter().enumerate() {
            if i != j {
                let xj = Scalar::from(other.recipient as u64);
                weight *= -xj
                    * (xi - xj)
                        .inverse()
                        .ok_or(ContractError("duplicate-recipient"))?;
            }
        }
        total += scalar_decode(&share.share)? * weight;
    }
    Ok(total)
}
