use std::cell::RefCell;
use std::fs::File;
use std::io::{BufReader, Write};
use std::path::Path;
use std::time::Instant;

use circle_core::dimacs_edge::{stream_dimacs_edges, DimacsProblem};
use circle_core::error::SosaError;

use crate::cnf::{edge_clauses, n_clauses, n_vars, vertex_clause};

pub fn encode_dimacs_edge_file_to_writer(
    path: &Path,
    output: &mut dyn Write,
) -> Result<f64, SosaError> {
    let file = File::open(path)?;
    let reader = BufReader::new(file);
    let started_at = Instant::now();
    let output = RefCell::new(output);

    stream_dimacs_edges(
        reader,
        |problem| {
            write_header_and_vertex_clauses(problem, *output.borrow_mut())?;
            Ok(())
        },
        |u, v| {
            write_edge_clauses(u, v, *output.borrow_mut())?;
            Ok(())
        },
    )?;

    Ok(started_at.elapsed().as_secs_f64())
}

fn write_header_and_vertex_clauses(
    problem: DimacsProblem,
    output: &mut dyn Write,
) -> Result<(), SosaError> {
    writeln!(
        output,
        "p cnf {} {}",
        n_vars(problem.n),
        n_clauses(problem.n, problem.m)
    )?;
    for vertex in 1..=problem.n {
        let clause = vertex_clause(vertex);
        writeln!(output, "{} {} {} 0", clause[0], clause[1], clause[2])?;
    }
    Ok(())
}

fn write_edge_clauses(u: usize, v: usize, output: &mut dyn Write) -> Result<(), SosaError> {
    for clause in edge_clauses(u, v) {
        writeln!(output, "{} {} 0", clause[0], clause[1])?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::fs;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    use super::*;

    #[test]
    fn encodes_three_color_cnf_without_circle_validation() {
        let path = write_temp_file(
            "\
c ircle representation START
c 1 2 1 2
c ircle representation END
p edge 2 1
e 1 2
",
        );

        let mut encoded = Vec::new();
        encode_dimacs_edge_file_to_writer(&path, &mut encoded).unwrap();

        assert_eq!(
            String::from_utf8(encoded).unwrap(),
            "\
p cnf 6 5
1 2 3 0
4 5 6 0
-1 -4 0
-2 -5 0
-3 -6 0
"
        );
        let _ = fs::remove_file(path);
    }

    #[test]
    fn rejects_invalid_edge_input() {
        let path = write_temp_file("p edge 1 1\ne 1 2\n");
        let mut output = Vec::new();

        let error = encode_dimacs_edge_file_to_writer(&path, &mut output).unwrap_err();

        assert!(error.to_string().contains("out of range"));
        let _ = fs::remove_file(path);
    }

    fn write_temp_file(content: &str) -> PathBuf {
        let mut path = std::env::temp_dir();
        path.push(format!("sat-native-encode-{}.col", unique_suffix()));
        fs::write(&path, content).unwrap();
        path
    }

    fn unique_suffix() -> u128 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    }
}
