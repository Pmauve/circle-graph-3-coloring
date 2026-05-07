use std::path::Path;
use std::time::Instant;

use crate::arc_ops::{chords_contained_in_left_right_arcs, restrict_instance_to_vertices};
use crate::base_case::solve_base_case;
use crate::lemma_38::{visit_lemma_33_family, FullySeparatedInstance};
use crate::reduction::{reduce_exhaustively, ReductionOutcome};
use crate::stats::Stats;
use crate::{SolveConfig, SolveStatus, SolveSummary};
use circle_core::dimacs_circle::{read_dimacs_circle, read_dimacs_circle_geometry};
use circle_core::error::SosaError;
use circle_core::instance::CircleInstance;

pub fn solve_dimacs_circle_file(
    path: &Path,
    config: SolveConfig,
) -> Result<SolveSummary, SosaError> {
    let parse_started = Instant::now();
    let dimacs = if config.validate_graph {
        Some(read_dimacs_circle(path)?)
    } else {
        None
    };
    let geometry = if config.validate_graph {
        None
    } else {
        Some(read_dimacs_circle_geometry(path)?)
    };
    let parse_time_s = parse_started.elapsed().as_secs_f64();

    let build_started = Instant::now();
    let instance = if let Some(dimacs) = dimacs {
        CircleInstance::from_dimacs_with_crossing_validation(dimacs, true)?
    } else {
        CircleInstance::from_dimacs_geometry_and_edge_file(
            geometry.expect("geometry must be parsed when validation is disabled"),
            path,
        )?
    };
    let build_time_s = build_started.elapsed().as_secs_f64();

    let started = Instant::now();
    let mut stats = Stats::with_profile_timers(config.profile);
    stats.set_disable_branch_dedup(config.disable_branch_dedup);
    let status = if solve_instance_recursively(instance, config, &mut stats, 0)? {
        SolveStatus::Colorable
    } else {
        SolveStatus::NotColorable
    };
    let solve_time_s = started.elapsed().as_secs_f64();
    let core_time_s = solve_time_s;

    Ok(SolveSummary {
        status,
        core_time_s,
        parse_time_s,
        build_time_s,
        solve_time_s,
        stats,
        error: None,
    })
}

fn solve_instance_recursively(
    instance: CircleInstance,
    config: SolveConfig,
    stats: &mut Stats,
    depth: u64,
) -> Result<bool, SosaError> {
    stats.solver_calls += 1;
    stats.max_recursion_depth = stats.max_recursion_depth.max(depth);

    let reduced = match reduce_exhaustively(instance, stats)? {
        ReductionOutcome::Conflict => return Ok(false),
        ReductionOutcome::Consistent(reduced) => reduced,
    };
    if reduced.n <= config.base_case_n {
        let started_at = stats.start_timer();
        let is_colorable = solve_base_case(&reduced, config.base_case_algorithm, stats)?;
        stats.base_case_time_ns += Stats::elapsed_ns(started_at);
        return Ok(is_colorable);
    }

    let mut found_colorable_branch = false;
    visit_lemma_33_family(&reduced, stats, |full, stats| {
        if solve_full_branch(full, config, stats, depth + 1)? {
            found_colorable_branch = true;
            return Ok(true);
        }
        Ok(false)
    })?;
    Ok(found_colorable_branch)
}

fn solve_full_branch(
    full: FullySeparatedInstance,
    config: SolveConfig,
    stats: &mut Stats,
    depth: u64,
) -> Result<bool, SosaError> {
    let (left_vertices, right_vertices) =
        chords_contained_in_left_right_arcs(&full.instance, &full.partition);
    let left_n = left_vertices.count_ones();
    let right_n = right_vertices.count_ones();
    let (first_vertices, second_vertices) = if left_n <= right_n {
        (&left_vertices, &right_vertices)
    } else {
        (&right_vertices, &left_vertices)
    };

    stats.arc_restrictions += 1;
    stats.child_instances_built += 1;
    let started_at = stats.start_timer();
    let first = restrict_instance_to_vertices(&full.instance, first_vertices)?;
    stats.arc_restriction_time_ns += Stats::elapsed_ns(started_at);
    if !solve_instance_recursively(first, config, stats, depth)? {
        stats.second_child_instances_skipped += 1;
        return Ok(false);
    }

    stats.arc_restrictions += 1;
    stats.child_instances_built += 1;
    let started_at = stats.start_timer();
    let second = restrict_instance_to_vertices(&full.instance, second_vertices)?;
    stats.arc_restriction_time_ns += Stats::elapsed_ns(started_at);
    solve_instance_recursively(second, config, stats, depth)
}

#[cfg(test)]
mod tests {
    use std::fs;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    use super::*;

    #[test]
    fn solves_small_colorable_file() {
        let path = write_temp_col(
            "\
c ircle representation START
c 1 2 3 1 2 3
c ircle representation END
p edge 3 3
e 1 2
e 1 3
e 2 3
",
        );

        let summary = solve_dimacs_circle_file(
            &path,
            SolveConfig {
                base_case_n: 3,
                base_case_algorithm: crate::BaseCaseAlgorithm::Backtracking,
                validate_graph: true,
                profile: false,
                disable_branch_dedup: false,
            },
        )
        .unwrap();

        assert_eq!(summary.status, SolveStatus::Colorable);
        assert!(summary.error.is_none());
        let _ = fs::remove_file(path);
    }

    #[test]
    fn solves_small_uncolorable_file() {
        let path = write_temp_col(
            "\
c ircle representation START
c 1 2 3 4 1 2 3 4
c ircle representation END
p edge 4 6
e 1 2
e 1 3
e 1 4
e 2 3
e 2 4
e 3 4
",
        );

        let summary = solve_dimacs_circle_file(
            &path,
            SolveConfig {
                base_case_n: 4,
                base_case_algorithm: crate::BaseCaseAlgorithm::Backtracking,
                validate_graph: true,
                profile: false,
                disable_branch_dedup: false,
            },
        )
        .unwrap();

        assert_eq!(summary.status, SolveStatus::NotColorable);
        assert!(summary.error.is_none());
        let _ = fs::remove_file(path);
    }

    #[test]
    fn solves_above_base_case_threshold() {
        let path = write_temp_col(
            "\
c ircle representation START
c 1 2 3 1 2 3
c ircle representation END
p edge 3 3
e 1 2
e 1 3
e 2 3
",
        );

        let summary = solve_dimacs_circle_file(
            &path,
            SolveConfig {
                base_case_n: 2,
                base_case_algorithm: crate::BaseCaseAlgorithm::Backtracking,
                validate_graph: true,
                profile: false,
                disable_branch_dedup: false,
            },
        )
        .unwrap();

        assert_eq!(summary.status, SolveStatus::Colorable);
        assert!(summary.error.is_none());
        let _ = fs::remove_file(path);
    }

    #[test]
    fn can_skip_crossing_validation() {
        let path = write_temp_col(
            "\
c ircle representation START
c 1 1 2 2
c ircle representation END
p edge 2 1
e 1 2
",
        );

        let strict = solve_dimacs_circle_file(
            &path,
            SolveConfig {
                base_case_n: 2,
                base_case_algorithm: crate::BaseCaseAlgorithm::Backtracking,
                validate_graph: true,
                profile: false,
                disable_branch_dedup: false,
            },
        );
        assert!(strict.unwrap_err().to_string().contains("does not match"));

        let skipped = solve_dimacs_circle_file(
            &path,
            SolveConfig {
                base_case_n: 2,
                base_case_algorithm: crate::BaseCaseAlgorithm::Backtracking,
                validate_graph: false,
                profile: false,
                disable_branch_dedup: false,
            },
        )
        .unwrap();
        assert_eq!(skipped.status, SolveStatus::Colorable);
        let _ = fs::remove_file(path);
    }

    fn write_temp_col(content: &str) -> PathBuf {
        let mut path = std::env::temp_dir();
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        path.push(format!("sosa-native-{nanos}.col"));
        fs::write(&path, content).unwrap();
        path
    }
}
