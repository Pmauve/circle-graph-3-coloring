use std::env;
use std::fs::File;
use std::io::{BufWriter, Write};
use std::path::Path;
use std::path::PathBuf;

use circle_core::crossing_edges::visit_circle_crossing_edges;
use circle_core::dimacs_circle::read_dimacs_circle_geometry_skip_edges;
use circle_core::error::SosaError;
use circle_core::generation::{
    sequence_output_path, CircleGraphBuilder, GeneratedSummary, GenerationConfig, GenerationFamily,
};
use circle_core::instance_check::{
    inspect_dimacs_circle_file, validate_dimacs_circle_file, InstanceSummary,
};
use sat_native::solver::status_to_output;
use sat_native::{solve_dimacs_edge_file, EdgeSource, SatConfig, SatStatus, SatSummary};

fn main() {
    let exit_code = match run() {
        Ok((output, exit_code)) => {
            println!("{output}");
            exit_code
        }
        Err(error) => {
            println!("{}", error_json(&error.to_string()));
            match error {
                SosaError::Input(_) => 2,
                SosaError::Internal(_) => 1,
                SosaError::NotImplemented(_) => 3,
            }
        }
    };
    std::process::exit(exit_code);
}

fn run() -> Result<(String, i32), SosaError> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.iter().any(|arg| arg == "--help" || arg == "-h") {
        return Ok((help().to_string(), 0));
    }
    let Some(command_group) = args.first() else {
        return Err(SosaError::Input(help().to_string()));
    };
    match command_group.as_str() {
        "instance" => run_instance(&args[1..]),
        "sat" => run_sat(&args[1..]),
        _ => Err(SosaError::Input(help().to_string())),
    }
}

fn run_instance(args: &[String]) -> Result<(String, i32), SosaError> {
    let Some(command) = args.first() else {
        return Err(SosaError::Input(instance_help().to_string()));
    };
    if command == "generate" {
        return run_instance_generate(&args[1..]);
    }
    if command == "generate-sequence" {
        return run_instance_generate_sequence(&args[1..]);
    }
    if command == "materialize-circle" {
        return run_instance_materialize_circle(&args[1..]);
    }
    if args.len() != 2 {
        return Err(SosaError::Input(instance_help().to_string()));
    }
    let path = PathBuf::from(&args[1]);
    let summary = match command.as_str() {
        "inspect" => inspect_dimacs_circle_file(&path)?,
        "validate" => validate_dimacs_circle_file(&path)?,
        command => {
            return Err(SosaError::Input(format!(
                "unknown instance command {command:?}; expected inspect, validate, generate, generate-sequence, or materialize-circle"
            )));
        }
    };
    Ok((summary_json(&summary), 0))
}

fn run_instance_generate(args: &[String]) -> Result<(String, i32), SosaError> {
    let options = GenerateOptions::parse(args, false)?;
    let mut builder = CircleGraphBuilder::new(options.config()?)?;
    builder.extend_to(options.n)?;
    let summary = builder.write_path(&options.output.ok_or_else(|| {
        SosaError::Input("--output is required for instance generate".to_string())
    })?)?;
    Ok((generated_summary_json(&summary), 0))
}

fn run_instance_generate_sequence(args: &[String]) -> Result<(String, i32), SosaError> {
    let options = GenerateOptions::parse(args, true)?;
    let config = options.config()?;
    let output_dir = options.output_dir.ok_or_else(|| {
        SosaError::Input("--output-dir is required for instance generate-sequence".to_string())
    })?;
    if options.step_n == 0 {
        return Err(SosaError::Input("--step-n must be at least 1".to_string()));
    }
    if options.start_n > options.stop_n {
        return Err(SosaError::Input(
            "--start-n must be less than or equal to --stop-n".to_string(),
        ));
    }

    let mut builder = CircleGraphBuilder::new(config.clone())?;
    let mut summaries = Vec::new();
    let mut n = options.start_n;
    while n <= options.stop_n {
        builder.extend_to(n)?;
        let path = sequence_output_path(
            &output_dir,
            config.family,
            n,
            config.seed,
            config.num_colors,
        );
        summaries.push(builder.write_path(&path)?);
        match n.checked_add(options.step_n) {
            Some(next) => n = next,
            None => break,
        }
    }
    Ok((generated_sequence_json(&summaries), 0))
}

fn run_instance_materialize_circle(args: &[String]) -> Result<(String, i32), SosaError> {
    if args.len() != 3 || args[1] != "--output" {
        return Err(SosaError::Input(
            "usage: three_col_native instance materialize-circle <instance.circle> --output <instance.circle.col>"
                .to_string(),
        ));
    }
    let input = PathBuf::from(&args[0]);
    let output = PathBuf::from(&args[2]);
    let geometry = read_dimacs_circle_geometry_skip_edges(&input)?;
    write_materialized_circle_col(&input, &output, &geometry)?;
    Ok((
        format!(
            "{{{},\"n\":{},\"m\":{},\"path\":{}}}",
            json_pair("status", "ok"),
            geometry.n,
            geometry.m_declared,
            json_string(&output.to_string_lossy())
        ),
        0,
    ))
}

fn write_materialized_circle_col(
    input: &Path,
    output: &Path,
    geometry: &circle_core::dimacs_circle::DimacsCircleGeometry,
) -> Result<(), SosaError> {
    if let Some(parent) = output.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let file = File::create(output)?;
    let mut writer = BufWriter::new(file);
    writeln!(writer, "c format version 1")?;
    writeln!(
        writer,
        "c instance id {}",
        input
            .file_stem()
            .and_then(|value| value.to_str())
            .unwrap_or("unknown")
    )?;
    writeln!(writer, "c source materialized-circle")?;
    writeln!(writer, "c materialized from {}", input.to_string_lossy())?;
    writeln!(writer, "c hord endpoint order START")?;
    for chunk in geometry.chord_endpoint_order.chunks(32) {
        write!(writer, "c")?;
        for vertex in chunk {
            write!(writer, " {}", vertex)?;
        }
        writeln!(writer)?;
    }
    writeln!(writer, "c hord endpoint order END")?;
    writeln!(writer, "p edge {} {}", geometry.n, geometry.m_declared)?;
    let mut edges = Vec::new();
    visit_circle_crossing_edges(geometry, |u, v| {
        let edge = if u <= v { (u, v) } else { (v, u) };
        edges.push(edge);
        Ok(())
    })?;
    edges.sort_unstable();
    for (u, v) in edges {
        writeln!(writer, "e {u} {v}")?;
    }
    Ok(())
}

#[derive(Clone, Debug)]
struct GenerateOptions {
    family: Option<GenerationFamily>,
    seed: Option<u64>,
    n: usize,
    start_n: usize,
    stop_n: usize,
    step_n: usize,
    output: Option<PathBuf>,
    output_dir: Option<PathBuf>,
    num_colors: u8,
    max_attempts_per_node: usize,
}

impl GenerateOptions {
    fn parse(args: &[String], sequence: bool) -> Result<Self, SosaError> {
        let mut options = Self {
            family: None,
            seed: None,
            n: 0,
            start_n: 0,
            stop_n: 0,
            step_n: 1,
            output: None,
            output_dir: None,
            num_colors: 3,
            max_attempts_per_node: 10_000,
        };
        let mut index = 0;
        while index < args.len() {
            match args[index].as_str() {
                "--family" => {
                    options.family = Some(GenerationFamily::parse(required_value(
                        args, index, "--family",
                    )?)?);
                    index += 2;
                }
                "--seed" => {
                    options.seed = Some(parse_u64_arg(args, index, "--seed")?);
                    index += 2;
                }
                "--n" => {
                    options.n = parse_usize_arg(args, index, "--n")?;
                    index += 2;
                }
                "--start-n" => {
                    options.start_n = parse_usize_arg(args, index, "--start-n")?;
                    index += 2;
                }
                "--stop-n" => {
                    options.stop_n = parse_usize_arg(args, index, "--stop-n")?;
                    index += 2;
                }
                "--step-n" => {
                    options.step_n = parse_usize_arg(args, index, "--step-n")?;
                    index += 2;
                }
                "--output" => {
                    options.output = Some(PathBuf::from(required_value(args, index, "--output")?));
                    index += 2;
                }
                "--output-dir" => {
                    options.output_dir =
                        Some(PathBuf::from(required_value(args, index, "--output-dir")?));
                    index += 2;
                }
                "--num-colors" => {
                    options.num_colors = parse_u8_arg(args, index, "--num-colors")?;
                    index += 2;
                }
                "--max-attempts-per-node" => {
                    options.max_attempts_per_node =
                        parse_usize_arg(args, index, "--max-attempts-per-node")?;
                    index += 2;
                }
                unknown => {
                    return Err(SosaError::Input(format!("unknown argument {unknown:?}")));
                }
            }
        }

        if sequence {
            if options.start_n == 0 || options.stop_n == 0 {
                return Err(SosaError::Input(
                    "--start-n and --stop-n are required for instance generate-sequence"
                        .to_string(),
                ));
            }
        } else if options.n == 0 {
            return Err(SosaError::Input(
                "--n is required for instance generate".to_string(),
            ));
        }
        Ok(options)
    }

    fn config(&self) -> Result<GenerationConfig, SosaError> {
        Ok(GenerationConfig {
            family: self
                .family
                .ok_or_else(|| SosaError::Input("--family is required".to_string()))?,
            seed: self
                .seed
                .ok_or_else(|| SosaError::Input("--seed is required".to_string()))?,
            num_colors: self.num_colors,
            max_attempts_per_node: self.max_attempts_per_node,
        })
    }
}

fn run_sat(args: &[String]) -> Result<(String, i32), SosaError> {
    if args.len() < 2 || args[0] != "solve" {
        return Err(SosaError::Input(
            "usage: three_col_native sat solve <instance.col> [--backend cadical-rustsat|kissat-rustsat] [--edge-source listed_edges|circle_crossings] [--timeout-s N]"
                .to_string(),
        ));
    }

    let path = PathBuf::from(&args[1]);
    let mut config = SatConfig {
        backend: "cadical-rustsat".to_string(),
        timeout_s: None,
        edge_source: EdgeSource::ListedEdges,
    };
    let mut index = 2;
    while index < args.len() {
        match args[index].as_str() {
            "--backend" => {
                config.backend = required_value(args, index, "--backend")?.to_string();
                index += 2;
            }
            "--timeout-s" => {
                let raw_value = required_value(args, index, "--timeout-s")?;
                config.timeout_s = Some(raw_value.parse::<u64>().map_err(|_| {
                    SosaError::Input(format!("invalid --timeout-s value {raw_value:?}"))
                })?);
                index += 2;
            }
            "--edge-source" => {
                config.edge_source =
                    EdgeSource::parse(required_value(args, index, "--edge-source")?)?;
                index += 2;
            }
            unknown => {
                return Err(SosaError::Input(format!("unknown argument {unknown:?}")));
            }
        }
    }

    let summary = solve_dimacs_edge_file(&path, config)?;
    let exit_code = match summary.status {
        SatStatus::Colorable | SatStatus::NotColorable => 0,
        SatStatus::Unknown => 3,
    };
    Ok((sat_summary_text(&summary), exit_code))
}

fn required_value<'a>(args: &'a [String], index: usize, flag: &str) -> Result<&'a str, SosaError> {
    args.get(index + 1)
        .map(String::as_str)
        .ok_or_else(|| SosaError::Input(format!("{flag} requires a value")))
}

fn parse_usize_arg(args: &[String], index: usize, flag: &str) -> Result<usize, SosaError> {
    let value = required_value(args, index, flag)?;
    value
        .parse::<usize>()
        .map_err(|_| SosaError::Input(format!("invalid {flag} value {value:?}")))
}

fn parse_u64_arg(args: &[String], index: usize, flag: &str) -> Result<u64, SosaError> {
    let value = required_value(args, index, flag)?;
    value
        .parse::<u64>()
        .map_err(|_| SosaError::Input(format!("invalid {flag} value {value:?}")))
}

fn parse_u8_arg(args: &[String], index: usize, flag: &str) -> Result<u8, SosaError> {
    let value = required_value(args, index, flag)?;
    value
        .parse::<u8>()
        .map_err(|_| SosaError::Input(format!("invalid {flag} value {value:?}")))
}

fn help() -> &'static str {
    "usage: three_col_native <instance|sat> ..."
}

fn instance_help() -> &'static str {
    "usage: three_col_native instance <inspect|validate> <instance.col> | instance materialize-circle <instance.circle> --output PATH | instance generate --family F --n N --seed S --output PATH | instance generate-sequence --family F --start-n N --stop-n N --step-n N --seed S --output-dir DIR"
}

fn sat_summary_text(summary: &SatSummary) -> String {
    let mut fields = vec![
        json_pair("status", "ok"),
        json_pair("solver_status", status_to_output(summary.status)),
        json_pair("edge_source", summary.edge_source.as_str()),
        format!("\"load_prepare_time_s\":{:.6}", summary.load_prepare_time_s),
        format!("\"total_native_time_s\":{:.6}", summary.total_native_time_s),
    ];
    if let Some(load_time_s) = summary.load_time_s {
        fields.push(format!("\"load_time_s\":{load_time_s:.6}"));
    }
    if let Some(prepare_time_s) = summary.prepare_time_s {
        fields.push(format!("\"prepare_time_s\":{prepare_time_s:.6}"));
    }
    if let Some(solve_time_s) = summary.solve_time_s {
        fields.push(format!("\"solve_time_s\":{solve_time_s:.6}"));
    }
    if let Some(error) = &summary.error {
        fields.push(format!("\"error\":{}", json_string(error)));
    }
    format!("{{{}}}", fields.join(","))
}

fn summary_json(summary: &InstanceSummary) -> String {
    let mut fields = vec![json_pair("status", "ok")];
    if let Some(instance_id) = &summary.instance_id {
        fields.push(json_pair("instance_id", instance_id));
    }
    if let Some(family) = &summary.family {
        fields.push(json_pair("family", family));
    }
    fields.push(format!("\"n\":{}", summary.n));
    fields.push(format!("\"m\":{}", summary.m));
    if let Some(num_colors) = summary.num_colors {
        fields.push(format!("\"num_colors\":{num_colors}"));
    }
    format!("{{{}}}", fields.join(","))
}

fn generated_summary_json(summary: &GeneratedSummary) -> String {
    format!(
        "{{{},{},{},\"n\":{},\"m\":{},\"num_colors\":{},\"path\":{}}}",
        json_pair("status", "ok"),
        json_pair("instance_id", &summary.instance_id),
        json_pair("family", &summary.family),
        summary.n,
        summary.m,
        summary.num_colors,
        json_string(&summary.path.to_string_lossy())
    )
}

fn generated_sequence_json(summaries: &[GeneratedSummary]) -> String {
    let paths = summaries
        .iter()
        .map(|summary| json_string(&summary.path.to_string_lossy()))
        .collect::<Vec<_>>()
        .join(",");
    let count = summaries.len();
    format!(
        "{{{},\"count\":{},\"paths\":[{}]}}",
        json_pair("status", "ok"),
        count,
        paths
    )
}

fn error_json(message: &str) -> String {
    format!(
        "{{{},\"error\":{}}}",
        json_pair("status", "error"),
        json_string(message)
    )
}

fn json_pair(key: &str, value: &str) -> String {
    format!("{}:{}", json_string(key), json_string(value))
}

fn json_string(value: &str) -> String {
    let mut escaped = String::with_capacity(value.len() + 2);
    escaped.push('"');
    for character in value.chars() {
        match character {
            '"' => escaped.push_str("\\\""),
            '\\' => escaped.push_str("\\\\"),
            '\n' => escaped.push_str("\\n"),
            '\r' => escaped.push_str("\\r"),
            '\t' => escaped.push_str("\\t"),
            '\u{08}' => escaped.push_str("\\b"),
            '\u{0c}' => escaped.push_str("\\f"),
            character if character.is_control() => {
                escaped.push_str(&format!("\\u{:04x}", character as u32));
            }
            character => escaped.push(character),
        }
    }
    escaped.push('"');
    escaped
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn escapes_json_strings() {
        assert_eq!(json_string("a\"b\\c\n"), "\"a\\\"b\\\\c\\n\"");
    }

    #[test]
    fn renders_summary_without_optional_fields() {
        let summary = InstanceSummary {
            instance_id: None,
            family: None,
            n: 2,
            m: 1,
            num_colors: None,
        };

        assert_eq!(
            summary_json(&summary),
            "{\"status\":\"ok\",\"n\":2,\"m\":1}"
        );
    }

    #[test]
    fn renders_sat_summary_text() {
        let summary = SatSummary {
            status: SatStatus::Colorable,
            edge_source: EdgeSource::CircleCrossings,
            load_prepare_time_s: 0.3,
            load_time_s: Some(0.1),
            prepare_time_s: Some(0.2),
            solve_time_s: Some(0.3),
            total_native_time_s: 0.6,
            error: None,
        };

        assert_eq!(
            sat_summary_text(&summary),
            "{\"status\":\"ok\",\"solver_status\":\"COLORABLE\",\"edge_source\":\"circle_crossings\",\"load_prepare_time_s\":0.300000,\"total_native_time_s\":0.600000,\"load_time_s\":0.100000,\"prepare_time_s\":0.200000,\"solve_time_s\":0.300000}"
        );
    }
}
