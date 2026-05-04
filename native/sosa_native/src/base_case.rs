use crate::colors::{color_bit, color_count, iter_colors};
use crate::instance::CircleInstance;
use crate::stats::Stats;

pub fn solve_base_case(instance: &CircleInstance, stats: &mut Stats) -> bool {
    stats.base_case_calls += 1;
    let mut assigned = vec![0u8; instance.n];
    search(instance, &mut assigned, stats)
}

fn search(instance: &CircleInstance, assigned: &mut [u8], stats: &mut Stats) -> bool {
    stats.base_case_search_nodes += 1;
    let Some(vertex) = choose_vertex(instance, assigned) else {
        return true;
    };
    let mask = available_mask(instance, assigned, vertex);
    for color in iter_colors(mask) {
        assigned[vertex] = color;
        if search(instance, assigned, stats) {
            return true;
        }
        assigned[vertex] = 0;
    }
    false
}

fn choose_vertex(instance: &CircleInstance, assigned: &[u8]) -> Option<usize> {
    let mut best: Option<(u32, usize, usize, usize)> = None;
    for vertex in 0..instance.n {
        if assigned[vertex] != 0 {
            continue;
        }
        let mask = available_mask(instance, assigned, vertex);
        let color_options = color_count(mask);
        let saturation = saturation_degree(instance, assigned, vertex);
        let degree = instance.degree(vertex as u32);
        let key = (
            color_options,
            usize::MAX - saturation,
            usize::MAX - degree,
            vertex,
        );
        if best.is_none_or(|best_key| key < best_key) {
            best = Some(key);
        }
    }
    best.map(|(_, _, _, vertex)| vertex)
}

fn available_mask(instance: &CircleInstance, assigned: &[u8], vertex: usize) -> u8 {
    let mut mask = instance.allowed[vertex];
    for &neighbor in instance.neighbors(vertex as u32) {
        let color = assigned[neighbor as usize];
        if color != 0 {
            mask &= !color_bit(color);
        }
    }
    mask
}

fn saturation_degree(instance: &CircleInstance, assigned: &[u8], vertex: usize) -> usize {
    let mut seen = 0u8;
    for &neighbor in instance.neighbors(vertex as u32) {
        let color = assigned[neighbor as usize];
        if color != 0 {
            seen |= color_bit(color);
        }
    }
    color_count(seen) as usize
}

#[cfg(test)]
mod tests {
    use crate::colors::{BLUE, GREEN, RED};
    use crate::dimacs::parse_dimacs_circle;

    use super::*;

    #[test]
    fn solves_triangle() {
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

        assert!(solve_base_case(&instance, &mut Stats::default()));
    }

    #[test]
    fn rejects_k4() {
        let instance = instance_from_text(
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

        assert!(!solve_base_case(&instance, &mut Stats::default()));
    }

    #[test]
    fn solves_path() {
        let instance = instance_from_text(
            "\
c ircle representation START
c 1 2 1 3 2 3
c ircle representation END
p edge 3 2
e 1 2
e 2 3
",
        );

        assert!(solve_base_case(&instance, &mut Stats::default()));
    }

    #[test]
    fn respects_list_color_restrictions() {
        let mut instance = instance_from_text(
            "\
c ircle representation START
c 1 2 1 2
c ircle representation END
p edge 2 1
e 1 2
",
        );
        instance.allowed[0] = RED;
        instance.allowed[1] = RED;

        assert!(!solve_base_case(&instance, &mut Stats::default()));

        instance.allowed[1] = GREEN | BLUE;
        assert!(solve_base_case(&instance, &mut Stats::default()));
    }

    #[test]
    fn records_search_stats() {
        let instance = instance_from_text(
            "\
c ircle representation START
c 1 1
c ircle representation END
p edge 1 0
",
        );
        let mut stats = Stats::default();

        assert!(solve_base_case(&instance, &mut stats));
        assert_eq!(stats.base_case_calls, 1);
        assert!(stats.base_case_search_nodes > 0);
    }

    fn instance_from_text(text: &str) -> CircleInstance {
        CircleInstance::from_dimacs(parse_dimacs_circle(text).unwrap()).unwrap()
    }
}
