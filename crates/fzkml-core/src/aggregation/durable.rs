use super::roles::{accepted_root, reconstruct, validate_contribution};
use super::{
    AggregateShare, Availability, Context, Contribution, Id, Parameters, Permit, Result, State,
    encoded, ensure, hash,
};
use crate::{ContractError, round_even};
use ark_ff::{BigInteger, PrimeField};
use ed25519_dalek::SigningKey;
use rusqlite::{Connection, OptionalExtension, TransactionBehavior, params};
use serde::{Deserialize, Serialize, de::DeserializeOwned};
use std::{fs::OpenOptions, path::Path, time::Duration};

fn database<T>(result: rusqlite::Result<T>) -> Result<T> {
    result.map_err(|_| ContractError("durable-ledger-operation"))
}
fn parse<T: DeserializeOwned>(data: &[u8]) -> Result<T> {
    ensure(data.len() <= 65_536, "ledger-record-size")?;
    serde_json::from_slice(data).map_err(|_| ContractError("ledger-record-encoding"))
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Released {
    pub release_id: Id,
    pub context: Id,
    pub accepted_root: Id,
    pub weighted_sum: i64,
    pub denominator: u32,
    pub model: i64,
    pub parent: Id,
    pub child: State,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Observation {
    pub observer: String,
    pub kind: String,
    pub release_id: Id,
    pub details: String,
}

/// Single trusted, non-rollbackable SQLite authority. Not distributed consensus.
pub struct Ledger {
    connection: Connection,
    authority: SigningKey,
    issuer: [u8; 32],
}
impl Ledger {
    pub fn open(
        path: &Path,
        authority: SigningKey,
        issuer: [u8; 32],
        genesis: &State,
    ) -> Result<Self> {
        genesis.validate()?;
        if !path.exists() {
            let mut options = OpenOptions::new();
            options.create_new(true).write(true);
            #[cfg(unix)]
            {
                use std::os::unix::fs::OpenOptionsExt;
                options.mode(0o600);
            }
            options
                .open(path)
                .map_err(|_| ContractError("private-ledger-create"))?;
        }
        let info = std::fs::symlink_metadata(path)
            .map_err(|_| ContractError("private-ledger-metadata"))?;
        ensure(
            info.is_file() && !info.file_type().is_symlink(),
            "private-ledger-path",
        )?;
        #[cfg(unix)]
        {
            use std::os::unix::fs::MetadataExt;
            ensure(
                info.mode() & 0o077 == 0 && info.nlink() == 1,
                "private-ledger-permissions",
            )?;
        }
        let connection = database(Connection::open(path))?;
        database(connection.busy_timeout(Duration::from_secs(10)))?;
        database(connection.execute_batch("PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS meta (name TEXT PRIMARY KEY, value BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS rounds (id BLOB PRIMARY KEY, context BLOB NOT NULL, phase TEXT NOT NULL, root BLOB, permit BLOB, result BLOB);
            CREATE TABLE IF NOT EXISTS accepted (round BLOB NOT NULL, serial BLOB NOT NULL, entity BLOB NOT NULL, nullifier BLOB NOT NULL, contribution BLOB NOT NULL, availability BLOB NOT NULL, PRIMARY KEY(round,serial), UNIQUE(round,entity), UNIQUE(round,nullifier));
            CREATE TABLE IF NOT EXISTS revoked (serial BLOB PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS observations (round BLOB PRIMARY KEY, value BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS attempts (round BLOB NOT NULL, attempt BLOB NOT NULL, outcome TEXT NOT NULL, PRIMARY KEY(round,attempt,outcome));"))?;
        database(connection.execute_batch("CREATE TABLE IF NOT EXISTS session_slots (session BLOB NOT NULL, sequence INTEGER NOT NULL, round BLOB NOT NULL, PRIMARY KEY(session,sequence));
            CREATE TABLE IF NOT EXISTS disclosure_slots (parent BLOB PRIMARY KEY, round BLOB NOT NULL UNIQUE);"))?;
        let mut ledger = Self {
            connection,
            authority,
            issuer,
        };
        let tx = database(
            ledger
                .connection
                .transaction_with_behavior(TransactionBehavior::Immediate),
        )?;
        let binding = hash(
            "ledger-authority-v1",
            &(
                ledger.authority.verifying_key().to_bytes(),
                issuer,
                genesis.id()?,
            ),
        )?;
        let existing: Option<Vec<u8>> = database(
            tx.query_row("SELECT value FROM meta WHERE name='binding'", [], |r| {
                r.get(0)
            })
            .optional(),
        )?;
        if let Some(old) = existing {
            ensure(old == binding, "wrong-ledger-authority-or-genesis")?;
        } else {
            database(tx.execute(
                "INSERT INTO meta VALUES ('binding',?1)",
                [binding.as_slice()],
            ))?;
            database(tx.execute("INSERT INTO meta VALUES ('head',?1)", [encoded(genesis)?]))?;
        }
        database(tx.commit())?;
        Ok(ledger)
    }
    pub fn head(&self) -> Result<State> {
        let data: Vec<u8> = database(self.connection.query_row(
            "SELECT value FROM meta WHERE name='head'",
            [],
            |r| r.get(0),
        ))?;
        parse(&data)
    }
    pub fn begin(&mut self, context: &Context) -> Result<()> {
        context.validate()?;
        ensure(
            context.authority == self.authority.verifying_key().to_bytes()
                && context.issuer == self.issuer,
            "untrusted-round-authority",
        )?;
        let id = context.id()?;
        let tx = database(
            self.connection
                .transaction_with_behavior(TransactionBehavior::Immediate),
        )?;
        let head: Vec<u8> =
            database(tx.query_row("SELECT value FROM meta WHERE name='head'", [], |r| r.get(0)))?;
        ensure(
            parse::<State>(&head)?.id()? == context.parent.id()?,
            "stale-parent",
        )?;
        let slot: Option<Vec<u8>> = database(
            tx.query_row(
                "SELECT round FROM session_slots WHERE session=?1 AND sequence=?2",
                params![context.session.as_slice(), context.round],
                |r| r.get(0),
            )
            .optional(),
        )?;
        if let Some(slot) = slot {
            ensure(slot == id, "session-round-equivocation")?;
        } else {
            database(tx.execute(
                "INSERT INTO session_slots VALUES (?1,?2,?3)",
                params![context.session.as_slice(), context.round, id.as_slice()],
            ))?;
        }
        let existing: Option<Vec<u8>> = database(
            tx.query_row(
                "SELECT context FROM rounds WHERE id=?1",
                [id.as_slice()],
                |r| r.get(0),
            )
            .optional(),
        )?;
        if let Some(existing) = existing {
            ensure(existing == encoded(context)?, "round-equivocation")?;
        } else {
            database(tx.execute(
                "INSERT INTO rounds(id,context,phase) VALUES (?1,?2,'open')",
                params![id.as_slice(), encoded(context)?],
            ))?;
        }
        database(tx.commit())
    }
    pub fn revoke(&mut self, serial: Id) -> Result<()> {
        database(self.connection.execute(
            "INSERT OR IGNORE INTO revoked VALUES (?1)",
            [serial.as_slice()],
        ))?;
        Ok(())
    }
    pub fn admit(
        &mut self,
        context: &Context,
        parameters: &Parameters,
        c: &Contribution,
        acks: &[Availability],
    ) -> Result<()> {
        validate_contribution(context, parameters, c)?;
        ensure(acks.len() == 3, "payload-availability-incomplete")?;
        for (i, ack) in acks.iter().enumerate() {
            ensure(
                ack.recipient as usize == i + 1,
                "availability-duplicate-order",
            )?;
            ack.verify(context, c)?;
        }
        let id = context.id()?;
        let tx = database(
            self.connection
                .transaction_with_behavior(TransactionBehavior::Immediate),
        )?;
        let (phase,parent):(String,Vec<u8>)=database(tx.query_row("SELECT rounds.phase,meta.value FROM rounds CROSS JOIN meta WHERE rounds.id=?1 AND meta.name='head'",[id.as_slice()],|r|Ok((r.get(0)?,r.get(1)?))))?;
        ensure(
            phase == "open" && parse::<State>(&parent)?.id()? == context.parent.id()?,
            "closed-or-stale-admission",
        )?;
        let revoked: bool = database(tx.query_row(
            "SELECT EXISTS(SELECT 1 FROM revoked WHERE serial=?1)",
            [c.credential.serial.as_slice()],
            |r| r.get(0),
        ))?;
        ensure(!revoked, "revoked-credential")?;
        database(tx.execute(
            "INSERT INTO accepted VALUES (?1,?2,?3,?4,?5,?6)",
            params![
                id.as_slice(),
                c.credential.serial.as_slice(),
                c.credential.entity.as_slice(),
                c.nullifier(context)?.as_slice(),
                encoded(c)?,
                encoded(&acks)?
            ],
        ))?;
        database(tx.commit())
    }
    fn accepted(&self, id: Id) -> Result<Vec<Contribution>> {
        let mut query = database(
            self.connection
                .prepare("SELECT contribution FROM accepted WHERE round=?1 ORDER BY serial"),
        )?;
        let rows = database(query.query_map([id.as_slice()], |r| r.get::<_, Vec<u8>>(0)))?;
        rows.map(|row| parse(&database(row)?)).collect()
    }
    pub fn freeze(&mut self, context: &Context) -> Result<(Id, Vec<Contribution>)> {
        let id = context.id()?;
        let accepted = self.accepted(id)?;
        let root = accepted_root(context, &accepted)?;
        let tx = database(
            self.connection
                .transaction_with_behavior(TransactionBehavior::Immediate),
        )?;
        let head: Vec<u8> =
            database(tx.query_row("SELECT value FROM meta WHERE name='head'", [], |r| r.get(0)))?;
        ensure(
            parse::<State>(&head)?.id()? == context.parent.id()?,
            "stale-frozen-parent",
        )?;
        let revoked: i64 = database(tx.query_row(
            "SELECT count(*) FROM accepted JOIN revoked USING(serial) WHERE round=?1",
            [id.as_slice()],
            |r| r.get(0),
        ))?;
        ensure(revoked == 0, "revocation-before-freeze")?;
        ensure(
            database(tx.execute(
                "UPDATE rounds SET phase='frozen',root=?1 WHERE id=?2 AND phase='open'",
                params![root.as_slice(), id.as_slice()],
            ))? == 1,
            "round-already-frozen",
        )?;
        database(tx.commit())?;
        Ok((root, accepted))
    }
    /// Commit possible-disclosure evidence BEFORE any recipient reveals an aggregate share.
    pub fn reserve(&mut self, context: &Context, root: Id, attempt: Id) -> Result<Permit> {
        let id = context.id()?;
        let tx = database(
            self.connection
                .transaction_with_behavior(TransactionBehavior::Immediate),
        )?;
        let (phase, stored, old): (String, Vec<u8>, Option<Vec<u8>>) = database(tx.query_row(
            "SELECT phase,root,permit FROM rounds WHERE id=?1",
            [id.as_slice()],
            |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
        ))?;
        ensure(
            stored == root && (phase == "frozen" || phase == "observing" || phase == "released"),
            "reserve-round-state",
        )?;
        if phase == "frozen" {
            let head: Vec<u8> =
                database(
                    tx.query_row("SELECT value FROM meta WHERE name='head'", [], |r| r.get(0)),
                )?;
            ensure(
                parse::<State>(&head)?.id()? == context.parent.id()?,
                "stale-disclosure-parent",
            )?;
            let revoked: i64 = database(tx.query_row(
                "SELECT count(*) FROM accepted JOIN revoked USING(serial) WHERE round=?1",
                [id.as_slice()],
                |r| r.get(0),
            ))?;
            ensure(revoked == 0, "revocation-before-disclosure")?;
        }
        let parent = context.parent.id()?;
        let selected: Option<Vec<u8>> = database(
            tx.query_row(
                "SELECT round FROM disclosure_slots WHERE parent=?1",
                [parent.as_slice()],
                |r| r.get(0),
            )
            .optional(),
        )?;
        if let Some(selected) = selected {
            ensure(selected == id, "parent-already-authorized-other-disclosure")?;
        } else {
            database(tx.execute(
                "INSERT INTO disclosure_slots VALUES (?1,?2)",
                params![parent.as_slice(), id.as_slice()],
            ))?;
        }
        let permit = if let Some(old) = old {
            parse(&old)?
        } else {
            Permit::issue(&self.authority, id, root)?
        };
        let observation=Observation{observer:"coordinator".into(),kind:"possibly-exposed-clean-sum".into(),release_id:permit.release_id,details:"Reserved before aggregate-share delivery; retain across abort/crash; no DP epsilon bound asserted.".into()};
        database(tx.execute(
            "INSERT OR IGNORE INTO observations VALUES (?1,?2)",
            params![id.as_slice(), encoded(&observation)?],
        ))?;
        database(tx.execute(
            "INSERT OR IGNORE INTO attempts VALUES (?1,?2,'reserved')",
            params![id.as_slice(), attempt.as_slice()],
        ))?;
        if phase != "released" {
            database(tx.execute(
                "UPDATE rounds SET phase='observing',permit=?1 WHERE id=?2",
                params![encoded(&permit)?, id.as_slice()],
            ))?;
        }
        database(tx.commit())?;
        Ok(permit)
    }
    pub fn observe_sum(
        &mut self,
        context: &Context,
        permit: &Permit,
        shares: &[AggregateShare],
        _attempt: Id,
    ) -> Result<(i64, u32, i64)> {
        permit.verify(context)?;
        let (phase, stored): (String, Option<Vec<u8>>) = database(self.connection.query_row(
            "SELECT phase,permit FROM rounds WHERE id=?1",
            [context.id()?.as_slice()],
            |r| Ok((r.get(0)?, r.get(1)?)),
        ))?;
        ensure(
            (phase == "observing" || phase == "released") && stored == Some(encoded(permit)?),
            "unreserved-or-aborted-observation",
        )?;
        ensure(
            shares.len() >= 3 - context.max_unavailable_recipients as usize && shares.len() <= 3,
            "unsupported-dropout-threshold",
        )?;
        let accepted = self.accepted(context.id()?)?;
        ensure(
            accepted_root(context, &accepted)? == permit.accepted_root,
            "released-accepted-set",
        )?;
        for share in shares {
            share.verify(context, permit, &accepted)?;
        }
        let scalar = reconstruct(shares)?;
        let bytes = scalar.into_bigint().to_bytes_le();
        ensure(
            bytes[8..].iter().all(|b| *b == 0),
            "aggregate-range-overflow",
        )?;
        let encoded_sum = u64::from_le_bytes(
            bytes[..8]
                .try_into()
                .map_err(|_| ContractError("aggregate-integer"))?,
        );
        let denominator: u32 = context.weights.iter().sum();
        ensure(
            encoded_sum <= 160 * u64::from(denominator),
            "aggregate-range-overflow",
        )?;
        let sum = i64::try_from(encoded_sum).map_err(|_| ContractError("aggregate-integer"))?
            - 80 * i64::from(denominator);
        let model = i64::try_from(round_even(sum.into(), denominator.into())?)
            .map_err(|_| ContractError("aggregate-rounding"))?;
        let observation=Observation{observer:"coordinator".into(),kind:"exposed-clean-sum".into(),release_id:permit.release_id,details:"Verified threshold aggregate received; retain even if the user-facing round aborts; no DP epsilon bound asserted.".into()};
        database(self.connection.execute(
            "UPDATE observations SET value=?1 WHERE round=?2",
            params![encoded(&observation)?, context.id()?.as_slice()],
        ))?;
        Ok((sum, denominator, model))
    }
    pub fn finish(
        &mut self,
        context: &Context,
        permit: &Permit,
        shares: &[AggregateShare],
        attempt: Id,
    ) -> Result<Released> {
        let (sum, denominator, model) = self.observe_sum(context, permit, shares, attempt)?;
        let mut child = context.parent.clone();
        child.model = model;
        child.sequence += 1;
        child.validate()?;
        let result = Released {
            release_id: permit.release_id,
            context: context.id()?,
            accepted_root: permit.accepted_root,
            weighted_sum: sum,
            denominator,
            model,
            parent: context.parent.id()?,
            child,
        };
        let tx = database(
            self.connection
                .transaction_with_behavior(TransactionBehavior::Immediate),
        )?;
        let (phase, old, stored): (String, Option<Vec<u8>>, Vec<u8>) = database(tx.query_row(
            "SELECT phase,result,permit FROM rounds WHERE id=?1",
            [result.context.as_slice()],
            |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
        ))?;
        ensure(stored == encoded(permit)?, "unreserved-reconstruction")?;
        if let Some(old) = old {
            ensure(old == encoded(&result)?, "release-decision-substitution")?;
            database(tx.execute(
                "INSERT OR IGNORE INTO attempts VALUES (?1,?2,'redelivered')",
                params![result.context.as_slice(), attempt.as_slice()],
            ))?;
            database(tx.commit())?;
            return parse(&old);
        }
        ensure(phase == "observing", "immutable-abort-decision")?;
        let head: Vec<u8> =
            database(tx.query_row("SELECT value FROM meta WHERE name='head'", [], |r| r.get(0)))?;
        ensure(
            parse::<State>(&head)?.id()? == context.parent.id()?,
            "stale-release-parent",
        )?;
        let observation=Observation{observer:"coordinator".into(),kind:"exposed-clean-sum".into(),release_id:permit.release_id,details:"Clean aggregate visible, even if delivery or later user-facing operation fails; DP accounting unresolved.".into()};
        database(tx.execute(
            "UPDATE observations SET value=?1 WHERE round=?2",
            params![encoded(&observation)?, result.context.as_slice()],
        ))?;
        database(tx.execute(
            "UPDATE rounds SET phase='released',result=?1 WHERE id=?2",
            params![encoded(&result)?, result.context.as_slice()],
        ))?;
        database(tx.execute(
            "UPDATE meta SET value=?1 WHERE name='head'",
            [encoded(&result.child)?],
        ))?;
        database(tx.execute(
            "INSERT OR IGNORE INTO attempts VALUES (?1,?2,'released')",
            params![result.context.as_slice(), attempt.as_slice()],
        ))?;
        database(tx.commit())?;
        Ok(result)
    }
    pub fn abort(&mut self, context: &Context, attempt: Id) -> Result<()> {
        let id = context.id()?;
        let tx = database(
            self.connection
                .transaction_with_behavior(TransactionBehavior::Immediate),
        )?;
        let phase: String = database(tx.query_row(
            "SELECT phase FROM rounds WHERE id=?1",
            [id.as_slice()],
            |r| r.get(0),
        ))?;
        ensure(phase != "released", "immutable-release-decision")?;
        database(tx.execute(
            "UPDATE rounds SET phase='aborted' WHERE id=?1",
            [id.as_slice()],
        ))?;
        database(tx.execute(
            "INSERT OR IGNORE INTO attempts VALUES (?1,?2,'aborted')",
            params![id.as_slice(), attempt.as_slice()],
        ))?;
        database(tx.commit())
    }
    pub fn observation(&self, context: &Context) -> Result<Option<Observation>> {
        let row: Option<Vec<u8>> = database(
            self.connection
                .query_row(
                    "SELECT value FROM observations WHERE round=?1",
                    [context.id()?.as_slice()],
                    |r| r.get(0),
                )
                .optional(),
        )?;
        row.map(|b| parse(&b)).transpose()
    }
    pub fn release_count(&self) -> Result<u32> {
        database(self.connection.query_row(
            "SELECT count(*) FROM rounds WHERE phase='released'",
            [],
            |r| r.get(0),
        ))
    }
    pub fn recovered(&self, context: &Context) -> Result<Option<Released>> {
        let row: Option<Vec<u8>> = database(
            self.connection
                .query_row(
                    "SELECT result FROM rounds WHERE id=?1",
                    [context.id()?.as_slice()],
                    |r| r.get(0),
                )
                .optional(),
        )?
        .flatten();
        row.map(|b| parse(&b)).transpose()
    }
}
