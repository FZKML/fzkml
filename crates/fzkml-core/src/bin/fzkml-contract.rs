use fzkml_core::{Batch, ContractError, evaluate, proof::ResearchSession, round_even};
use std::io::{self, Read};

fn execute() -> Result<(), ContractError> {
    let args: Vec<String> = std::env::args().take(5).collect();
    if args.get(1).map(String::as_str) == Some("round") && args.len() == 4 {
        let n = args[2].parse().map_err(|_| ContractError("integer"))?;
        let d = args[3].parse().map_err(|_| ContractError("integer"))?;
        println!("{}", round_even(n, d)?);
        return Ok(());
    }
    let is_check = args.get(1).map(String::as_str) == Some("check") && args.len() == 3;
    if !is_check && (args.len() != 2 || !matches!(args[1].as_str(), "evaluate" | "smoke")) {
        return Err(ContractError(
            "usage: fzkml-contract evaluate|smoke < canonical-hex",
        ));
    }
    let mut raw = String::new();
    io::stdin()
        .take(172)
        .read_to_string(&mut raw)
        .map_err(|_| ContractError("input-encoding"))?;
    let text = raw.strip_suffix('\n').unwrap_or(&raw);
    if text.len() != 168
        || !text
            .bytes()
            .all(|v| v.is_ascii_digit() || (b'a'..=b'f').contains(&v))
    {
        return Err(ContractError("canonical-hex"));
    }
    let data: Result<Vec<u8>, _> = (0..168)
        .step_by(2)
        .map(|i| u8::from_str_radix(&text[i..i + 2], 16))
        .collect();
    let data = data.map_err(|_| ContractError("canonical-hex"))?;
    let batch = Batch::decode(&data)?;
    if is_check {
        let expected = args[2].parse().map_err(|_| ContractError("integer"))?;
        println!("{}", fzkml_core::proof::check_constraints(&data, expected)?);
    } else if args[1] == "evaluate" {
        println!("{}", evaluate(&batch)?.output);
    } else {
        let session = ResearchSession::setup()?;
        let proved = session.prove(&data)?;
        println!("{}", session.verify(&data, proved.output, &proved.proof)?);
    }
    Ok(())
}
fn main() {
    if let Err(error) = execute() {
        eprintln!("{error}");
        std::process::exit(2);
    }
}
