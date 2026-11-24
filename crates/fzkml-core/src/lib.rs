//! Exact tiny research relation. No production security or constant-time claim.
pub mod proof;

pub const RESULT_SCHEMA_VERSION: &str = "1.0.0";
pub const CONTRACT_VERSION: &str = "fzknum-1.0.0";
pub const FIXTURE_VERSION: &str = "numeric-v1";
pub const HEADER: [u8; 16] = *b"FZKNUM01\x01\x00\x03\x00\x10\x00\x00\x00";
pub const INPUT_BYTES: usize = 84;

pub fn contract_digest() -> String {
    use sha2::{Digest, Sha256};
    format!(
        "{:x}",
        Sha256::digest(include_bytes!("../../../specs/numeric-contract-v1.json"))
    )
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ContractError(pub &'static str);
impl std::fmt::Display for ContractError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.0)
    }
}
impl std::error::Error for ContractError {}

#[derive(Clone, Copy, Debug)]
pub struct Batch {
    pub w: i64,
    pub x: [i64; 3],
    pub y: [i64; 3],
    pub counts: [u32; 3],
}
impl Default for Batch {
    fn default() -> Self {
        Self {
            w: 0,
            x: [0; 3],
            y: [0; 3],
            counts: [1; 3],
        }
    }
}
impl Batch {
    pub fn validate(&self) -> Result<(), ContractError> {
        if std::iter::once(&self.w)
            .chain(self.x.iter())
            .chain(self.y.iter())
            .any(|v| !(-32..=32).contains(v))
        {
            return Err(ContractError("input-range"));
        }
        if self.counts.iter().any(|v| !(1..=4).contains(v)) {
            return Err(ContractError("count-range"));
        }
        Ok(())
    }
    pub fn decode(bytes: &[u8]) -> Result<Self, ContractError> {
        if bytes.len() != INPUT_BYTES || bytes[..16] != HEADER {
            return Err(ContractError("canonical-length-or-header"));
        }
        let i64_at = |offset| -> Result<i64, ContractError> {
            Ok(i64::from_le_bytes(
                bytes[offset..offset + 8]
                    .try_into()
                    .map_err(|_| ContractError("canonical-integer"))?,
            ))
        };
        let mut batch = Self {
            w: i64_at(16)?,
            ..Self::default()
        };
        for i in 0..3 {
            let offset = 24 + i * 20;
            batch.x[i] = i64_at(offset)?;
            batch.y[i] = i64_at(offset + 8)?;
            batch.counts[i] = u32::from_le_bytes(
                bytes[offset + 16..offset + 20]
                    .try_into()
                    .map_err(|_| ContractError("canonical-count"))?,
            );
        }
        batch.validate()?;
        Ok(batch)
    }
    pub fn encode(&self) -> Result<[u8; INPUT_BYTES], ContractError> {
        self.validate()?;
        let mut output = [0; INPUT_BYTES];
        output[..16].copy_from_slice(&HEADER);
        output[16..24].copy_from_slice(&self.w.to_le_bytes());
        for i in 0..3 {
            let offset = 24 + i * 20;
            output[offset..offset + 8].copy_from_slice(&self.x[i].to_le_bytes());
            output[offset + 8..offset + 16].copy_from_slice(&self.y[i].to_le_bytes());
            output[offset + 16..offset + 20].copy_from_slice(&self.counts[i].to_le_bytes());
        }
        Ok(output)
    }
}

/// Euclidean division then round-to-nearest, ties-to-even, for bounded operands.
pub fn round_even(n: i128, d: i128) -> Result<i128, ContractError> {
    if !(-(1 << 20)..=(1 << 20)).contains(&n) || !(1..=16).contains(&d) {
        return Err(ContractError("division-range"));
    }
    let (q, r) = (n.div_euclid(d), n.rem_euclid(d));
    Ok(q + i128::from(2 * r > d || (2 * r == d && q.rem_euclid(2) == 1)))
}

#[derive(Clone, Debug)]
pub struct Witness {
    pub predictions: [i64; 3],
    pub gradients: [i64; 3],
    pub updates: [i64; 3],
    pub output: i64,
}
pub fn evaluate(batch: &Batch) -> Result<Witness, ContractError> {
    batch.validate()?;
    let mut result = Witness {
        predictions: [0; 3],
        gradients: [0; 3],
        updates: [0; 3],
        output: 0,
    };
    let mut numerator = 0_i128;
    let mut denominator = 0_i128;
    for i in 0..3 {
        let prediction = round_even(i128::from(batch.w) * i128::from(batch.x[i]), 16)?;
        let gradient = round_even(
            (prediction - i128::from(batch.y[i])) * i128::from(batch.x[i]),
            16,
        )?;
        let update = i128::from(batch.w) - round_even(gradient, 4)?;
        result.predictions[i] = i64::try_from(prediction).map_err(|_| ContractError("overflow"))?;
        result.gradients[i] = i64::try_from(gradient).map_err(|_| ContractError("overflow"))?;
        result.updates[i] = i64::try_from(update).map_err(|_| ContractError("overflow"))?;
        numerator += update * i128::from(batch.counts[i]);
        denominator += i128::from(batch.counts[i]);
    }
    result.output = i64::try_from(round_even(numerator, denominator)?)
        .map_err(|_| ContractError("overflow"))?;
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn exact_hand_vector_and_negative_ties() {
        let b = Batch {
            w: 8,
            x: [16, -8, 24],
            y: [16, -16, 8],
            counts: [1, 2, 1],
        };
        let result = evaluate(&b).expect("valid fixture");
        assert_eq!(result.predictions, [8, -4, 12]);
        assert_eq!(result.gradients, [-8, -6, 6]);
        assert_eq!(result.updates, [10, 10, 6]);
        assert_eq!(result.output, 9);
        assert_eq!(round_even(-6, 4).expect("valid"), -2);
        assert_eq!(round_even(-2, 4).expect("valid"), 0);
        assert_eq!(round_even(6, 4).expect("valid"), 2);
        assert_eq!(
            Batch::decode(&b.encode().expect("encode"))
                .expect("decode")
                .w,
            8
        );
    }
    #[test]
    fn rejects_exceptions() {
        assert!(Batch::decode(&[0; 85]).is_err());
        assert!(
            evaluate(&Batch {
                w: 33,
                ..Batch::default()
            })
            .is_err()
        );
        assert!(
            evaluate(&Batch {
                counts: [0, 1, 1],
                ..Batch::default()
            })
            .is_err()
        );
        assert!(round_even(1, 0).is_err());
    }
}
