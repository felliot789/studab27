"""Check the experimental Rust CLI against Python using public and fictional data."""
import argparse
import copy
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from schola.evaluator import evaluate_all  # noqa: E402


def encode(payload):
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def public_fixture():
    public = ROOT / "data/public"
    return {
        "routes": json.loads((public / "scholarships_2027.json").read_text()),
        "overlays": json.loads((public / "overlay.example.json").read_text()),
        "profile": json.loads((public / "profile.example.json").read_text()),
    }


def synthetic_cases():
    rule = {"cycle": "2027", "program": "Example Engineering", "sourceUrl": "https://example.edu/call",
            "checkedAt": "2026-11-01", "nationalCurriculumDirectEntry": True,
            "preGraduationApplicationAllowed": True}
    base = {"routes": [{"id": "fictional-route", "satRole": "HIGH", "suggestedSatBenchmark": "1500+"}],
            "overlays": [{"routeId": "fictional-route", "estimatedFamilyGapIdrMPerMonth": "0–2",
                          "personalSatTargetNote": "", "verifiedRules": rule}],
            "profile": {"snapshot": {"expectedGraduation": "June 2027", "maxFamilyContributionIdrMPerMonth": 4}}}
    cases = []

    def add(name, *, overlay=None, rule_change=None, graduation=None, route=None, **top):
        payload = copy.deepcopy(base)
        payload["overlays"][0].update(overlay or {})
        if rule_change is not None:
            payload["overlays"][0]["verifiedRules"].update(rule_change)
        if graduation is not None:
            payload["profile"]["snapshot"]["expectedGraduation"] = graduation
        payload["routes"][0].update(route or {})
        payload.update(top)
        cases.append((name, payload))

    add("all-gates-met")
    for label, gap in [("at-cap", "2–4"), ("cross-cap", "3–5"), ("above-cap", "5–8"),
                       ("missing", None), ("unknown", "TBD"), ("ambiguous", "0 if funded, 20 otherwise"),
                       ("reversed", "6–2"), ("negative", "-2"), ("invalid-suffix", "2 M"),
                       ("comma-decimal", "2,5–4,0"), ("approximate", " ≈ 2 — 4 "),
                       ("tilde", "~ 2 - 4"), ("unicode-digits", "٢–٤"), ("numeric", 4), ("boolean", True)]:
        add("gap-" + label, overlay={"estimatedFamilyGapIdrMPerMonth": gap})
    cost = {"tuition": 12, "housing": 4, "food": 2, "insurance": .5, "other": .5, "coverage": 15, "upfront": 40}
    add("cost-at-cap", overlay={"costEstimate": cost})
    add("cost-upfront-ignored", overlay={"costEstimate": {**cost, "upfront": 10000}})
    add("cost-overcovered", overlay={"costEstimate": {**cost, "coverage": 100}}, cap=0)
    for field, value in [("housing", None), ("food", -1), ("insurance", True), ("coverage", "15")]:
        add("cost-invalid-" + field, overlay={"costEstimate": {**cost, field: value}})
    incomplete = {key: value for key, value in cost.items() if key != "housing"}
    add("cost-missing-component", overlay={"costEstimate": incomplete})
    add("cost-forged-number-object", overlay={"costEstimate": {**cost, "tuition": {"$serde_json::private::Number": "4"}}})
    for label, value in [("empty", {}), ("null", None)]:
        add("cost-" + label + "-uses-range", overlay={"costEstimate": value})
    decimal_cost = dict.fromkeys(("tuition", "housing", "food", "insurance", "other", "coverage"), 0)
    decimal_cost.update(tuition=.1, housing=.2)
    add("decimal-sum-at-cap", overlay={"costEstimate": decimal_cost}, cap=.3)
    add("decimal-sum-over-cap", overlay={"costEstimate": decimal_cost}, cap=.29999999999999993)
    add("decimal-coverage-exact-zero", overlay={"costEstimate": {**decimal_cost, "coverage": .3}}, cap=0)
    add("decimal-tiny-cost", overlay={"costEstimate": {**decimal_cost, "tuition": 1e-30, "housing": 0}}, cap=0)
    add("decimal-context-rounding", overlay={"costEstimate": {**decimal_cost, "tuition": .3, "housing": 1e-30}}, cap=.3)
    add("decimal-tiny-cap", overlay={"estimatedFamilyGapIdrMPerMonth": "0"}, cap=1e-30)
    add("explicit-null-scenario-defaults", sat=None, cap=None)

    for label, change in [("old-cycle", {"cycle": "2026"}), ("http", {"sourceUrl": "http://example.edu/call"}),
                          ("no-check-date", {"checkedAt": ""}), ("no-program", {"program": ""}),
                          ("curriculum-rejected", {"nationalCurriculumDirectEntry": False}),
                          ("curriculum-unknown", {"nationalCurriculumDirectEntry": None}),
                          ("curriculum-text-not-bool", {"nationalCurriculumDirectEntry": "true"}),
                          ("graduation-rule-unknown", {"preGraduationApplicationAllowed": None}),
                          ("graduation-no-cutoff", {"preGraduationApplicationAllowed": False})]:
        add("rule-" + label, rule_change=change)
    add("seed-claims-unverified", overlay={"verifiedRules": {}, "preGradApplyAllowed": "Yes"},
        route={"preGradApplyAllowed": "Yes"}, sat=1600)
    for label, graduation, cutoff in [
        ("month-before", "June 2027", "2027-05-31"),
        ("month-crosses", "June 2027", "2027-06-15"),
        ("month-last-day", "June 2027", "2027-06-30"),
        ("date-exact", "2027-06-30", "2027-06-30"),
        ("date-after", "2027-06-30", "2027-06-29"),
        ("leap-crosses", "February 2028", "2028-02-28"),
        ("leap-last-day", "February 2028", "2028-02-29"),
        ("nonleap-last-day", "February 2027", "2027-02-28"),
        ("compact-date", "20270630", "2027-06-30"),
        ("week-date", "2027-W26-3", "2027-06-30"),
        ("compact-week-date", "2027W263", "2027-06-30"),
        ("invalid-date", "2027-02-30", "2027-06-30"),
        ("invalid-cutoff", "June 2027", "2027-02-30"),
        ("unknown-date", "UNKNOWN", "2027-06-30"),
        ("lowercase-month", "june 2027", "2027-06-30"),
        ("abbreviated-month", "Jun 2027", "2027-06-30"),
        ("unicode-year", "June ٢٠٢٧", "2027-06-30"),
    ]:
        add("graduation-" + label, graduation=graduation,
            rule_change={"preGraduationApplicationAllowed": False, "finalDiplomaDeadline": cutoff})
    for score in (0, 1499, 1500, 1600):
        add("sat-score-" + str(score), sat=score)
    for label, target in [("lower-bound", "1300"), ("upper-bound", "1600"), ("outside-low", "1299"),
                          ("outside-high", "1601"), ("word-prefix", "x1500"), ("word-suffix", "1500x"),
                          ("underscore", "_1500"), ("five-digits", "11500"),
                          ("multiple", "1400–1500"), ("unicode-digits", "14٣٠"),
                          ("unicode-word-prefix", "é1500"), ("combining-prefix", "\u03011500"),
                          ("combining-suffix", "1500\u0301"), ("unknown", "UNKNOWN")]:
        add("sat-target-" + label, route={"suggestedSatBenchmark": target}, sat=1450)
    add("sat-overlay-target-preferred", overlay={"personalSatTargetNote": "Aim for 1400"}, sat=1450)
    add("sat-overlay-unknown-prevents-fallback", overlay={"personalSatTargetNote": "UNKNOWN"}, sat=1600)
    add("sat-low-role-without-score", route={"satRole": "LOW"})
    add("sat-low-role-with-target-score", route={"satRole": "LOW"}, sat=1500)
    add("sat-low-role-without-target", route={"satRole": "LOW", "suggestedSatBenchmark": "UNKNOWN"}, sat=1500)
    payload = copy.deepcopy(base)
    payload["overlays"] = []
    cases.append(("missing-overlay", payload))
    payload = copy.deepcopy(base)
    payload["overlays"].append({"routeId": "fictional-route", "estimatedFamilyGapIdrMPerMonth": "8"})
    cases.append(("last-duplicate-overlay-wins", payload))
    return cases


def run(command, data):
    return subprocess.run(command, input=data, capture_output=True, cwd=ROOT, timeout=30, check=False)


def first_difference(expected, actual, path="result"):
    if isinstance(expected, dict) and isinstance(actual, dict):
        if expected.keys() != actual.keys():
            return path + ": object keys differ"
        for key in expected:
            difference = first_difference(expected[key], actual[key], f"{path}.{key}")
            if difference:
                return difference
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return path + ": array lengths differ"
        for index, (left, right) in enumerate(zip(expected, actual)):
            difference = first_difference(left, right, f"{path}[{index}]")
            if difference:
                return difference
    elif expected != actual or (isinstance(expected, bool) != isinstance(actual, bool)):
        return f"{path}: expected {str(expected)[:160]!r}, got {str(actual)[:160]!r}"
    return None


def check_parity(binary, fixture):
    scenarios = [("public-demo", fixture)]
    scenarios += [("public-demo-zero-cap", {**fixture, "sat": 1300, "cap": 0}),
                  ("public-demo-high-score", {**fixture, "sat": 1600, "cap": 100})]
    scenarios += synthetic_cases()
    statuses = {key: set() for key in ("budget", "curriculum", "graduation", "sat", "overall")}
    evaluations = 0
    for name, payload in scenarios:
        data = encode(payload)
        expected = evaluate_all(json.loads(data))
        result = run([str(binary)], data)
        if result.returncode or result.stderr:
            raise ValueError(f"{name}: Rust failed or wrote unexpected stderr (details withheld)")
        try:
            actual = json.loads(result.stdout)
        except (ValueError, UnicodeDecodeError) as error:
            raise ValueError(f"{name}: Rust returned invalid JSON") from error
        difference = first_difference(expected, actual)
        if difference:
            raise ValueError(f"{name}: {difference}")
        for entry in expected:
            for key in statuses:
                statuses[key].add(entry[key] if key == "overall" else entry[key]["status"])
        evaluations += len(expected)
    required = {"budget": {"PASS", "FAIL", "UNKNOWN"}, "curriculum": {"PASS", "FAIL", "UNKNOWN"},
                "graduation": {"PASS", "FAIL", "UNKNOWN"},
                "sat": {"UNKNOWN", "TARGET_MET", "BELOW_TARGET", "NOT_CENTRAL"},
                "overall": {"GATES_MET", "BLOCKED", "NEEDS_VERIFICATION"}}
    if statuses != required:
        raise ValueError("The parity scenarios no longer cover every gate status")
    print(f"Parity: {len(scenarios)} scenarios / {evaluations} route evaluations matched, including all {len(fixture['routes'])} public routes.")


def check_invalid_inputs(binary):
    marker = "DO_NOT_ECHO_INVALID_INPUT_4A7E9"
    base = synthetic_cases()[0][1]
    invalid = [b'{"DO_NOT_ECHO_INVALID_INPUT_4A7E9":', encode(None), encode([]), encode({}),
               encode({**base, "routes": marker}), encode({**base, "overlays": marker}),
               encode({**base, "profile": marker}), encode({**base, "routes": [{"id": None}]}),
               encode({**base, "overlays": [{"routeId": marker, "personalSatTargetNote": 123}]}),
               encode({**base, "profile": {"snapshot": marker}}),
               encode({**base, "profile": {"snapshot": {"maxFamilyContributionIdrMPerMonth": None}}})]
    for field in ("cap", "sat"):
        invalid += [encode({**base, field: value}) for value in (-1, True, marker, {"$serde_json::private::Number": "4"})]
    numeric_marker = encode({**base, "cap": marker})
    invalid += [numeric_marker.replace(encode(marker), token) for token in (b"NaN", b"Infinity", b"-Infinity")]
    invalid.append(encode(base)[:-1] + b',"padding":"' + marker.encode() + b"x" * (32 * 1024 * 1024) + b'"}')
    for data in invalid:
        result = run([str(binary)], data)
        if result.returncode == 0 or result.stdout or not result.stderr or len(result.stderr) > 500 or marker.encode() in result.stderr:
            raise ValueError("Invalid input was not rejected with an empty stdout and a short, safe stderr")
    print(f"Invalid inputs: {len(invalid)} rejected without echoing input.")


def benchmark(binary, fixture, samples):
    data = encode(fixture)
    commands = {"Python": [sys.executable, "-B", "-m", "schola.evaluator"], "Rust": [str(binary)]}
    expected = evaluate_all(json.loads(data))
    # Each sample starts a fresh process and includes launch, parsing, evaluation, and serialization.
    for command in commands.values():
        for _ in range(3):
            result = run(command, data)
            if result.returncode or result.stderr or json.loads(result.stdout) != expected:
                raise ValueError("Benchmark warmup correctness check failed (details withheld)")
    timings = {name: [] for name in commands}
    for sample in range(samples):
        order = list(commands) if sample % 2 == 0 else list(reversed(commands))
        for name in order:
            start = time.perf_counter_ns()
            result = run(commands[name], data)
            elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
            if result.returncode or result.stderr or json.loads(result.stdout) != expected:
                raise ValueError("Benchmark sample correctness check failed (details withheld)")
            timings[name].append(elapsed_ms)
    print(f"CLI benchmark: identical {len(data)}-byte public payload; 3 warmups and {samples} fresh processes per implementation.")
    for name, values in timings.items():
        p95 = sorted(values)[math.ceil(.95 * len(values)) - 1]
        print(f"  {name}: median {statistics.median(values):.3f} ms; p95 {p95:.3f} ms")
    print("These are local CLI timings, including process startup; they do not measure phone or end-to-end app performance.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=ROOT / "rust/evaluator/target/release/studab27-evaluator",
                        help="already-built Rust release binary")
    parser.add_argument("--benchmark", action="store_true", help="benchmark only after all correctness checks pass")
    parser.add_argument("--samples", type=int, default=40, help="fresh-process samples per implementation (default: 40)")
    args = parser.parse_args()
    if not 10 <= args.samples <= 1000:
        parser.error("--samples must be between 10 and 1000")
    binary = args.binary.resolve()
    if not binary.is_file():
        parser.error("Build the Rust evaluator in release mode first, or pass --binary")
    try:
        fixture = public_fixture()
        check_parity(binary, fixture)
        check_invalid_inputs(binary)
        if args.benchmark:
            benchmark(binary, fixture, args.samples)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"Rust evaluator check failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
