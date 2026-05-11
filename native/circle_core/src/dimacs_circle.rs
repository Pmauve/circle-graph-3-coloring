use std::fs;
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;

use crate::error::SosaError;

#[derive(Debug, Clone, Eq, PartialEq)]
pub struct DimacsCircle {
    pub n: usize,
    pub m_declared: usize,
    pub chord_endpoint_order: Vec<u32>,
    pub edges: Vec<(u32, u32)>,
}

#[derive(Debug, Clone, Eq, PartialEq)]
pub struct DimacsCircleGeometry {
    pub n: usize,
    pub m_declared: usize,
    pub chord_endpoint_order: Vec<u32>,
}

pub fn read_dimacs_circle(path: &Path) -> Result<DimacsCircle, SosaError> {
    let text = fs::read_to_string(path)?;
    parse_dimacs_circle(&text)
}

pub fn read_dimacs_circle_geometry_skip_edges(
    path: &Path,
) -> Result<DimacsCircleGeometry, SosaError> {
    let file = File::open(path)?;
    parse_dimacs_circle_geometry_skip_edges(BufReader::new(file))
}

fn parse_dimacs_circle_geometry_skip_edges<R: BufRead>(
    reader: R,
) -> Result<DimacsCircleGeometry, SosaError> {
    let mut n: Option<usize> = None;
    let mut m_declared: Option<usize> = None;
    let mut chord_endpoint_order = Vec::new();
    let mut in_chord_endpoint_order_block = false;
    let mut saw_chord_endpoint_order_block = false;

    for (line_index, raw_line) in reader.lines().enumerate() {
        let line_number = line_index + 1;
        let raw_line = raw_line?;
        let line = raw_line.trim().trim_start_matches('\u{feff}');
        if line.is_empty() {
            continue;
        }
        let parts: Vec<&str> = line.split_whitespace().collect();
        match parts[0] {
            "c" => match chord_endpoint_order_action(&parts[1..]) {
                Some("START") => {
                    if in_chord_endpoint_order_block {
                        return input_error(format!(
                            "nested chord endpoint order block at line {line_number}"
                        ));
                    }
                    if saw_chord_endpoint_order_block {
                        return input_error(format!(
                            "duplicate chord endpoint order block at line {line_number}"
                        ));
                    }
                    in_chord_endpoint_order_block = true;
                    saw_chord_endpoint_order_block = true;
                }
                Some("END") => {
                    if !in_chord_endpoint_order_block {
                        return input_error(format!(
                            "chord endpoint order END without START at line {line_number}"
                        ));
                    }
                    in_chord_endpoint_order_block = false;
                }
                Some(action) if in_chord_endpoint_order_block => {
                    return input_error(format!(
                        "unsupported chord endpoint order directive {action:?} at line {line_number}"
                    ));
                }
                _ if in_chord_endpoint_order_block => {
                    for token in &parts[1..] {
                        chord_endpoint_order.push(parse_positive_u32(token, line_number)?);
                    }
                }
                _ => {}
            },
            "p" => {
                if parts.len() != 4
                    || (parts[1] != "edge" && parts[1] != "col" && parts[1] != "circle")
                {
                    return input_error(format!(
                        "unsupported DIMACS problem line at line {line_number}: {line}"
                    ));
                }
                if n.is_some() {
                    return input_error(format!(
                        "duplicate DIMACS problem line at line {line_number}"
                    ));
                }
                n = Some(parse_usize(parts[2], line_number, "vertex count")?);
                m_declared = Some(parse_usize(parts[3], line_number, "edge count")?);
                if saw_chord_endpoint_order_block && !in_chord_endpoint_order_block {
                    break;
                }
            }
            "e" => {}
            _ => {
                return input_error(format!(
                    "unsupported DIMACS line at line {line_number}: {line}"
                ));
            }
        }
    }

    if in_chord_endpoint_order_block {
        return input_error("chord endpoint order block is missing END".to_string());
    }
    let n =
        n.ok_or_else(|| SosaError::Input("DIMACS file is missing a problem line".to_string()))?;
    let m_declared = m_declared.expect("m_declared must be present when n is present");
    if !saw_chord_endpoint_order_block {
        return input_error("DIMACS file is missing a chord endpoint order block".to_string());
    }
    validate_vertex_ranges(n, &[], &chord_endpoint_order)?;
    validate_chord_endpoint_order(n, &chord_endpoint_order)?;

    Ok(DimacsCircleGeometry {
        n,
        m_declared,
        chord_endpoint_order,
    })
}

pub fn parse_dimacs_circle(text: &str) -> Result<DimacsCircle, SosaError> {
    let mut n: Option<usize> = None;
    let mut m_declared: Option<usize> = None;
    let mut edges = Vec::new();
    let mut chord_endpoint_order = Vec::new();
    let mut in_chord_endpoint_order_block = false;
    let mut saw_chord_endpoint_order_block = false;

    for (line_index, raw_line) in text.lines().enumerate() {
        let line_number = line_index + 1;
        let line = raw_line.trim().trim_start_matches('\u{feff}');
        if line.is_empty() {
            continue;
        }
        let parts: Vec<&str> = line.split_whitespace().collect();
        match parts[0] {
            "c" => match chord_endpoint_order_action(&parts[1..]) {
                Some("START") => {
                    if in_chord_endpoint_order_block {
                        return input_error(format!(
                            "nested chord endpoint order block at line {line_number}"
                        ));
                    }
                    if saw_chord_endpoint_order_block {
                        return input_error(format!(
                            "duplicate chord endpoint order block at line {line_number}"
                        ));
                    }
                    in_chord_endpoint_order_block = true;
                    saw_chord_endpoint_order_block = true;
                }
                Some("END") => {
                    if !in_chord_endpoint_order_block {
                        return input_error(format!(
                            "chord endpoint order END without START at line {line_number}"
                        ));
                    }
                    in_chord_endpoint_order_block = false;
                }
                Some(action) if in_chord_endpoint_order_block => {
                    return input_error(format!(
                            "unsupported chord endpoint order directive {action:?} at line {line_number}"
                        ));
                }
                _ if in_chord_endpoint_order_block => {
                    for token in &parts[1..] {
                        chord_endpoint_order.push(parse_positive_u32(token, line_number)?);
                    }
                }
                _ => {}
            },
            "p" => {
                if parts.len() != 4 || (parts[1] != "edge" && parts[1] != "col") {
                    return input_error(format!(
                        "unsupported DIMACS problem line at line {line_number}: {line}"
                    ));
                }
                if n.is_some() {
                    return input_error(format!(
                        "duplicate DIMACS problem line at line {line_number}"
                    ));
                }
                n = Some(parse_usize(parts[2], line_number, "vertex count")?);
                m_declared = Some(parse_usize(parts[3], line_number, "edge count")?);
            }
            "e" => {
                if parts.len() != 3 {
                    return input_error(format!(
                        "malformed edge line at line {line_number}: {line}"
                    ));
                }
                edges.push((
                    parse_positive_u32(parts[1], line_number)?,
                    parse_positive_u32(parts[2], line_number)?,
                ));
            }
            _ => {
                return input_error(format!(
                    "unsupported DIMACS line at line {line_number}: {line}"
                ));
            }
        }
    }

    if in_chord_endpoint_order_block {
        return input_error("chord endpoint order block is missing END".to_string());
    }
    let n =
        n.ok_or_else(|| SosaError::Input("DIMACS file is missing a problem line".to_string()))?;
    let m_declared = m_declared.expect("m_declared must be present when n is present");
    if !saw_chord_endpoint_order_block {
        return input_error("DIMACS file is missing a chord endpoint order block".to_string());
    }
    if edges.len() != m_declared {
        return input_error(format!(
            "problem line declares {m_declared} edge(s), but {} were read",
            edges.len()
        ));
    }
    validate_vertex_ranges(n, &edges, &chord_endpoint_order)?;
    validate_chord_endpoint_order(n, &chord_endpoint_order)?;

    Ok(DimacsCircle {
        n,
        m_declared,
        chord_endpoint_order,
        edges,
    })
}

fn chord_endpoint_order_action(parts: &[&str]) -> Option<&'static str> {
    if parts.len() == 4 && parts[0] == "hord" && parts[1] == "endpoint" && parts[2] == "order" {
        match parts[3] {
            "START" => Some("START"),
            "END" => Some("END"),
            _ => Some("UNKNOWN"),
        }
    } else {
        None
    }
}

fn parse_usize(token: &str, line_number: usize, name: &str) -> Result<usize, SosaError> {
    token
        .parse::<usize>()
        .map_err(|_| SosaError::Input(format!("invalid {name} {token:?} at line {line_number}")))
}

fn parse_positive_u32(token: &str, line_number: usize) -> Result<u32, SosaError> {
    let value = token.parse::<u32>().map_err(|_| {
        SosaError::Input(format!(
            "invalid positive integer {token:?} at line {line_number}"
        ))
    })?;
    if value == 0 {
        return input_error(format!("vertex id 0 out of range at line {line_number}"));
    }
    Ok(value)
}

fn validate_vertex_ranges(
    n: usize,
    edges: &[(u32, u32)],
    chord_endpoint_order: &[u32],
) -> Result<(), SosaError> {
    let n_u32 = u32::try_from(n)
        .map_err(|_| SosaError::Input(format!("vertex count {n} does not fit into u32")))?;
    for &(u, v) in edges {
        if u > n_u32 {
            return input_error(format!("edge vertex id {u} out of range 1..{n}"));
        }
        if v > n_u32 {
            return input_error(format!("edge vertex id {v} out of range 1..{n}"));
        }
    }
    for &vertex in chord_endpoint_order {
        if vertex > n_u32 {
            return input_error(format!("circle vertex id {vertex} out of range 1..{n}"));
        }
    }
    Ok(())
}

fn validate_chord_endpoint_order(n: usize, chord_endpoint_order: &[u32]) -> Result<(), SosaError> {
    let expected_len = 2 * n;
    if chord_endpoint_order.len() != expected_len {
        return input_error(format!(
            "chord endpoint order has {} endpoint(s), expected {expected_len}",
            chord_endpoint_order.len()
        ));
    }
    let mut counts = vec![0usize; n];
    for &vertex in chord_endpoint_order {
        counts[(vertex - 1) as usize] += 1;
    }
    for (index, count) in counts.iter().copied().enumerate() {
        if count != 2 {
            return input_error(format!(
                "vertex {} appears {count} time(s) in chord endpoint order, expected 2",
                index + 1
            ));
        }
    }
    Ok(())
}

fn input_error<T>(message: String) -> Result<T, SosaError> {
    Err(SosaError::Input(message))
}

#[cfg(test)]
mod tests {
    use super::*;

    const TRIANGLE: &str = "\
c hord endpoint order START
c 1 2 3 1 2 3
c hord endpoint order END
p edge 3 3
e 1 2
e 1 3
e 2 3
";

    #[test]
    fn parses_valid_triangle() {
        let parsed = parse_dimacs_circle(TRIANGLE).unwrap();

        assert_eq!(parsed.n, 3);
        assert_eq!(parsed.m_declared, 3);
        assert_eq!(parsed.chord_endpoint_order, vec![1, 2, 3, 1, 2, 3]);
        assert_eq!(parsed.edges, vec![(1, 2), (1, 3), (2, 3)]);
    }

    #[test]
    fn parses_valid_edgeless_graph() {
        let parsed = parse_dimacs_circle(
            "\
c hord endpoint order START
c 1 1 2 2
c hord endpoint order END
p edge 2 0
",
        )
        .unwrap();

        assert_eq!(parsed.n, 2);
        assert!(parsed.edges.is_empty());
    }

    #[test]
    fn rejects_missing_problem_line() {
        assert!(parse_dimacs_circle(
            "c hord endpoint order START\nc 1 1\nc hord endpoint order END\n"
        )
        .unwrap_err()
        .to_string()
        .contains("problem line"));
    }

    #[test]
    fn rejects_missing_chord_endpoint_order_block() {
        assert!(parse_dimacs_circle("p edge 1 0\n")
            .unwrap_err()
            .to_string()
            .contains("chord endpoint order"));
    }

    #[test]
    fn rejects_duplicate_chord_endpoint_order_block() {
        let error = parse_dimacs_circle(
            "\
c hord endpoint order START
c 1 1
c hord endpoint order END
c hord endpoint order START
c 1 1
c hord endpoint order END
p edge 1 0
",
        )
        .unwrap_err();

        assert!(error.to_string().contains("duplicate"));
    }

    #[test]
    fn rejects_malformed_problem_line() {
        assert!(parse_dimacs_circle("p bad 1 0\n")
            .unwrap_err()
            .to_string()
            .contains("problem line"));
    }

    #[test]
    fn rejects_malformed_edge_line() {
        assert!(parse_dimacs_circle(
            "\
c hord endpoint order START
c 1 1
c hord endpoint order END
p edge 1 1
e 1
",
        )
        .unwrap_err()
        .to_string()
        .contains("malformed edge"));
    }

    #[test]
    fn rejects_vertex_out_of_range() {
        assert!(parse_dimacs_circle(
            "\
c hord endpoint order START
c 1 1
c hord endpoint order END
p edge 1 1
e 1 2
",
        )
        .unwrap_err()
        .to_string()
        .contains("out of range"));
    }

    #[test]
    fn rejects_wrong_chord_endpoint_order_length() {
        assert!(parse_dimacs_circle(
            "\
c hord endpoint order START
c 1
c hord endpoint order END
p edge 1 0
",
        )
        .unwrap_err()
        .to_string()
        .contains("endpoint"));
    }

    #[test]
    fn rejects_wrong_endpoint_multiplicity() {
        assert!(parse_dimacs_circle(
            "\
c hord endpoint order START
c 1 1 1 2
c hord endpoint order END
p edge 2 0
",
        )
        .unwrap_err()
        .to_string()
        .contains("appears"));
    }

    #[test]
    fn rejects_declared_edge_count_mismatch() {
        assert!(parse_dimacs_circle(
            "\
c hord endpoint order START
c 1 1
c hord endpoint order END
p edge 1 1
",
        )
        .unwrap_err()
        .to_string()
        .contains("declares"));
    }

    #[test]
    fn accepts_utf8_bom_on_first_line() {
        let parsed = parse_dimacs_circle(
            "\u{feff}c hord endpoint order START
c 1 1
c hord endpoint order END
p edge 1 0
",
        )
        .unwrap();

        assert_eq!(parsed.n, 1);
    }
}
