use std::env;
use std::path::PathBuf;

use circle_core::error::SosaError;
use circle_core::instance_check::{
    inspect_dimacs_circle_file, validate_dimacs_circle_file, InstanceSummary,
};
use sat_native::solver::status_to_output;
use sat_native::{solve_dimacs_edge_file, SatConfig, SatStatus, SatSummary};

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
    if args.len() != 2 {
        return Err(SosaError::Input(
            "usage: three_col_native instance <inspect|validate> <instance.col>".to_string(),
        ));
    }
    let path = PathBuf::from(&args[1]);
    let summary = match args[0].as_str() {
        "inspect" => inspect_dimacs_circle_file(&path)?,
        "validate" => validate_dimacs_circle_file(&path)?,
        command => {
            return Err(SosaError::Input(format!(
                "unknown instance command {command:?}; expected inspect or validate"
            )));
        }
    };
    Ok((summary_json(&summary), 0))
}

fn run_sat(args: &[String]) -> Result<(String, i32), SosaError> {
    if args.len() < 2 || args[0] != "solve" {
        return Err(SosaError::Input(
            "usage: three_col_native sat solve <instance.col> --solver-bin <path> [--backend dimacs-pipe] [--timeout-s N]"
                .to_string(),
        ));
    }

    let path = PathBuf::from(&args[1]);
    let mut config = SatConfig {
        backend: "dimacs-pipe".to_string(),
        solver_bin: String::new(),
        timeout_s: None,
    };
    let mut index = 2;
    while index < args.len() {
        match args[index].as_str() {
            "--backend" => {
                config.backend = required_value(args, index, "--backend")?.to_string();
                index += 2;
            }
            "--solver-bin" => {
                config.solver_bin = required_value(args, index, "--solver-bin")?.to_string();
                index += 2;
            }
            "--timeout-s" => {
                let raw_value = required_value(args, index, "--timeout-s")?;
                config.timeout_s = Some(raw_value.parse::<u64>().map_err(|_| {
                    SosaError::Input(format!("invalid --timeout-s value {raw_value:?}"))
                })?);
                index += 2;
            }
            unknown => {
                return Err(SosaError::Input(format!("unknown argument {unknown:?}")));
            }
        }
    }
    if config.solver_bin.is_empty() {
        return Err(SosaError::Input("--solver-bin is required".to_string()));
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

fn help() -> &'static str {
    "usage: three_col_native <instance|sat> ..."
}

fn sat_summary_text(summary: &SatSummary) -> String {
    let mut lines = vec![
        format!("s {}", status_to_output(summary.status)),
        format!("t parse_encode_time_s {:.6}", summary.parse_encode_time_s),
        format!("t solve_time_s {:.6}", summary.solve_time_s),
        format!("t core_time_s {:.6}", summary.core_time_s),
    ];
    if let Some(error) = &summary.error {
        lines.push(format!("e {error}"));
    }
    lines.join("\n")
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
            parse_encode_time_s: 0.1,
            solve_time_s: 0.2,
            core_time_s: 0.3,
            error: None,
        };

        assert_eq!(
            sat_summary_text(&summary),
            "s COLORABLE\nt parse_encode_time_s 0.100000\nt solve_time_s 0.200000\nt core_time_s 0.300000"
        );
    }
}
