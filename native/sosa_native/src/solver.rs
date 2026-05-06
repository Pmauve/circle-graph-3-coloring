use std::path::Path;
use std::time::Instant;

use crate::arc_ops::restrict_instance_to_arc;
use crate::base_case::solve_base_case;
use crate::lemma_38::{visit_lemma_33_family, FullySeparatedInstance};
use crate::reduction::{reduce_exhaustively, ReductionOutcome};
use crate::stats::Stats;
use crate::{SolveConfig, SolveStatus, SolveSummary};
use circle_core::dimacs_circle::read_dimacs_circle;
use circle_core::error::SosaError;
use circle_core::instance::CircleInstance;
use circle_core::partition::ArcName;

pub fn solve_dimacs_circle_file(
    path: &Path,
    config: SolveConfig,
) -> Result<SolveSummary, SosaError> {
    let dimacs = read_dimacs_circle(path)?;
    let instance =
        CircleInstance::from_dimacs_with_crossing_validation(dimacs, config.validate_graph)?;

    let started = Instant::now();
    let mut stats = Stats::default();
    let status = if solve_instance_recursively(instance, config, &mut stats, 0)? {
        SolveStatus::Colorable
    } else {
        SolveStatus::NotColorable
    };
    let core_time_s = started.elapsed().as_secs_f64();

    Ok(SolveSummary {
        status,
        core_time_s,
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
        return Ok(solve_base_case(&reduced, stats));
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
    let left = restrict_instance_to_arc(&full.instance, &full.partition, ArcName::L)?;
    let right = restrict_instance_to_arc(&full.instance, &full.partition, ArcName::R)?;
    let (first, second) = if left.n <= right.n {
        (left, right)
    } else {
        (right, left)
    };

    if !solve_instance_recursively(first, config, stats, depth)? {
        return Ok(false);
    }
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
                validate_graph: true,
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
                validate_graph: true,
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
                validate_graph: true,
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
                validate_graph: true,
            },
        );
        assert!(strict.unwrap_err().to_string().contains("does not match"));

        let skipped = solve_dimacs_circle_file(
            &path,
            SolveConfig {
                base_case_n: 2,
                validate_graph: false,
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
