pub mod bitset;
pub mod colors;
pub mod dimacs_circle;
pub mod dimacs_edge;
pub mod error;
pub mod instance;
pub mod instance_check;
pub mod partition;

pub use dimacs_circle::{parse_dimacs_circle, read_dimacs_circle, DimacsCircle};
pub use error::SosaError;
pub use instance::CircleInstance;
