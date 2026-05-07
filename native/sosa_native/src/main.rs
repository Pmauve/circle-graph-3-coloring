use std::env;
use std::path::PathBuf;

use circle_core::error::SosaError;
use sosa_native::{
    solve_dimacs_circle_file, BaseCaseAlgorithm, SolveConfig, SolveStatus, SolveSummary, Stats,
};

struct CliRun {
    summary: SolveSummary,
    print_stats: bool,
}

fn main() {
    let exit_code = match run() {
        Ok(cli_run) => {
            print_summary(&cli_run.summary, cli_run.print_stats);
            match cli_run.summary.status {
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

fn run() -> Result<CliRun, SosaError> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.iter().any(|arg| arg == "--help" || arg == "-h") {
        print_help();
        std::process::exit(0);
    }
    if args.len() < 2 || args[0] != "solve" {
        return Err(SosaError::Input(
            "usage: sosa_native solve <instance.col> [--base-case-n N] [--base-case-algorithm backtracking|cadical-rustsat|kissat-rustsat] [--skip-graph-validation] [--stats] [--disable-branch-dedup]"
                .to_string(),
        ));
    }

    let path = PathBuf::from(&args[1]);
    let mut config = SolveConfig::default();
    let mut print_stats = false;
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
            "--base-case-algorithm" => {
                let raw_value = args.get(index + 1).ok_or_else(|| {
                    SosaError::Input("--base-case-algorithm requires a value".to_string())
                })?;
                config.base_case_algorithm = BaseCaseAlgorithm::parse(raw_value)?;
                index += 2;
            }
            "--skip-graph-validation" => {
                config.validate_graph = false;
                index += 1;
            }
            "--stats" => {
                print_stats = true;
                config.profile = true;
                index += 1;
            }
            "--disable-branch-dedup" => {
                config.disable_branch_dedup = true;
                index += 1;
            }
            unknown => {
                return Err(SosaError::Input(format!("unknown argument {unknown:?}")));
            }
        }
    }

    Ok(CliRun {
        summary: solve_dimacs_circle_file(&path, config)?,
        print_stats,
    })
}

fn print_help() {
    println!("usage: sosa_native solve <instance.col> [--base-case-n N] [--base-case-algorithm backtracking|cadical-rustsat|kissat-rustsat] [--skip-graph-validation] [--stats] [--disable-branch-dedup]");
}

fn print_summary(summary: &SolveSummary, print_stats: bool) {
    match summary.status {
        SolveStatus::Colorable => println!("s COLORABLE"),
        SolveStatus::NotColorable => println!("s NOT_COLORABLE"),
        SolveStatus::Unknown => println!("s UNKNOWN"),
    }
    println!("t core_time_s {:.6}", summary.core_time_s);
    println!("t parse_time_s {:.6}", summary.parse_time_s);
    println!("t build_time_s {:.6}", summary.build_time_s);
    println!("t solve_time_s {:.6}", summary.solve_time_s);
    if !print_stats {
        if let Some(error) = &summary.error {
            println!("e {error}");
        }
        return;
    }
    println!("t solver_calls {}", summary.stats.solver_calls);
    println!("t base_case_calls {}", summary.stats.base_case_calls);
    println!(
        "t base_case_search_nodes {}",
        summary.stats.base_case_search_nodes
    );
    println!(
        "t base_case_sat_calls {}",
        summary.stats.base_case_sat_calls
    );
    println!(
        "t base_case_sat_clauses {}",
        summary.stats.base_case_sat_clauses
    );
    println!(
        "t base_case_sat_literals {}",
        summary.stats.base_case_sat_literals
    );
    println!(
        "t base_case_sat_build_s {:.6}",
        summary.stats.base_case_sat_build_ns as f64 / 1_000_000_000.0
    );
    println!(
        "t base_case_sat_solve_s {:.6}",
        summary.stats.base_case_sat_solve_ns as f64 / 1_000_000_000.0
    );
    print_profile(&summary.stats);
    if let Some(error) = &summary.error {
        println!("e {error}");
    }
}

fn print_profile(stats: &Stats) {
    println!("p rr_steps {}", stats.rr_steps);
    println!("p rr_deleted_vertices {}", stats.rr_deleted_vertices);
    println!("p rr_rebuilds {}", stats.rr_rebuilds);
    println!(
        "p partitioned_rr_rebuilds {}",
        stats.partitioned_rr_rebuilds
    );
    println!("p base_case_calls {}", stats.base_case_calls);
    println!("p base_case_search_nodes {}", stats.base_case_search_nodes);
    println!("p solver_calls {}", stats.solver_calls);
    println!("p arc_restrictions {}", stats.arc_restrictions);
    println!("p child_instances_built {}", stats.child_instances_built);
    println!(
        "p second_child_instances_skipped {}",
        stats.second_child_instances_skipped
    );
    println!("p lemma_36_calls {}", stats.lemma_36_calls);
    println!("p lemma_37_calls {}", stats.lemma_37_calls);
    println!("p lemma_38_calls {}", stats.lemma_38_calls);
    println!("p lemma_33_calls {}", stats.lemma_33_calls);
    println!(
        "p branch_candidates_generated {}",
        stats.branch_candidates_generated
    );
    println!(
        "p branch_candidates_unique {}",
        stats.branch_candidates_unique
    );
    println!(
        "p branch_candidates_duplicates {}",
        stats.branch_candidates_duplicates
    );
    println!("p max_recursion_depth {}", stats.max_recursion_depth);
    println!("p base_case_time_s {:.6}", ns_to_s(stats.base_case_time_ns));
    println!(
        "p arc_restriction_time_s {:.6}",
        ns_to_s(stats.arc_restriction_time_ns)
    );
    println!("p rr_queue_time_s {:.6}", ns_to_s(stats.rr_queue_time_ns));
    println!(
        "p rr_rebuild_time_s {:.6}",
        ns_to_s(stats.rr_rebuild_time_ns)
    );
    println!(
        "p partitioned_rr_rebuild_time_s {:.6}",
        ns_to_s(stats.partitioned_rr_rebuild_time_ns)
    );
    println!("p lemma_36_time_s {:.6}", ns_to_s(stats.lemma_36_time_ns));
    println!(
        "p lemma_36_branch_setup_time_s {:.6}",
        ns_to_s(stats.lemma_36_branch_setup_time_ns)
    );
    println!(
        "p lemma_36_reduction_time_s {:.6}",
        ns_to_s(stats.lemma_36_reduction_time_ns)
    );
    println!(
        "p lemma_36_dedup_time_s {:.6}",
        ns_to_s(stats.lemma_36_dedup_time_ns)
    );
    println!("p lemma_38_time_s {:.6}", ns_to_s(stats.lemma_38_time_ns));
}

fn ns_to_s(nanos: u128) -> f64 {
    nanos as f64 / 1_000_000_000.0
}
