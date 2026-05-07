use std::env;
use std::path::PathBuf;

use circle_core::error::SosaError;
use circle_core::instance_check::{
    inspect_dimacs_circle_file, validate_dimacs_circle_file, InstanceSummary,
};

fn main() {
    let exit_code = match run() {
        Ok(output) => {
            println!("{output}");
            0
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

fn run() -> Result<String, SosaError> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.iter().any(|arg| arg == "--help" || arg == "-h") {
        return Ok(help().to_string());
    }
    if args.len() != 3 || args[0] != "instance" {
        return Err(SosaError::Input(
            "usage: three_col_native instance <inspect|validate> <instance.col>".to_string(),
        ));
    }

    let path = PathBuf::from(&args[2]);
    let summary = match args[1].as_str() {
        "inspect" => inspect_dimacs_circle_file(&path)?,
        "validate" => validate_dimacs_circle_file(&path)?,
        command => {
            return Err(SosaError::Input(format!(
                "unknown instance command {command:?}; expected inspect or validate"
            )));
        }
    };
    Ok(summary_json(&summary))
}

fn help() -> &'static str {
    "usage: three_col_native instance <inspect|validate> <instance.col>"
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
}
