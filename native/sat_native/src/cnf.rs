pub const NUM_COLORS: usize = 3;

#[inline]
pub fn color_var(vertex_1based: usize, color_zero_based: usize) -> i32 {
    ((vertex_1based - 1) * NUM_COLORS + color_zero_based + 1) as i32
}

#[inline]
pub fn n_vars(n_vertices: usize) -> usize {
    n_vertices * NUM_COLORS
}

#[inline]
pub fn n_clauses(n_vertices: usize, n_edges: usize) -> usize {
    n_vertices + NUM_COLORS * n_edges
}

pub fn vertex_clause(vertex_1based: usize) -> [i32; NUM_COLORS] {
    [
        color_var(vertex_1based, 0),
        color_var(vertex_1based, 1),
        color_var(vertex_1based, 2),
    ]
}

pub fn edge_clauses(u_1based: usize, v_1based: usize) -> [[i32; 2]; NUM_COLORS] {
    [
        [-color_var(u_1based, 0), -color_var(v_1based, 0)],
        [-color_var(u_1based, 1), -color_var(v_1based, 1)],
        [-color_var(u_1based, 2), -color_var(v_1based, 2)],
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn maps_vertices_and_colors_to_dense_vars() {
        assert_eq!(color_var(1, 0), 1);
        assert_eq!(color_var(1, 2), 3);
        assert_eq!(color_var(2, 0), 4);
        assert_eq!(color_var(10, 2), 30);
    }

    #[test]
    fn counts_standard_three_color_cnf_shape() {
        assert_eq!(n_vars(4), 12);
        assert_eq!(n_clauses(4, 6), 22);
    }

    #[test]
    fn builds_vertex_and_edge_clauses() {
        assert_eq!(vertex_clause(2), [4, 5, 6]);
        assert_eq!(edge_clauses(1, 2), [[-1, -4], [-2, -5], [-3, -6]]);
    }
}
