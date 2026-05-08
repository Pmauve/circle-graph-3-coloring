use crate::stats::Stats;
use circle_core::bitset::BitSet;
use circle_core::colors::{singleton_color, ColorMask};
use circle_core::error::SosaError;
use circle_core::instance::CircleInstance;
use circle_core::partition::CirclePartition;

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
    let state = ReductionState::from_instance(&instance);
    reduce_state(instance, state, stats)
}

pub fn reduce_allowed(
    instance: &CircleInstance,
    allowed: Vec<ColorMask>,
    stats: &mut Stats,
) -> Result<ReductionOutcome, SosaError> {
    let state = ReductionState::from_allowed(instance, allowed)?;
    reduce_borrowed_state(instance, state, stats)
}

fn reduce_state(
    instance: CircleInstance,
    mut state: ReductionState,
    stats: &mut Stats,
) -> Result<ReductionOutcome, SosaError> {
    let started_at = stats.start_timer();
    if !run_rr_queue(&instance, &mut state, stats) {
        stats.rr_queue_time_ns += Stats::elapsed_ns(started_at);
        return Ok(ReductionOutcome::Conflict);
    }
    stats.rr_queue_time_ns += Stats::elapsed_ns(started_at);

    if state.deleted_count > 0 {
        stats.rr_deleted_vertices += state.deleted_count as u64;
        stats.rr_rebuilds += 1;
        let started_at = stats.start_timer();
        let rebuilt = instance.rebuild_from_active(&state.active_vertices, state.allowed)?;
        stats.rr_rebuild_time_ns += Stats::elapsed_ns(started_at);
        Ok(ReductionOutcome::Consistent(rebuilt))
    } else {
        let mut reduced = instance;
        reduced.allowed = state.allowed;
        Ok(ReductionOutcome::Consistent(reduced))
    }
}

fn reduce_borrowed_state(
    instance: &CircleInstance,
    mut state: ReductionState,
    stats: &mut Stats,
) -> Result<ReductionOutcome, SosaError> {
    let started_at = stats.start_timer();
    if !run_rr_queue(instance, &mut state, stats) {
        stats.rr_queue_time_ns += Stats::elapsed_ns(started_at);
        return Ok(ReductionOutcome::Conflict);
    }
    stats.rr_queue_time_ns += Stats::elapsed_ns(started_at);

    if state.deleted_count > 0 {
        stats.rr_deleted_vertices += state.deleted_count as u64;
        stats.rr_rebuilds += 1;
        let started_at = stats.start_timer();
        let rebuilt = instance.rebuild_from_active(&state.active_vertices, state.allowed)?;
        stats.rr_rebuild_time_ns += Stats::elapsed_ns(started_at);
        Ok(ReductionOutcome::Consistent(rebuilt))
    } else {
        let mut reduced = instance.clone();
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
    let started_at = stats.start_timer();
    if !run_rr_queue(&instance, &mut state, stats) {
        stats.rr_queue_time_ns += Stats::elapsed_ns(started_at);
        return Ok(PartitionedReductionOutcome::Conflict);
    }
    stats.rr_queue_time_ns += Stats::elapsed_ns(started_at);

    if state.deleted_count > 0 {
        stats.rr_deleted_vertices += state.deleted_count as u64;
        stats.partitioned_rr_rebuilds += 1;
        let started_at = stats.start_timer();
        let (instance, partition) = instance.rebuild_from_active_with_partition(
            &state.active_vertices,
            state.allowed,
            partition,
        )?;
        stats.partitioned_rr_rebuild_time_ns += Stats::elapsed_ns(started_at);
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

pub fn reduce_allowed_with_partition(
    instance: &CircleInstance,
    allowed: Vec<ColorMask>,
    partition: &CirclePartition,
    stats: &mut Stats,
) -> Result<PartitionedReductionOutcome, SosaError> {
    let mut state = ReductionState::from_allowed(instance, allowed)?;
    let started_at = stats.start_timer();
    if !run_rr_queue(instance, &mut state, stats) {
        stats.rr_queue_time_ns += Stats::elapsed_ns(started_at);
        return Ok(PartitionedReductionOutcome::Conflict);
    }
    stats.rr_queue_time_ns += Stats::elapsed_ns(started_at);

    if state.deleted_count > 0 {
        stats.rr_deleted_vertices += state.deleted_count as u64;
        stats.partitioned_rr_rebuilds += 1;
        let started_at = stats.start_timer();
        let (instance, partition) = instance.rebuild_from_active_with_partition(
            &state.active_vertices,
            state.allowed,
            partition,
        )?;
        stats.partitioned_rr_rebuild_time_ns += Stats::elapsed_ns(started_at);
        Ok(PartitionedReductionOutcome::Consistent {
            instance,
            partition,
        })
    } else {
        let mut reduced = instance.clone();
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
        let color_bit = circle_core::colors::color_bit(color);
        state.active_vertices.clear(vertex as usize);
        state.deleted_count += 1;
        stats.rr_steps += 1;
        if !instance.has_adjacency() {
            if !apply_color_to_lazy_circle_neighbors(instance, vertex, color_bit, state, stats) {
                return false;
            }
        } else {
            for &neighbor in instance.neighbors(vertex) {
                if !apply_color_to_neighbor(neighbor, color_bit, state) {
                    return false;
                }
            }
        }
    }
    true
}

fn apply_color_to_lazy_circle_neighbors(
    instance: &CircleInstance,
    vertex: u32,
    color_bit: ColorMask,
    state: &mut ReductionState,
    stats: &mut Stats,
) -> bool {
    let started_at = stats.start_timer();
    stats.lazy_neighbor_queries += 1;
    state.lazy_touched.clear();

    let endpoint_count = instance.endpoint_count();
    let a = instance.left[vertex as usize] as usize;
    let b = instance.right[vertex as usize] as usize;
    let clockwise_len = if a < b {
        b - a - 1
    } else {
        endpoint_count - a - 1 + b
    };
    let counterclockwise_len = endpoint_count - 2 - clockwise_len;
    let (start, len) = if clockwise_len <= counterclockwise_len {
        ((a + 1) % endpoint_count, clockwise_len)
    } else {
        ((b + 1) % endpoint_count, counterclockwise_len)
    };

    stats.lazy_neighbor_endpoints_scanned += len as u64;
    for offset in 0..len {
        let position = (start + offset) % endpoint_count;
        let neighbor = instance.endpoint_at[position] as usize;
        if neighbor == vertex as usize || !state.active_vertices.get(neighbor) {
            continue;
        }
        if state.lazy_endpoint_counts[neighbor] == 0 {
            state.lazy_touched.push(neighbor as u32);
        }
        state.lazy_endpoint_counts[neighbor] += 1;
    }

    let mut ok = true;
    for index in 0..state.lazy_touched.len() {
        let neighbor = state.lazy_touched[index];
        let count = state.lazy_endpoint_counts[neighbor as usize];
        state.lazy_endpoint_counts[neighbor as usize] = 0;
        if count == 1 {
            stats.lazy_neighbor_neighbors_emitted += 1;
            if !apply_color_to_neighbor(neighbor, color_bit, state) {
                ok = false;
            }
        }
    }
    stats.lazy_neighbor_time_ns += Stats::elapsed_ns(started_at);
    ok
}

fn apply_color_to_neighbor(
    neighbor: u32,
    color_bit: ColorMask,
    state: &mut ReductionState,
) -> bool {
    let neighbor_index = neighbor as usize;
    if !state.active_vertices.get(neighbor_index) {
        return true;
    }
    if state.allowed[neighbor_index] & color_bit == 0 {
        return true;
    }
    state.allowed[neighbor_index] &= !color_bit;
    if state.allowed[neighbor_index] == 0 {
        return false;
    }
    if singleton_color(state.allowed[neighbor_index]).is_some() {
        state.queue.push(neighbor);
    }
    true
}

struct ReductionState {
    active_vertices: BitSet,
    allowed: Vec<ColorMask>,
    queue: Vec<u32>,
    lazy_endpoint_counts: Vec<u8>,
    lazy_touched: Vec<u32>,
    deleted_count: usize,
}

impl ReductionState {
    fn from_instance(instance: &CircleInstance) -> Self {
        Self::from_allowed_unchecked(instance, instance.allowed.clone())
    }

    fn from_allowed(instance: &CircleInstance, allowed: Vec<ColorMask>) -> Result<Self, SosaError> {
        if allowed.len() != instance.n {
            return Err(SosaError::Internal(
                "allowed colors must match instance size".to_string(),
            ));
        }
        Ok(Self::from_allowed_unchecked(instance, allowed))
    }

    fn from_allowed_unchecked(instance: &CircleInstance, allowed: Vec<ColorMask>) -> Self {
        let queue = allowed
            .iter()
            .enumerate()
            .filter_map(|(vertex, &mask)| singleton_color(mask).map(|_| vertex as u32))
            .collect();
        Self {
            active_vertices: BitSet::full(instance.n),
            allowed,
            queue,
            lazy_endpoint_counts: if instance.has_adjacency() {
                Vec::new()
            } else {
                vec![0; instance.n]
            },
            lazy_touched: Vec::new(),
            deleted_count: 0,
        }
    }
}

#[cfg(test)]
mod tests {
    use circle_core::colors::{ALL_COLORS, BLUE, GREEN, RED};
    use circle_core::dimacs_circle::parse_dimacs_circle;
    use circle_core::instance::CircleInstance;

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
