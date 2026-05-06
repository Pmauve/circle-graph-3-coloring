use std::fmt;

#[derive(Debug)]
pub enum SosaError {
    Input(String),
    Internal(String),
    NotImplemented(String),
}

impl fmt::Display for SosaError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            SosaError::Input(message) => write!(formatter, "{message}"),
            SosaError::Internal(message) => write!(formatter, "{message}"),
            SosaError::NotImplemented(message) => write!(formatter, "{message}"),
        }
    }
}

impl std::error::Error for SosaError {}

impl From<std::io::Error> for SosaError {
    fn from(error: std::io::Error) -> Self {
        SosaError::Input(error.to_string())
    }
}
