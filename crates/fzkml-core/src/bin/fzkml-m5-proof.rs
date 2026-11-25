//! Run all bounded M5 proof workloads on public synthetic inputs.
use fzkml_core::model_workloads::{MEDIAN_INPUT, NEURAL_INPUT, Relation, measure};
use serde_json::json;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let median = measure(Relation::Median, &MEDIAN_INPUT)?;
    let inference = measure(Relation::Inference, &NEURAL_INPUT[..5])?;
    let train = measure(Relation::Train, &NEURAL_INPUT)?;
    println!(
        "{}",
        json!({"median": median, "inference": inference, "train": train})
    );
    Ok(())
}
