//! Only the fixed original synthetic fixture is accepted; no witness CLI input.
fn main() {
    let result = (|| {
        let mut args = std::env::args_os().skip(1);
        let path = args
            .next()
            .ok_or(fzkml_core::ContractError("private-database-path-required"))?;
        if args.next().is_some() {
            return Err(fzkml_core::ContractError("unexpected-argument"));
        }
        fzkml_core::aggregation::demo(std::path::Path::new(&path))
    })();
    match result {
        Ok(report) => match serde_json::to_string(&report) {
            Ok(text) => println!("{text}"),
            Err(_) => {
                eprintln!("demo-report-encoding");
                std::process::exit(1);
            }
        },
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(1);
        }
    }
}
