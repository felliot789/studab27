# Rust scenario evaluator trial

The first Rust slice implements the read-only budget, curriculum, graduation and advisory SAT evaluator. It uses the existing JSON input/output contract and preserves gate reasons, evidence boundaries and `UNKNOWN` results. It does not choose scholarships, verify eligibility, save a scenario or change application progress.

## Scope

- [Rust evaluator](../rust/evaluator/src/lib.rs): typed inputs and deterministic planning gates.
- [CLI](../rust/evaluator/src/main.rs): one JSON request on stdin and one JSON array on stdout; bounded input and generic failure messages.
- [Server bridge](../src/lib/storage.ts): `evaluateScenarios()` selects the optional executable for POST `/api/schola` with `action: "simulate"`.
- [Parity and benchmark check](../scripts/check-rust-evaluator.py): public examples and fictional boundary cases compared with [the Python reference](../schola/evaluator.py).

The dashboard's combined derivation, workspace persistence, Schola jobs, source fetching and recovery still use Python. The frontend and SQLite schema are unchanged. This trial retains a process boundary; it evaluates a Rust implementation before introducing a persistent backend service.

Compatibility targets the application's validated payloads: monthly caps up to 100, monthly cost components up to 1000, and the existing scenario SAT bounds. Decimal strings and small finite JSON fractions retain exact threshold arithmetic. Arbitrarily large JSON integer literals beyond Rust's integer range are outside this trial's supported interface; malformed input types fail rather than being coerced.

## Build and verify

Rust and Cargo are required for the trial only. The regular `npm run check` continues to work without them.

```sh
npm run check:rust
python3 scripts/check-rust-evaluator.py --benchmark --samples 40
```

`check:rust` checks formatting, runs Rust tests, builds the locked release executable and checks output parity. Keep [Cargo.lock](../rust/evaluator/Cargo.lock) versioned. Build output under `rust/evaluator/target/` stays ignored.

The benchmark launches each implementation as a separate process with identical serialized fixture input, warms them up and alternates order. It includes startup, JSON parsing, calculation and output. It measures this CLI workload only; it does not establish a phone, full-dashboard, database or Schola research speedup.

### Recorded comparison — 2026-11-19

On the same local Linux host, a Rust 1.98.0 release build and the system Python each received the identical 456,950-byte public fixture. Three warmups preceded 40 fresh-process samples per implementation, with alternating order and output checks on every run.

| Implementation | Median | p95 |
| --- | --- | --- |
| Python reference | 24.817 ms | 25.403 ms |
| Rust release | 2.770 ms | 2.861 ms |

Rust took about one ninth of the time for this process-level workload. Compatibility checks matched 89 scenarios / 290 route evaluations, covering every gate/SAT/overall status and all 68 public routes. Another 23 invalid inputs failed safely, including nonfinite numbers, oversized input and forged numeric objects. These fixtures do not prove equivalence for arbitrary Python inputs or measure physical-phone responsiveness.

## Opt-in web verification

Leave `STUDAB27_EVALUATOR_BIN` unset for the existing Python scenario backend. An absolute path to the built Rust executable selects it at server runtime. A selected executable that is missing, invalid or fails returns an error; it never silently retries through Python. Do not put private configuration or records in this executable path.

Run the following **inside a separate staging checkout with its own validated production build**:

```sh
STUDAB27_EVALUATOR_BIN="$PWD/rust/evaluator/target/release/studab27-evaluator" python3 scripts/check-app.py
```

The HTTP check creates a temporary fictional workspace and a free loopback port. It compares the complete scenario result against Python, checks that workspace records are unchanged, and exercises the existing host, origin and session boundaries. Run the same check with the variable unset to cover the default backend.

Do not build over the `.next` directory served by a running production service. These checks require no production configuration change, worker restart or model request. Enabling the Rust evaluator on the live service is a separate deployment step.

## Next decision

Review compatibility and measured costs before expanding the trial. A successful evaluator port does not establish parity for database transactions, source retrieval or durable research jobs. Any wider migration needs its own contracts and validation.
