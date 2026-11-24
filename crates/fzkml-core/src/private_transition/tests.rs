use super::*;
use crate::proof::rounded;
use ark_bn254::{Fq2, G1Affine, G2Affine};
use ark_ff::UniformRand;
use ark_r1cs_std::R1CSVar;
use ark_relations::r1cs::ConstraintSystem;
use rand::{SeedableRng, rngs::StdRng};

fn fixture() -> Batch {
    Batch {
        w: 8,
        x: [16, -8, 24],
        y: [16, -16, 8],
        counts: [1, 2, 1],
    }
}
fn opening(batch: Batch) -> Opening {
    Opening {
        batch,
        model_blinding: [11; 32],
        data_blinding: [19; 32],
    }
}
fn satisfied(circuit: PrivateCircuit) -> bool {
    let cs = ConstraintSystem::new_ref();
    circuit
        .generate_constraints(cs.clone())
        .expect("synthesize public test fixture");
    cs.is_satisfied().expect("check")
}

#[test]
fn canonical_context_and_statement_are_unambiguous() {
    let b = fixture();
    let s = opening(b).statement(Context::synthetic([5; 32], b.counts, b.w), 9);
    assert_eq!(
        Context::decode(&s.context.encode()).expect("decode"),
        s.context
    );
    assert_eq!(Statement::decode(&s.encode()).expect("decode"), s);
    let format_valid_but_unrepresentable = Context::synthetic([5; 32], b.counts, 33);
    assert!(Context::decode(&format_valid_but_unrepresentable.encode()).is_ok());
    for length in [0, 1, STATEMENT_BYTES - 1, STATEMENT_BYTES + 1] {
        assert!(Statement::decode(&vec![0; length]).is_err());
    }
    let mut duplicate = s.context.clone();
    duplicate.roster[1] = duplicate.roster[0];
    assert!(Context::decode(&duplicate.encode()).is_err());
    for offset in [132, 164, 196, 228, 260] {
        let mut bytes = s.context.encode();
        bytes[offset] ^= 1;
        assert!(Context::decode(&bytes).is_err());
    }
    let mut swapped = s.context.clone();
    swapped.roster.swap(0, 1);
    assert_ne!(hash(&swapped.encode()), hash(&s.context.encode()));
}

#[test]
fn actual_private_circuit_binds_model_data_initialization_and_output() {
    let b = fixture();
    let original = opening(b);
    let statement = original.statement(Context::synthetic([5; 32], b.counts, b.w), 9);
    assert!(satisfied(PrivateCircuit::new(
        original.clone(),
        evaluate(&b).expect("eval"),
        statement.clone()
    )));
    // The parent state value is a public circuit input tied to the private w.
    let mut wrong_parent_context = statement.context.clone();
    wrong_parent_context.parent_value -= 1;
    let wrong_parent = opening(b).statement(wrong_parent_context, 9);
    let mut parent_mutant =
        PrivateCircuit::new(opening(b), evaluate(&b).expect("eval"), wrong_parent);
    assert!(!satisfied(parent_mutant.clone()));
    parent_mutant.fault = Some(TestFault::OmitParentEquality);
    assert!(satisfied(parent_mutant));
    // The output is unique in the intended relation. Removing its equality admits 10.
    let mut wrong = statement.clone();
    wrong.output = 10;
    let mut output_mutant =
        PrivateCircuit::new(original.clone(), evaluate(&b).expect("eval"), wrong);
    assert!(!satisfied(output_mutant.clone()));
    output_mutant.fault = Some(TestFault::OmitOutputEquality);
    assert!(satisfied(output_mutant));
    // Same committed initialization (8), actual arithmetic initialization (9).
    let mut bad_model = original.clone();
    bad_model.batch.w = 9;
    let bad_witness = evaluate(&bad_model.batch).expect("eval");
    assert_eq!(bad_witness.output, 10);
    let mut wrong = statement.clone();
    wrong.output = bad_witness.output;
    let mut mutant = PrivateCircuit::new(bad_model, bad_witness, wrong);
    assert!(!satisfied(mutant.clone()));
    mutant.fault = Some(TestFault::DetachedModel(b.w.to_le_bytes()));
    assert!(satisfied(mutant));
    // Same data commitment, changed training data. Only the detached-byte mutant passes.
    let mut bad_data = original;
    bad_data.batch.x[0] = 0;
    let bad_witness = evaluate(&bad_data.batch).expect("eval");
    assert_eq!(bad_witness.output, 8);
    let mut wrong = statement;
    wrong.output = bad_witness.output;
    let mut mutant = PrivateCircuit::new(bad_data, bad_witness, wrong);
    assert!(!satisfied(mutant.clone()));
    mutant.fault = Some(TestFault::DetachedData(data_bytes(&b)));
    assert!(satisfied(mutant));
}

#[test]
fn omitted_remainder_range_and_exception_mutants_have_counterexamples() {
    // Unique-but-wrong: y=x+1 has one y for x=1, yet the intended function is y=x.
    let cs = ConstraintSystem::new_ref();
    let x = FpVar::new_input(cs.clone(), || Ok(field(1))).expect("allocate");
    let y = FpVar::new_witness(cs.clone(), || Ok(field(2))).expect("allocate");
    y.enforce_equal(&(x + field(1))).expect("constraint");
    assert!(cs.is_satisfied().expect("check"));
    assert_ne!(y.value().expect("assigned output"), field(1));
    // Dropping 0<=r<d admits 1=2*1+(-1), with q=1 rather than RNE(1/2)=0.
    let cs = ConstraintSystem::new_ref();
    let q = FpVar::new_witness(cs.clone(), || Ok(field(1))).expect("allocate");
    let r = FpVar::new_witness(cs.clone(), || Ok(field(-1))).expect("allocate");
    (&q * field(2) + &r)
        .enforce_equal(&FpVar::Constant(field(1)))
        .expect("constraint");
    assert!(cs.is_satisfied().expect("check"));
    bound(cs.clone(), &r, -1, 0, 1).expect("bound");
    assert!(!cs.is_satisfied().expect("range must reject"));
    assert_eq!(crate::round_even(1, 2).expect("oracle case"), 0);
    // A missing divisor check turns 0=0*q into an apparent division result.
    let cs = ConstraintSystem::new_ref();
    let q = FpVar::new_witness(cs.clone(), || Ok(field(7))).expect("allocate");
    (&q * field(0))
        .enforce_equal(&FpVar::Constant(field(0)))
        .expect("constraint");
    assert!(cs.is_satisfied().expect("mutant passes"));
    assert!(crate::round_even(0, 0).is_err());
    let cs = ConstraintSystem::new_ref();
    let bad = FpVar::new_witness(cs.clone(), || Ok(field(33))).expect("allocate");
    assert!(cs.is_satisfied().expect("no bound"));
    bound(cs.clone(), &bad, 33, -32, 32).expect("bound");
    assert!(!cs.is_satisfied().expect("strict bound"));
    // The actual shared rounding gadget still gives the intended signed tie result.
    let cs = ConstraintSystem::new_ref();
    let result = rounded(
        cs.clone(),
        &FpVar::Constant(field(-2)),
        -2,
        &FpVar::Constant(field(4)),
        4,
        4,
    )
    .expect("round");
    result
        .enforce_equal(&FpVar::Constant(field(0)))
        .expect("result");
    assert!(cs.is_satisfied().expect("strict relation"));
}

#[test]
fn full_state_aggregation_is_not_parent_plus_rounded_delta_aggregation() {
    // Exact v1 relation: client full-state outputs are [1, 1, 2], with counts
    // [1, 1, 2]. RNE(6/4)=2, while the weighted delta mean is RNE(2/4)=0,
    // so parent 1 plus the rounded delta is 1. Rounding cannot move across
    // the state/delta boundary.
    let batch = Batch {
        w: 1,
        x: [0, 0, 8],
        y: [0, 0, 8],
        counts: [1, 1, 2],
    };
    let witness = evaluate(&batch).expect("bounded exact transition");
    assert_eq!(witness.updates, [1, 1, 2]);
    assert_eq!(witness.output, 2);
    assert_eq!(crate::round_even(6, 4).expect("full state"), 2);
    assert_eq!(1 + crate::round_even(2, 4).expect("weighted delta"), 1);
    assert_ne!(
        i128::from(witness.output),
        1 + crate::round_even(2, 4).expect("delta")
    );
}

#[test]
fn valid_output_outside_next_round_input_range_is_not_continuable() {
    let batch = Batch {
        w: 32,
        x: [8, 8, 8],
        y: [32, 32, 32],
        counts: [1, 2, 1],
    };
    let witness = evaluate(&batch).expect("valid bounded transition");
    assert_eq!(witness.updates, [34, 34, 34]);
    assert_eq!(witness.output, 34);

    // The v2 context format can carry this public output, but numeric-v1 only
    // admits an initial weight in [-32,32]; the lineage gate must stop here.
    let context = Context::synthetic([5; 32], batch.counts, witness.output);
    assert!(Context::decode(&context.encode()).is_ok());
    assert_eq!(
        ensure_next_initial_weight(witness.output),
        Err(ContractError("lineage-parent-outside-next-input-range"))
    );
    let next_batch = Batch {
        w: witness.output,
        ..batch
    };
    assert!(next_batch.validate().is_err());
}

#[test]
fn bounded_seeded_parser_fuzz_and_noncanonical_points_fail_closed() {
    let mut rng = StdRng::seed_from_u64(20261124);
    for _ in 0..256 {
        let length = (rng.next_u32() as usize) % (ENVELOPE_BYTES + 32);
        let mut data = vec![0; length];
        rng.fill_bytes(&mut data);
        assert!(Envelope::decode(&data).is_err());
    }
    let b = fixture();
    let statement = opening(b).statement(Context::synthetic([5; 32], b.counts, b.w), 9);
    let bytes = Envelope {
        statement,
        proof: [255; 128],
    }
    .encode();
    assert!(Envelope::decode(&bytes).is_err());
    for length in 0..ENVELOPE_BYTES {
        assert!(Envelope::decode(&bytes[..length]).is_err());
    }
    let mut oversized = bytes.to_vec();
    oversized.extend_from_slice(&[0; 32]);
    assert!(Envelope::decode(&oversized).is_err());
}

#[test]
fn on_curve_but_wrong_subgroup_point_is_rejected() {
    let mut rng = StdRng::seed_from_u64(20261125);
    let point = (0..128)
        .find_map(|_| {
            G2Affine::get_point_from_x_unchecked(Fq2::rand(&mut rng), false)
                .filter(|p| !p.is_in_correct_subgroup_assuming_on_curve())
        })
        .expect("seeded on-curve non-subgroup example");
    assert!(point.is_on_curve());
    let invalid = Proof::<Bn254> {
        a: G1Affine::default(),
        b: point,
        c: G1Affine::default(),
    };
    let mut encoded = Vec::new();
    invalid
        .serialize_compressed(&mut encoded)
        .expect("serialize");
    let b = fixture();
    let statement = opening(b).statement(Context::synthetic([5; 32], b.counts, b.w), 9);
    let bytes = Envelope {
        statement,
        proof: encoded.try_into().expect("fixed proof size"),
    }
    .encode();
    assert!(Envelope::decode(&bytes).is_err());
}
