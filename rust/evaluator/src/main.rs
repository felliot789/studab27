use std::io::{self, Read, Write};
use std::process::ExitCode;

const MAX_INPUT_BYTES: u64 = 32 * 1024 * 1024;

fn run() -> Result<(), ()> {
    let mut input = Vec::new();
    io::stdin()
        .lock()
        .take(MAX_INPUT_BYTES + 1)
        .read_to_end(&mut input)
        .map_err(|_| ())?;
    if input.len() as u64 > MAX_INPUT_BYTES {
        return Err(());
    }
    // Complete validation and serialization before writing anything to stdout.
    let output = studab27_evaluator::evaluate_json(&input).map_err(|_| ())?;
    io::stdout().lock().write_all(&output).map_err(|_| ())
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(()) => {
            eprintln!("Evaluation failed: invalid input or I/O error.");
            ExitCode::FAILURE
        }
    }
}
