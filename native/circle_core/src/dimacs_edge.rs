use std::io::BufRead;

use crate::error::SosaError;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct DimacsProblem {
    pub n: usize,
    pub m: usize,
}

pub fn stream_dimacs_edges<R, P, E>(
    reader: R,
    on_problem: P,
    mut on_edge: E,
) -> Result<(), SosaError>
where
    R: BufRead,
    P: FnOnce(DimacsProblem) -> Result<(), SosaError>,
    E: FnMut(usize, usize) -> Result<(), SosaError>,
{
    let mut problem: Option<DimacsProblem> = None;
    let mut on_problem = Some(on_problem);
    let mut edge_count = 0usize;

    for (line_index, raw_line) in reader.lines().enumerate() {
        let line_number = line_index + 1;
        let raw_line = raw_line?;
        let line = raw_line.trim().trim_start_matches('\u{feff}');
        if line.is_empty() {
            continue;
        }
        let parts: Vec<&str> = line.split_whitespace().collect();
        match parts[0] {
            "c" => {}
            "p" => {
                if parts.len() != 4 || (parts[1] != "edge" && parts[1] != "col") {
                    return input_error(format!(
                        "unsupported DIMACS problem line at line {line_number}: {line}"
                    ));
                }
                if problem.is_some() {
                    return input_error(format!(
                        "duplicate DIMACS problem line at line {line_number}"
                    ));
                }
                let parsed = DimacsProblem {
                    n: parse_usize(parts[2], line_number, "vertex count")?,
                    m: parse_usize(parts[3], line_number, "edge count")?,
                };
                let callback = on_problem.take().expect("problem callback must be present");
                callback(parsed)?;
                problem = Some(parsed);
            }
            "e" => {
                let problem = problem.ok_or_else(|| {
                    SosaError::Input(format!(
                        "edge line before problem line at line {line_number}"
                    ))
                })?;
                if parts.len() != 3 {
                    return input_error(format!(
                        "malformed edge line at line {line_number}: {line}"
                    ));
                }
                let u = parse_positive_usize(parts[1], line_number)?;
                let v = parse_positive_usize(parts[2], line_number)?;
                if u > problem.n {
                    return input_error(format!(
                        "edge vertex id {u} out of range 1..{}",
                        problem.n
                    ));
                }
                if v > problem.n {
                    return input_error(format!(
                        "edge vertex id {v} out of range 1..{}",
                        problem.n
                    ));
                }
                if u == v {
                    return input_error(format!("self-loop on vertex {u} at line {line_number}"));
                }
                on_edge(u, v)?;
                edge_count += 1;
            }
            _ => {
                return input_error(format!(
                    "unsupported DIMACS line at line {line_number}: {line}"
                ));
            }
        }
    }

    let problem = problem
        .ok_or_else(|| SosaError::Input("DIMACS file is missing a problem line".to_string()))?;
    if edge_count != problem.m {
        return input_error(format!(
            "problem line declares {} edge(s), but {edge_count} were read",
            problem.m
        ));
    }
    Ok(())
}

fn parse_usize(token: &str, line_number: usize, name: &str) -> Result<usize, SosaError> {
    token
        .parse::<usize>()
        .map_err(|_| SosaError::Input(format!("invalid {name} {token:?} at line {line_number}")))
}

fn parse_positive_usize(token: &str, line_number: usize) -> Result<usize, SosaError> {
    let value = parse_usize(token, line_number, "positive integer")?;
    if value == 0 {
        return input_error(format!("vertex id 0 out of range at line {line_number}"));
    }
    Ok(value)
}

fn input_error<T>(message: String) -> Result<T, SosaError> {
    Err(SosaError::Input(message))
}

#[cfg(test)]
mod tests {
    use std::io::Cursor;

    use super::*;

    #[test]
    fn streams_problem_and_edges_while_ignoring_circle_comments() {
        let mut problem = None;
        let mut edges = Vec::new();

        stream_dimacs_edges(
            Cursor::new(
                "\
c format version 1
c ircle representation START
c 1 2 1 2
c ircle representation END
p edge 2 1
e 1 2
",
            ),
            |parsed| {
                problem = Some(parsed);
                Ok(())
            },
            |u, v| {
                edges.push((u, v));
                Ok(())
            },
        )
        .unwrap();

        assert_eq!(problem, Some(DimacsProblem { n: 2, m: 1 }));
        assert_eq!(edges, vec![(1, 2)]);
    }

    #[test]
    fn accepts_col_problem_line() {
        let mut problem = None;

        stream_dimacs_edges(
            Cursor::new("p col 1 0\n"),
            |parsed| {
                problem = Some(parsed);
                Ok(())
            },
            |_u, _v| Ok(()),
        )
        .unwrap();

        assert_eq!(problem, Some(DimacsProblem { n: 1, m: 0 }));
    }

    #[test]
    fn rejects_edge_before_problem_line() {
        assert!(
            stream_dimacs_edges(Cursor::new("e 1 2\n"), |_| Ok(()), |_u, _v| Ok(()))
                .unwrap_err()
                .to_string()
                .contains("before problem")
        );
    }

    #[test]
    fn rejects_duplicate_problem_line() {
        assert!(stream_dimacs_edges(
            Cursor::new("p edge 1 0\np edge 1 0\n"),
            |_| Ok(()),
            |_u, _v| Ok(())
        )
        .unwrap_err()
        .to_string()
        .contains("duplicate"));
    }

    #[test]
    fn rejects_out_of_range_edge() {
        assert!(stream_dimacs_edges(
            Cursor::new("p edge 1 1\ne 1 2\n"),
            |_| Ok(()),
            |_u, _v| Ok(())
        )
        .unwrap_err()
        .to_string()
        .contains("out of range"));
    }

    #[test]
    fn rejects_self_loop() {
        assert!(stream_dimacs_edges(
            Cursor::new("p edge 1 1\ne 1 1\n"),
            |_| Ok(()),
            |_u, _v| Ok(())
        )
        .unwrap_err()
        .to_string()
        .contains("self-loop"));
    }

    #[test]
    fn rejects_edge_count_mismatch() {
        assert!(
            stream_dimacs_edges(Cursor::new("p edge 1 1\n"), |_| Ok(()), |_u, _v| Ok(()))
                .unwrap_err()
                .to_string()
                .contains("declares")
        );
    }
}
