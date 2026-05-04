use std::collections::HashSet;

use crate::arc_ops::chords_between_arcs;
use crate::error::SosaError;
use crate::instance::CircleInstance;
use crate::lemma_36::visit_lemma_36_family_with_partition;
use crate::partition::{ArcName, CirclePartition};
use crate::stats::Stats;

#[derive(Clone, Debug, Eq, Hash, PartialEq)]
pub struct SemiSeparatedInstance {
    pub instance: CircleInstance,
    pub partition: CirclePartition,
}

pub fn construct_lemma_37_partition(
    instance: &CircleInstance,
) -> Result<CirclePartition, SosaError> {
    let n_positions = instance.endpoint_count();
    if instance.n == 0 {
        return Ok(CirclePartition::empty(n_positions));
    }

    let base_arc_size = instance.n / 2;
    let remainder = 2 * instance.n - 4 * base_arc_size;
    let arc_sizes = [
        base_arc_size + usize::from(0 < remainder),
        base_arc_size + usize::from(1 < remainder),
        base_arc_size + usize::from(2 < remainder),
        base_arc_size + usize::from(3 < remainder),
    ];

    let left_boundary = 0;
    let top_boundary = advance_boundary(n_positions, left_boundary, arc_sizes[0])?;
    let right_boundary = advance_boundary(n_positions, top_boundary, arc_sizes[1])?;
    let bottom_boundary = advance_boundary(n_positions, right_boundary, arc_sizes[2])?;
    CirclePartition::new(
        n_positions,
        left_boundary,
        top_boundary,
        right_boundary,
        bottom_boundary,
    )
}

pub fn visit_lemma_37_family<F>(
    instance: &CircleInstance,
    stats: &mut Stats,
    mut visit: F,
) -> Result<bool, SosaError>
where
    F: FnMut(SemiSeparatedInstance, &mut Stats) -> Result<bool, SosaError>,
{
    stats.lemma_37_calls += 1;
    let partition = construct_lemma_37_partition(instance)?;
    let rotated_partition = partition.rotate_counterclockwise();
    let h_lr = chords_between_arcs(instance, &partition, ArcName::L, &partition, ArcName::R);
    let h_tb = chords_between_arcs(instance, &partition, ArcName::T, &partition, ArcName::B);
    let mut seen = HashSet::new();

    visit_lemma_36_family_with_partition(
        instance,
        &partition,
        &rotated_partition,
        &h_lr,
        &h_tb,
        stats,
        |branch, stats| {
            let semi = SemiSeparatedInstance {
                instance: branch.instance,
                partition: branch.partition,
            };
            if seen.insert(semi.clone()) {
                return visit(semi, stats);
            }
            Ok(false)
        },
    )
}

pub fn is_semi_separated_instance(semi: &SemiSeparatedInstance) -> bool {
    chords_between_arcs(
        &semi.instance,
        &semi.partition,
        ArcName::L,
        &semi.partition,
        ArcName::R,
    )
    .count_ones()
        == 0
}

fn advance_boundary(
    n_positions: usize,
    start_boundary: usize,
    target_active_endpoints: usize,
) -> Result<usize, SosaError> {
    if target_active_endpoints == 0 {
        return Ok(start_boundary);
    }
    if n_positions == 0 {
        return Err(SosaError::Internal(
            "cannot advance a boundary in an empty endpoint order".to_string(),
        ));
    }

    let mut current = start_boundary;
    let mut remaining = target_active_endpoints;
    for _ in 0..n_positions {
        remaining -= 1;
        if remaining == 0 {
            return Ok((current + 1) % n_positions);
        }
        current = (current + 1) % n_positions;
    }
    Err(SosaError::Internal(
        "failed to place balanced Lemma 3.7 partition".to_string(),
    ))
}

#[cfg(test)]
mod tests {
    use crate::dimacs::parse_dimacs_circle;

    use super::*;

    #[test]
    fn constructs_balanced_partition() {
        let instance = instance_from_text(
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

        let partition = construct_lemma_37_partition(&instance).unwrap();

        assert_eq!(partition.left_boundary, 0);
        assert_eq!(partition.top_boundary, 2);
        assert_eq!(partition.right_boundary, 4);
        assert_eq!(partition.bottom_boundary, 5);
    }

    #[test]
    fn visits_semi_separated_instances() {
        let instance = instance_from_text(
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
        let mut branches = Vec::new();

        visit_lemma_37_family(&instance, &mut Stats::default(), |semi, _| {
            branches.push(semi);
            Ok(false)
        })
        .unwrap();

        assert!(!branches.is_empty());
        assert!(branches.iter().all(is_semi_separated_instance));
    }

    fn instance_from_text(text: &str) -> CircleInstance {
        CircleInstance::from_dimacs(parse_dimacs_circle(text).unwrap()).unwrap()
    }
}
