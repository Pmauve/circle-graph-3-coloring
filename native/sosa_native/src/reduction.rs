use crate::bitset::BitSet;
use crate::colors::{singleton_color, ColorMask};
use crate::error::SosaError;
use crate::instance::CircleInstance;
use crate::partition::CirclePartition;
use crate::stats::Stats;

#[derive(Debug, Eq, PartialEq)]
pub enum ReductionOutcome {
    Consistent(CircleInstance),
    Conflict,
}

pub enum PartitionedReductionOutcome {
    Consistent {
        instance: CircleInstance,
        partition: CirclePartition,
    },
    Conflict,
}

pub fn reduce_exhaustively(
    instance: CircleInstance,
    stats: &mut Stats,
) -> Result<ReductionOutcome, SosaError> {
    let mut state = ReductionState::from_instance(&instance);
    if !run_rr_queue(&instance, &mut state, stats) {
        return Ok(ReductionOutcome::Conflict);
    }

    if state.deleted_count > 0 {
        stats.rr_deleted_vertices += state.deleted_count as u64;
        Ok(ReductionOutcome::Consistent(instance.rebuild_from_active(
            &state.active_vertices,
            state.allowed,
        )?))
    } else {
        let mut reduced = instance;
        reduced.allowed = state.allowed;
        Ok(ReductionOutcome::Consistent(reduced))
    }
}

pub fn reduce_exhaustively_with_partition(
    instance: CircleInstance,
    partition: &CirclePartition,
    stats: &mut Stats,
) -> Result<PartitionedReductionOutcome, SosaError> {
    let mut state = ReductionState::from_instance(&instance);
    if !run_rr_queue(&instance, &mut state, stats) {
        return Ok(PartitionedReductionOutcome::Conflict);
    }

    if state.deleted_count > 0 {
        stats.rr_deleted_vertices += state.deleted_count as u64;
        let (instance, partition) = instance.rebuild_from_active_with_partition(
            &state.active_vertices,
            state.allowed,
            partition,
        )?;
        Ok(PartitionedReductionOutcome::Consistent {
            instance,
            partition,
        })
    } else {
        let mut reduced = instance;
        reduced.allowed = state.allowed;
        Ok(PartitionedReductionOutcome::Consistent {
            instance: reduced,
            partition: partition.clone(),
        })
    }
}

fn run_rr_queue(instance: &CircleInstance, state: &mut ReductionState, stats: &mut Stats) -> bool {
    while let Some(vertex) = state.queue.pop() {
        if !state.active_vertices.get(vertex as usize) {
            continue;
        }
        let Some(color) = singleton_color(state.allowed[vertex as usize]) else {
            continue;
        };
        let color_bit = crate::colors::color_bit(color);
        state.active_vertices.clear(vertex as usize);
        state.deleted_count += 1;
        stats.rr_steps += 1;
        for &neighbor in instance.neighbors(vertex) {
            let neighbor_index = neighbor as usize;
            if !state.active_vertices.get(neighbor_index) {
                continue;
            }
            if state.allowed[neighbor_index] & color_bit == 0 {
                continue;
            }
            state.allowed[neighbor_index] &= !color_bit;
            if state.allowed[neighbor_index] == 0 {
                return false;
            }
            if singleton_color(state.allowed[neighbor_index]).is_some() {
                state.queue.push(neighbor);
            }
        }
    }
    true
}

struct ReductionState {
    active_vertices: BitSet,
    allowed: Vec<ColorMask>,
    queue: Vec<u32>,
    deleted_count: usize,
}

impl ReductionState {
    fn from_instance(instance: &CircleInstance) -> Self {
        let queue = instance
            .allowed
            .iter()
            .enumerate()
            .filter_map(|(vertex, &mask)| singleton_color(mask).map(|_| vertex as u32))
            .collect();
        Self {
            active_vertices: BitSet::full(instance.n),
            allowed: instance.allowed.clone(),
            queue,
            deleted_count: 0,
        }
    }
}

#[cfg(test)]
mod tests {
    use crate::colors::{ALL_COLORS, BLUE, GREEN, RED};
    use crate::dimacs::parse_dimacs_circle;
    use crate::instance::CircleInstance;

    use super::*;

    #[test]
    fn leaves_unconstrained_instance_unchanged() {
        let instance = edge_instance();
        let mut stats = Stats::default();

        let outcome = reduce_exhaustively(instance.clone(), &mut stats).unwrap();

        assert_eq!(outcome, ReductionOutcome::Consistent(instance));
        assert_eq!(stats.rr_steps, 0);
    }

    #[test]
    fn propagates_singleton_color_to_neighbor() {
        let mut instance = edge_instance();
        instance.allowed[0] = RED;
        let mut stats = Stats::default();

        let outcome = reduce_exhaustively(instance, &mut stats).unwrap();
        let ReductionOutcome::Consistent(reduced) = outcome else {
            panic!("expected consistent reduction");
        };

        assert_eq!(reduced.n, 1);
        assert_eq!(reduced.allowed[0], GREEN | BLUE);
        assert_eq!(stats.rr_steps, 1);
        assert_eq!(stats.rr_deleted_vertices, 1);
    }

    #[test]
    fn detects_adjacent_singleton_conflict() {
        let mut instance = edge_instance();
        instance.allowed[0] = RED;
        instance.allowed[1] = RED;
        let mut stats = Stats::default();

        let outcome = reduce_exhaustively(instance, &mut stats).unwrap();

        assert_eq!(outcome, ReductionOutcome::Conflict);
    }

    #[test]
    fn propagates_chain() {
        let mut instance = path_instance();
        instance.allowed[0] = RED;
        instance.allowed[1] = RED | GREEN;
        instance.allowed[2] = ALL_COLORS;
        let mut stats = Stats::default();

        let outcome = reduce_exhaustively(instance, &mut stats).unwrap();
        let ReductionOutcome::Consistent(reduced) = outcome else {
            panic!("expected consistent reduction");
        };

        assert_eq!(reduced.n, 1);
        assert_eq!(reduced.allowed[0], RED | BLUE);
        assert_eq!(stats.rr_steps, 2);
        assert_eq!(stats.rr_deleted_vertices, 2);
    }

    #[test]
    fn returns_translated_partition_for_rebuilt_instance() {
        let mut instance = path_instance();
        instance.allowed[0] = RED;
        let partition = CirclePartition::new(instance.endpoint_count(), 0, 1, 3, 5).unwrap();
        let mut stats = Stats::default();

        let outcome = reduce_exhaustively_with_partition(instance, &partition, &mut stats).unwrap();
        let PartitionedReductionOutcome::Consistent {
            instance,
            partition,
        } = outcome
        else {
            panic!("expected consistent reduction");
        };

        assert_eq!(instance.n, 2);
        assert_eq!(partition, CirclePartition::new(4, 0, 0, 1, 3).unwrap());
    }

    fn edge_instance() -> CircleInstance {
        let dimacs = parse_dimacs_circle(
            "\
c ircle representation START
c 1 2 1 2
c ircle representation END
p edge 2 1
e 1 2
",
        )
        .unwrap();
        CircleInstance::from_dimacs(dimacs).unwrap()
    }

    fn path_instance() -> CircleInstance {
        let dimacs = parse_dimacs_circle(
            "\
c ircle representation START
c 1 2 1 3 2 3
c ircle representation END
p edge 3 2
e 1 2
e 2 3
",
        )
        .unwrap();
        CircleInstance::from_dimacs(dimacs).unwrap()
    }
}
