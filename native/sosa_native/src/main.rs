use std::env;
use std::path::PathBuf;

use circle_core::error::SosaError;
use sosa_native::{solve_dimacs_circle_file, SolveConfig, SolveStatus, SolveSummary};

fn main() {
    let exit_code = match run() {
        Ok(summary) => {
            print_summary(&summary);
            match summary.status {
                SolveStatus::Colorable | SolveStatus::NotColorable => 0,
                SolveStatus::Unknown => 3,
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

fn run() -> Result<SolveSummary, SosaError> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.iter().any(|arg| arg == "--help" || arg == "-h") {
        print_help();
        std::process::exit(0);
    }
    if args.len() < 2 || args[0] != "solve" {
        return Err(SosaError::Input(
            "usage: sosa_native solve <instance.col> [--base-case-n N] [--skip-graph-validation]"
                .to_string(),
        ));
    }

    let path = PathBuf::from(&args[1]);
    let mut config = SolveConfig::default();
    let mut index = 2;
    while index < args.len() {
        match args[index].as_str() {
            "--base-case-n" => {
                let raw_value = args.get(index + 1).ok_or_else(|| {
                    SosaError::Input("--base-case-n requires an integer value".to_string())
                })?;
                config.base_case_n = raw_value.parse::<usize>().map_err(|_| {
                    SosaError::Input(format!("invalid --base-case-n value {raw_value:?}"))
                })?;
                index += 2;
            }
            "--skip-graph-validation" => {
                config.validate_graph = false;
                index += 1;
            }
            unknown => {
                return Err(SosaError::Input(format!("unknown argument {unknown:?}")));
            }
        }
    }

    solve_dimacs_circle_file(&path, config)
}

fn print_help() {
    println!("usage: sosa_native solve <instance.col> [--base-case-n N] [--skip-graph-validation]");
}

fn print_summary(summary: &SolveSummary) {
    match summary.status {
        SolveStatus::Colorable => println!("s COLORABLE"),
        SolveStatus::NotColorable => println!("s NOT_COLORABLE"),
        SolveStatus::Unknown => println!("s UNKNOWN"),
    }
    println!("t core_time_s {:.6}", summary.core_time_s);
    if let Some(error) = &summary.error {
        println!("e {error}");
    }
}
