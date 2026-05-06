use std::env;
use std::path::PathBuf;

use circle_core::error::SosaError;
use sat_native::solver::status_to_output;
use sat_native::{solve_dimacs_edge_file, SatConfig, SatStatus, SatSummary};

fn main() {
    let exit_code = match run() {
        Ok(summary) => {
            print_summary(&summary);
            match summary.status {
                SatStatus::Colorable | SatStatus::NotColorable => 0,
                SatStatus::Unknown => 3,
            }
        }
        Err(error) => {
            println!("s ERROR");
            println!("e {error}");
            match error {
                SosaError::Input(_) => 2,
                SosaError::Internal(_) => 1,
                SosaError::NotImplemented(_) => 3,
            }
        }
    };
    std::process::exit(exit_code);
}

fn run() -> Result<SatSummary, SosaError> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.iter().any(|arg| arg == "--help" || arg == "-h") {
        print_help();
        std::process::exit(0);
    }
    if args.len() < 2 || args[0] != "solve" {
        return Err(SosaError::Input(
            "usage: sat_native solve <instance.col> --solver-bin <path> [--backend dimacs-pipe] [--timeout-s N]"
                .to_string(),
        ));
    }

    let path = PathBuf::from(&args[1]);
    let mut config = SatConfig {
        backend: "dimacs-pipe".to_string(),
        solver_bin: String::new(),
        timeout_s: None,
    };
    let mut index = 2;
    while index < args.len() {
        match args[index].as_str() {
            "--backend" => {
                config.backend = required_value(&args, index, "--backend")?.to_string();
                index += 2;
            }
            "--solver-bin" => {
                config.solver_bin = required_value(&args, index, "--solver-bin")?.to_string();
                index += 2;
            }
            "--timeout-s" => {
                let raw_value = required_value(&args, index, "--timeout-s")?;
                config.timeout_s = Some(raw_value.parse::<u64>().map_err(|_| {
                    SosaError::Input(format!("invalid --timeout-s value {raw_value:?}"))
                })?);
                index += 2;
            }
            unknown => {
                return Err(SosaError::Input(format!("unknown argument {unknown:?}")));
            }
        }
    }
    if config.solver_bin.is_empty() {
        return Err(SosaError::Input("--solver-bin is required".to_string()));
    }

    solve_dimacs_edge_file(&path, config)
}

fn required_value<'a>(args: &'a [String], index: usize, flag: &str) -> Result<&'a str, SosaError> {
    args.get(index + 1)
        .map(String::as_str)
        .ok_or_else(|| SosaError::Input(format!("{flag} requires a value")))
}

fn print_help() {
    println!(
        "usage: sat_native solve <instance.col> --solver-bin <path> [--backend dimacs-pipe] [--timeout-s N]"
    );
}

fn print_summary(summary: &SatSummary) {
    println!("s {}", status_to_output(summary.status));
    println!("t parse_encode_time_s {:.6}", summary.parse_encode_time_s);
    println!("t solve_time_s {:.6}", summary.solve_time_s);
    println!("t core_time_s {:.6}", summary.core_time_s);
    if let Some(error) = &summary.error {
        println!("e {error}");
    }
}
