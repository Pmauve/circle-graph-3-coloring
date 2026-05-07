use circle_core::bitset::BitSet;
use circle_core::error::SosaError;
use circle_core::instance::CircleInstance;
use circle_core::partition::{ArcName, CirclePartition};

pub fn count_endpoints_in_arc(
    instance: &CircleInstance,
    partition: &CirclePartition,
    arc_name: ArcName,
) -> usize {
    partition
        .positions(arc_name)
        .filter(|&position| (instance.endpoint_at[position] as usize) < instance.n)
        .count()
}

pub fn chords_between_arcs(
    instance: &CircleInstance,
    first_partition: &CirclePartition,
    first_arc_name: ArcName,
    second_partition: &CirclePartition,
    second_arc_name: ArcName,
) -> BitSet {
    let mut vertices = BitSet::empty(instance.n);
    for vertex in 0..instance.n {
        let left = instance.left[vertex] as usize;
        let right = instance.right[vertex] as usize;
        let crosses_arcs = (first_partition.contains_position(first_arc_name, left)
            && second_partition.contains_position(second_arc_name, right))
            || (first_partition.contains_position(first_arc_name, right)
                && second_partition.contains_position(second_arc_name, left));
        if crosses_arcs {
            vertices.set(vertex, true);
        }
    }
    vertices
}

pub fn restrict_instance_to_arc(
    instance: &CircleInstance,
    partition: &CirclePartition,
    arc_name: ArcName,
) -> Result<CircleInstance, SosaError> {
    let mut active = BitSet::empty(instance.n);
    for vertex in 0..instance.n {
        let Some(left_arc) = partition.endpoint_arc(instance.left[vertex] as usize) else {
            continue;
        };
        let Some(right_arc) = partition.endpoint_arc(instance.right[vertex] as usize) else {
            continue;
        };
        if left_arc == arc_name && right_arc == arc_name {
            active.set(vertex, true);
        }
    }
    instance.rebuild_from_active(&active, instance.allowed.clone())
}

pub fn restrict_instance_to_vertices(
    instance: &CircleInstance,
    active: &BitSet,
) -> Result<CircleInstance, SosaError> {
    instance.rebuild_from_active(active, instance.allowed.clone())
}

pub fn chords_contained_in_left_right_arcs(
    instance: &CircleInstance,
    partition: &CirclePartition,
) -> (BitSet, BitSet) {
    let mut left = BitSet::empty(instance.n);
    let mut right = BitSet::empty(instance.n);
    for vertex in 0..instance.n {
        let Some(first_arc) = partition.endpoint_arc(instance.left[vertex] as usize) else {
            continue;
        };
        let Some(second_arc) = partition.endpoint_arc(instance.right[vertex] as usize) else {
            continue;
        };
        if first_arc == ArcName::L && second_arc == ArcName::L {
            left.set(vertex, true);
        } else if first_arc == ArcName::R && second_arc == ArcName::R {
            right.set(vertex, true);
        }
    }
    (left, right)
}

pub fn advance_boundary_inside_arc(
    instance: &CircleInstance,
    partition: &CirclePartition,
    arc_name: ArcName,
    target_active_endpoints: usize,
) -> Result<usize, SosaError> {
    if target_active_endpoints == 0 {
        return match arc_name {
            ArcName::T => Ok(partition.top_boundary),
            ArcName::B => Ok(partition.bottom_boundary),
            _ => Err(SosaError::Internal(
                "only T and B arcs are split by Lemma 3.8".to_string(),
            )),
        };
    }

    let mut remaining = target_active_endpoints;
    for position in partition.positions(arc_name) {
        let owner = instance.endpoint_at[position] as usize;
        if owner >= instance.n {
            continue;
        }
        remaining -= 1;
        if remaining == 0 {
            return Ok((position + 1) % partition.n_endpoints);
        }
    }
    Err(SosaError::Internal(
        "failed to advance partition boundary".to_string(),
    ))
}

#[cfg(test)]
mod tests {
    use circle_core::dimacs_circle::parse_dimacs_circle;
    use circle_core::partition::ArcName::{B, L, R, T};

    use super::*;

    #[test]
    fn counts_endpoints_and_cross_arc_chords() {
        let instance = triangle_instance();
        let partition = CirclePartition::new(instance.endpoint_count(), 0, 2, 4, 5).unwrap();

        assert_eq!(count_endpoints_in_arc(&instance, &partition, L), 2);
        assert_eq!(count_endpoints_in_arc(&instance, &partition, T), 2);

        let between = chords_between_arcs(&instance, &partition, L, &partition, R);
        assert_eq!(between.iter_ones().collect::<Vec<_>>(), vec![1]);
    }

    #[test]
    fn restricts_instance_to_internal_arc_chords() {
        let instance = nested_instance();
        let partition = CirclePartition::new(instance.endpoint_count(), 0, 2, 0, 0).unwrap();

        let restricted = restrict_instance_to_arc(&instance, &partition, L).unwrap();

        assert_eq!(restricted.n, 1);
        assert!(restricted.neighbors(0).is_empty());
    }

    #[test]
    fn advances_boundary_by_active_endpoint_count() {
        let instance = triangle_instance();
        let partition = CirclePartition::new(instance.endpoint_count(), 0, 2, 5, 5).unwrap();

        assert_eq!(
            advance_boundary_inside_arc(&instance, &partition, T, 2).unwrap(),
            4
        );
        assert_eq!(
            advance_boundary_inside_arc(&instance, &partition, B, 0).unwrap(),
            5
        );
    }

    fn triangle_instance() -> CircleInstance {
        CircleInstance::from_dimacs(
            parse_dimacs_circle(
                "\
c ircle representation START
c 1 2 3 1 2 3
c ircle representation END
p edge 3 3
e 1 2
e 1 3
e 2 3
",
            )
            .unwrap(),
        )
        .unwrap()
    }

    fn nested_instance() -> CircleInstance {
        CircleInstance::from_dimacs(
            parse_dimacs_circle(
                "\
c ircle representation START
c 1 1 2 2
c ircle representation END
p edge 2 0
",
            )
            .unwrap(),
        )
        .unwrap()
    }
}
