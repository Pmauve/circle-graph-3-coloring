use crate::dimacs_circle::DimacsCircleGeometry;
use crate::error::SosaError;

pub fn visit_circle_crossing_edges<F>(
    geometry: &DimacsCircleGeometry,
    mut visit: F,
) -> Result<usize, SosaError>
where
    F: FnMut(usize, usize) -> Result<(), SosaError>,
{
    let n = geometry.n;
    let mut seen_once = vec![false; n + 1];
    let mut active = vec![false; n + 1];
    let mut previous = vec![0usize; n + 1];
    let mut next = vec![0usize; n + 1];
    let mut tail = 0usize;
    let mut emitted = 0usize;

    for &raw_vertex in &geometry.chord_endpoint_order {
        let vertex = raw_vertex as usize;
        if !seen_once[vertex] {
            seen_once[vertex] = true;
            active[vertex] = true;
            if tail != 0 {
                previous[vertex] = tail;
                next[tail] = vertex;
            }
            tail = vertex;
            continue;
        }

        if !active[vertex] {
            return Err(SosaError::Internal(format!(
                "circle edge sweep closed inactive vertex {vertex}"
            )));
        }
        let mut other = next[vertex];
        while other != 0 {
            visit(vertex, other)?;
            emitted += 1;
            other = next[other];
        }

        let before = previous[vertex];
        let after = next[vertex];
        if before != 0 {
            next[before] = after;
        }
        if after == 0 {
            tail = before;
        } else {
            previous[after] = before;
        }
        active[vertex] = false;
        previous[vertex] = 0;
        next[vertex] = 0;
    }

    if emitted != geometry.m_declared {
        return Err(SosaError::Input(format!(
            "circle representation implies {emitted} edges, but DIMACS declares {}",
            geometry.m_declared
        )));
    }

    Ok(emitted)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn visits_circle_crossings_once() {
        let geometry = DimacsCircleGeometry {
            n: 3,
            m_declared: 3,
            chord_endpoint_order: vec![1, 2, 3, 1, 2, 3],
        };
        let mut edges = Vec::new();

        let count = visit_circle_crossing_edges(&geometry, |u, v| {
            edges.push((u, v));
            Ok(())
        })
        .unwrap();

        assert_eq!(count, 3);
        assert_eq!(edges, vec![(1, 2), (1, 3), (2, 3)]);
    }

    #[test]
    fn rejects_declared_edge_mismatch() {
        let geometry = DimacsCircleGeometry {
            n: 2,
            m_declared: 1,
            chord_endpoint_order: vec![1, 1, 2, 2],
        };

        let error = visit_circle_crossing_edges(&geometry, |_u, _v| Ok(())).unwrap_err();

        assert!(error.to_string().contains("DIMACS declares 1"));
    }
}
