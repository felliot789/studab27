//! Read-only planning gates matching `schola/evaluator.py`.
//!
//! Input is the application's JSON evaluation payload; unknown fields are ignored.
//! Gate decisions use decimal arithmetic, never binary floating-point arithmetic.

use bigdecimal::{BigDecimal, RoundingMode, ToPrimitive};
use chrono::{Datelike, NaiveDate, Weekday};
use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::num::NonZeroU64;
use std::str::FromStr;
use std::sync::OnceLock;

/// Deliberately carries no input, path, or parser details across the CLI boundary.
#[derive(Debug)]
pub struct EvaluationError;

#[derive(Deserialize)]
pub struct Payload {
    routes: Vec<Route>,
    overlays: Vec<Overlay>,
    profile: Profile,
    #[serde(default)]
    sat: Option<Value>,
    #[serde(default)]
    cap: Option<Value>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Route {
    id: String,
    #[serde(default)]
    sat_role: String,
    #[serde(default)]
    suggested_sat_benchmark: String,
}

#[derive(Default, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Overlay {
    route_id: String,
    #[serde(default)]
    estimated_family_gap_idr_m_per_month: Value,
    #[serde(default)]
    personal_sat_target_note: String,
    #[serde(default)]
    cost_estimate: Option<Value>,
    #[serde(default)]
    verified_rules: Option<VerifiedRules>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct VerifiedRules {
    #[serde(default)]
    cycle: String,
    #[serde(default)]
    program: String,
    #[serde(default)]
    source_url: String,
    #[serde(default)]
    checked_at: String,
    #[serde(default)]
    national_curriculum_direct_entry: Value,
    #[serde(default)]
    pre_graduation_application_allowed: Value,
    #[serde(default)]
    final_diploma_deadline: Option<String>,
}

#[derive(Deserialize)]
struct Profile {
    #[serde(default)]
    snapshot: Snapshot,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Snapshot {
    #[serde(default)]
    expected_graduation: Option<String>,
    #[serde(default = "default_cap")]
    max_family_contribution_idr_m_per_month: Value,
}

fn default_cap() -> Value {
    Value::from(0)
}

impl Default for Snapshot {
    fn default() -> Self {
        Self {
            expected_graduation: None,
            max_family_contribution_idr_m_per_month: default_cap(),
        }
    }
}

#[derive(Serialize)]
pub struct Gate {
    status: &'static str,
    reason: &'static str,
    basis: &'static str,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BudgetGate {
    #[serde(flatten)]
    gate: Gate,
    gap_range: Option<[f64; 2]>,
    #[serde(skip_serializing_if = "Option::is_none")]
    calculation: Option<Option<Calculation>>,
}

#[derive(Serialize)]
struct Calculation {
    total: f64,
    coverage: f64,
    gap: f64,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct SatGate {
    status: &'static str,
    target: Option<u16>,
    scenario_score: Option<Value>,
    basis: &'static str,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Evaluation {
    route_id: String,
    budget: BudgetGate,
    curriculum: Gate,
    graduation: Gate,
    sat: SatGate,
    overall: &'static str,
}

fn gate(status: &'static str, reason: &'static str, basis: &'static str) -> Gate {
    Gate {
        status,
        reason,
        basis,
    }
}

fn numeric(value: &Value) -> Result<BigDecimal, EvaluationError> {
    let number = value.as_number().ok_or(EvaluationError)?;
    let finite = number
        .as_f64()
        .filter(|n| n.is_finite() && *n >= 0.0)
        .ok_or(EvaluationError)?;
    let text = number.to_string();
    // Python's JSON reader makes decimal/exponent tokens floats, then numeric()
    // uses Decimal(str(value)). Normalize those tokens to the same shortest
    // round-trip decimal; retain integer tokens exactly as Python does.
    let normalized = if text.contains(['.', 'e', 'E']) {
        finite.to_string()
    } else {
        text
    };
    BigDecimal::from_str(&normalized).map_err(|_| EvaluationError)
}

fn output_number(value: &BigDecimal) -> Result<f64, EvaluationError> {
    value
        .to_f64()
        .filter(|n| n.is_finite())
        .ok_or(EvaluationError)
}

fn rounded(value: BigDecimal) -> BigDecimal {
    // Python Decimal's default context is 28 significant digits, half even.
    value.with_precision_round(
        NonZeroU64::new(28).expect("nonzero precision"),
        RoundingMode::HalfEven,
    )
}

fn ascii_decimal_digits(text: &str) -> Option<String> {
    // Unicode 15.1 decimal-digit zeroes, matching the Python runtime's UCD.
    // Decimal/int accept these digits after Python's Unicode-aware \d regex.
    const ZEROES: &[u32] = &[
        0x30, 0x660, 0x6f0, 0x7c0, 0x966, 0x9e6, 0xa66, 0xae6, 0xb66, 0xbe6, 0xc66, 0xce6, 0xd66,
        0xde6, 0xe50, 0xed0, 0xf20, 0x1040, 0x1090, 0x17e0, 0x1810, 0x1946, 0x19d0, 0x1a80, 0x1a90,
        0x1b50, 0x1bb0, 0x1c40, 0x1c50, 0xa620, 0xa8d0, 0xa900, 0xa9d0, 0xa9f0, 0xaa50, 0xabf0,
        0xff10, 0x104a0, 0x10d30, 0x11066, 0x110f0, 0x11136, 0x111d0, 0x112f0, 0x11450, 0x114d0,
        0x11650, 0x116c0, 0x11730, 0x118e0, 0x11950, 0x11c50, 0x11d50, 0x11da0, 0x11f50, 0x16a60,
        0x16ac0, 0x16b50, 0x1d7ce, 0x1d7d8, 0x1d7e2, 0x1d7ec, 0x1d7f6, 0x1e140, 0x1e2f0, 0x1e4f0,
        0x1e950, 0x1fbf0,
    ];
    text.chars()
        .map(|character| {
            if character == '.' {
                return Some('.');
            }
            let code = character as u32;
            ZEROES.iter().find_map(|zero| {
                (code >= *zero && code < zero + 10).then(|| (b'0' + (code - zero) as u8) as char)
            })
        })
        .collect()
}

fn truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(value) => *value,
        Value::Number(value) => value.as_f64().is_some_and(|n| n != 0.0),
        Value::String(value) => !value.is_empty(),
        Value::Array(value) => !value.is_empty(),
        Value::Object(value) => !value.is_empty(),
    }
}

fn estimate_range(value: &Value) -> Result<Option<(BigDecimal, BigDecimal)>, EvaluationError> {
    if value.is_number() {
        let number = numeric(value)?;
        return Ok(Some((number.clone(), number)));
    }
    let Some(text) = value.as_str() else {
        return Ok(None);
    };
    let text = text.trim().replace(',', ".");
    static RANGE: OnceLock<Regex> = OnceLock::new();
    let pattern = RANGE.get_or_init(|| {
        Regex::new(r"^(?:~|≈)?\s*(\d+(?:\.\d+)?)\s*(?:[–—-]\s*(\d+(?:\.\d+)?))?$")
            .expect("constant range regex")
    });
    let Some(captures) = pattern.captures(&text) else {
        return Ok(None);
    };
    let Some(lo_text) = ascii_decimal_digits(&captures[1]) else {
        return Ok(None);
    };
    let Some(hi_text) = ascii_decimal_digits(captures.get(2).map_or(&captures[1], |m| m.as_str()))
    else {
        return Ok(None);
    };
    let Ok(lo) = BigDecimal::from_str(&lo_text) else {
        return Ok(None);
    };
    let Ok(hi) = BigDecimal::from_str(&hi_text) else {
        return Ok(None);
    };
    Ok((lo <= hi).then_some((lo, hi)))
}

fn unknown_budget(reason: &'static str) -> BudgetGate {
    BudgetGate {
        gate: gate("UNKNOWN", reason, "UNKNOWN"),
        gap_range: None,
        calculation: None,
    }
}

fn budget(overlay: &Overlay, cap: &BigDecimal) -> Result<BudgetGate, EvaluationError> {
    let (lo, hi, calculation) = if let Some(cost) =
        overlay.cost_estimate.as_ref().filter(|value| truthy(value))
    {
        let Some(cost) = cost.as_object() else {
            return Ok(unknown_budget("Cost estimate is incomplete or invalid."));
        };
        let fields = [
            "tuition",
            "housing",
            "food",
            "insurance",
            "other",
            "coverage",
        ];
        let values: Result<Vec<_>, _> = fields
            .iter()
            .map(|name| cost.get(*name).ok_or(EvaluationError).and_then(numeric))
            .collect();
        let Ok(values) = values else {
            return Ok(unknown_budget("Cost estimate is incomplete or invalid."));
        };
        let total = values[..5]
            .iter()
            .fold(BigDecimal::from(0), |total, value| rounded(total + value));
        let coverage = &values[5];
        let gap = rounded(&total - coverage).max(BigDecimal::from(0));
        let detail = Calculation {
            total: output_number(&total)?,
            coverage: output_number(coverage)?,
            gap: output_number(&gap)?,
        };
        (gap.clone(), gap, Some(detail))
    } else {
        let Some((lo, hi)) = estimate_range(&overlay.estimated_family_gap_idr_m_per_month)? else {
            return Ok(unknown_budget(
                "Add a monthly cost and coverage estimate; missing costs are not zero.",
            ));
        };
        (lo, hi, None)
    };
    let result = if &hi <= cap {
        gate(
            "PASS",
            "Planning estimate fits the monthly family cap. Confirm actual costs and disbursement timing.",
            "ESTIMATE",
        )
    } else if &lo > cap {
        gate(
            "FAIL",
            "Even the low end exceeds the family cap. A tuition waiver alone may leave a living-cost gap.",
            "ESTIMATE",
        )
    } else {
        gate(
            "UNKNOWN",
            "The estimated range crosses the family cap; get a firmer cost breakdown.",
            "ESTIMATE",
        )
    };
    Ok(BudgetGate {
        gate: result,
        gap_range: Some([output_number(&lo)?, output_number(&hi)?]),
        calculation: Some(calculation),
    })
}

fn verified_rule(overlay: &Overlay) -> Option<&VerifiedRules> {
    overlay.verified_rules.as_ref().filter(|rule| {
        rule.cycle == "2027"
            && rule.source_url.starts_with("https://")
            && !rule.checked_at.is_empty()
            && !rule.program.is_empty()
    })
}

fn curriculum(rule: Option<&VerifiedRules>) -> Gate {
    match rule.and_then(|rule| rule.national_curriculum_direct_entry.as_bool()) {
        Some(true) => gate(
            "PASS",
            "Direct-entry national-curriculum rule recorded for this program; other requirements still apply.",
            "VERIFIED_RULE",
        ),
        Some(false) => gate(
            "FAIL",
            "Verified rule requires an additional qualification or foundation pathway.",
            "VERIFIED_RULE",
        ),
        None => gate(
            "UNKNOWN",
            "Confirm Indonesian national-diploma direct entry for the exact engineering program and 2027 cycle.",
            "UNKNOWN",
        ),
    }
}

fn iso_date(text: &str) -> Option<NaiveDate> {
    // Python date.fromisoformat accepts calendar and ISO-week forms, with or
    // without separators. Do not broaden it to partial/ambiguous dates.
    static ISO: OnceLock<Regex> = OnceLock::new();
    let pattern = ISO.get_or_init(|| Regex::new(r"^(?:([0-9]{4})-([0-9]{2})-([0-9]{2})|([0-9]{4})([0-9]{2})([0-9]{2})|([0-9]{4})-W([0-9]{2})(?:-([1-7]))?|([0-9]{4})W([0-9]{2})([1-7])?)$").expect("constant date regex"));
    let captures = pattern.captures(text)?;
    let integer = |index| captures.get(index)?.as_str().parse::<u32>().ok();
    for start in [1, 4] {
        if let Some(year) = integer(start).filter(|year| *year > 0) {
            return NaiveDate::from_ymd_opt(year as i32, integer(start + 1)?, integer(start + 2)?);
        }
    }
    for start in [7, 10] {
        if let Some(year) = integer(start).filter(|year| *year > 0) {
            let weekdays = [
                Weekday::Mon,
                Weekday::Tue,
                Weekday::Wed,
                Weekday::Thu,
                Weekday::Fri,
                Weekday::Sat,
                Weekday::Sun,
            ];
            let day = integer(start + 2).unwrap_or(1);
            let date = NaiveDate::from_isoywd_opt(
                year as i32,
                integer(start + 1)?,
                weekdays[(day - 1) as usize],
            )?;
            return (1..=9999).contains(&date.year()).then_some(date);
        }
    }
    None
}

fn graduation_range(text: &str) -> Option<(NaiveDate, NaiveDate)> {
    if let Some(date) = iso_date(text) {
        return Some((date, date));
    }
    static MONTH: OnceLock<Regex> = OnceLock::new();
    let pattern =
        MONTH.get_or_init(|| Regex::new(r"^([A-Za-z]+) (\d{4})$").expect("constant month regex"));
    let captures = pattern.captures(text)?;
    let month = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    .iter()
    .position(|name| *name == &captures[1])? as u32
        + 1;
    let year: i32 = ascii_decimal_digits(&captures[2])?.parse().ok()?;
    if year == 0 {
        return None;
    }
    let earliest = NaiveDate::from_ymd_opt(year, month, 1)?;
    let latest = (28..=31)
        .rev()
        .find_map(|day| NaiveDate::from_ymd_opt(year, month, day))?;
    Some((earliest, latest))
}

fn graduation(rule: Option<&VerifiedRules>, snapshot: &Snapshot) -> Gate {
    if let Some(rule) = rule {
        match rule.pre_graduation_application_allowed.as_bool() {
            Some(true) => {
                return gate(
                    "PASS",
                    "A current program-specific source permits applying before graduation; final-document conditions still apply.",
                    "VERIFIED_RULE",
                );
            }
            Some(false) => {
                if let Some((cutoff, (earliest, latest))) = rule
                    .final_diploma_deadline
                    .as_deref()
                    .and_then(iso_date)
                    .zip(
                        snapshot
                            .expected_graduation
                            .as_deref()
                            .and_then(graduation_range),
                    )
                {
                    if earliest > cutoff {
                        return gate(
                            "FAIL",
                            "Final diploma is required before the earliest expected graduation date.",
                            "VERIFIED_RULE",
                        );
                    }
                    if latest <= cutoff {
                        return gate(
                            "PASS",
                            "Graduation is expected before the diploma cutoff; document issuance still needs confirmation.",
                            "VERIFIED_RULE",
                        );
                    }
                }
            }
            None => {}
        }
    }
    gate(
        "UNKNOWN",
        "Verify expected-graduation/SKL acceptance and the final diploma deadline; seed wording is unverified.",
        "UNKNOWN",
    )
}

fn evaluate(
    route: &Route,
    overlay: &Overlay,
    snapshot: &Snapshot,
    cap: &BigDecimal,
    sat: &Option<Value>,
    sat_number: Option<&BigDecimal>,
) -> Result<Evaluation, EvaluationError> {
    let budget = budget(overlay, cap)?;
    let rule = verified_rule(overlay);
    let curriculum = curriculum(rule);
    let graduation = graduation(rule, snapshot);
    let target_text = if overlay.personal_sat_target_note.is_empty() {
        &route.suggested_sat_benchmark
    } else {
        &overlay.personal_sat_target_note
    };
    static SAT: OnceLock<Regex> = OnceLock::new();
    // Python's Unicode \w is letters/numbers/underscore; Rust's \w also
    // includes combining marks, so spell out the Python word boundaries.
    let pattern = SAT.get_or_init(|| {
        Regex::new(r"(?:^|[^\p{L}\p{N}_])(1[3-5]\d{2}|1600)(?:$|[^\p{L}\p{N}_])")
            .expect("constant SAT regex")
    });
    let target = pattern
        .captures(target_text)
        .and_then(|captures| ascii_decimal_digits(&captures[1])?.parse::<u16>().ok());
    let sat_status = match (sat_number, target) {
        (Some(score), Some(target)) if score >= &BigDecimal::from(target) => "TARGET_MET",
        (Some(_), Some(_)) => "BELOW_TARGET",
        _ if route.sat_role == "LOW" => "NOT_CENTRAL",
        _ => "UNKNOWN",
    };
    let statuses = [budget.gate.status, curriculum.status, graduation.status];
    let overall = if statuses.contains(&"FAIL") {
        "BLOCKED"
    } else if statuses.iter().all(|status| *status == "PASS") {
        "GATES_MET"
    } else {
        "NEEDS_VERIFICATION"
    };
    Ok(Evaluation {
        route_id: route.id.clone(),
        budget,
        curriculum,
        graduation,
        sat: SatGate {
            status: sat_status,
            target,
            scenario_score: sat.clone(),
            basis: "ADVISORY_TARGET",
        },
        overall,
    })
}

/// Evaluate every route in order. Duplicate overlays keep the last entry, just
/// like the Python dictionary comprehension. Nothing is written on an error.
pub fn evaluate_all(payload: Payload) -> Result<Vec<Evaluation>, EvaluationError> {
    let cap = numeric(
        payload.cap.as_ref().unwrap_or(
            &payload
                .profile
                .snapshot
                .max_family_contribution_idr_m_per_month,
        ),
    )?;
    let sat_number = payload.sat.as_ref().map(numeric).transpose()?;
    let overlays: HashMap<_, _> = payload
        .overlays
        .iter()
        .map(|overlay| (overlay.route_id.as_str(), overlay))
        .collect();
    let empty = Overlay::default();
    payload
        .routes
        .iter()
        .map(|route| {
            evaluate(
                route,
                overlays.get(route.id.as_str()).copied().unwrap_or(&empty),
                &payload.profile.snapshot,
                &cap,
                &payload.sat,
                sat_number.as_ref(),
            )
        })
        .collect()
}

/// Decode JSON and evaluate it without filesystem or network access.
pub fn evaluate_json(input: &[u8]) -> Result<Vec<u8>, EvaluationError> {
    let payload = serde_json::from_slice(input).map_err(|_| EvaluationError)?;
    let evaluations = evaluate_all(payload)?;
    serde_json::to_vec(&evaluations).map_err(|_| EvaluationError)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn run(extra: Value) -> Value {
        let mut payload = json!({"routes": [{"id": "example", "suggestedSatBenchmark": "1500+"}], "overlays": [{"routeId": "example"}], "profile": {"snapshot": {"maxFamilyContributionIdrMPerMonth": 4}}});
        for (key, value) in extra.as_object().unwrap() {
            payload[key] = value.clone();
        }
        serde_json::from_slice(&evaluate_json(&serde_json::to_vec(&payload).unwrap()).unwrap())
            .unwrap()
    }

    #[test]
    fn costs_use_decimal_arithmetic_and_ignore_upfront() {
        let result = run(
            json!({"cap": 0.3, "overlays": [{"routeId": "example", "costEstimate": {"tuition": 0.1, "housing": 0.2, "food": 0, "insurance": 0, "other": 0, "coverage": 0, "upfront": "ignored"}}]}),
        );
        assert_eq!(result[0]["budget"]["status"], "PASS");
        assert_eq!(result[0]["budget"]["gapRange"], json!([0.3, 0.3]));
    }

    #[test]
    fn missing_evidence_and_sat_never_make_gates_pass() {
        let result = run(
            json!({"sat": 1560, "overlays": [{"routeId": "example", "estimatedFamilyGapIdrMPerMonth": "0–2"}]}),
        );
        assert_eq!(result[0]["sat"]["status"], "TARGET_MET");
        assert_eq!(result[0]["curriculum"]["status"], "UNKNOWN");
        assert_eq!(result[0]["graduation"]["status"], "UNKNOWN");
        assert_eq!(result[0]["overall"], "NEEDS_VERIFICATION");
    }

    #[test]
    fn month_graduation_is_a_range_and_leap_days_are_validated() {
        assert_eq!(graduation_range("February 2028").unwrap().1.day(), 29);
        assert_eq!(graduation_range("February 2027").unwrap().1.day(), 28);
        assert_eq!(iso_date("2027-W24-3"), iso_date("20270616"));
        assert_eq!(iso_date("2027-02-29"), None);
        assert_eq!(iso_date("2027-6-01"), None);
        assert_eq!(graduation_range("june 2027"), None);
    }

    #[test]
    fn tiny_numbers_and_python_float_normalization_are_preserved() {
        let result = run(
            json!({"cap": 1e-30, "overlays": [{"routeId": "example", "costEstimate": {"tuition": 1e-30, "housing": 0, "food": 0, "insurance": 0, "other": 0, "coverage": 0}}]}),
        );
        assert_eq!(result[0]["budget"]["status"], "PASS");
        assert_eq!(
            numeric(&serde_json::from_str("0.10000000000000001").unwrap()).unwrap(),
            BigDecimal::from_str("0.1").unwrap()
        );
    }

    #[test]
    fn invalid_scenario_numbers_fail_atomically() {
        for invalid in [json!(true), json!(-1), json!("4")] {
            let payload = json!({"routes": [{"id": "example"}], "overlays": [], "profile": {}, "cap": invalid});
            assert!(evaluate_json(&serde_json::to_vec(&payload).unwrap()).is_err());
        }
        let input = br#"{"routes":[{"id":"example"}],"overlays":[],"profile":{},"cap":{"$serde_json::private::Number":"4"}}"#;
        assert!(evaluate_json(input).is_err());
        let input = br#"{"routes":[{"id":"example"}],"overlays":[],"profile":{},"sat":{"$serde_json::private::Number":"1500"}}"#;
        assert!(evaluate_json(input).is_err());
        let input = br#"{"routes":[{"id":"example"}],"overlays":[],"profile":{"snapshot":{"maxFamilyContributionIdrMPerMonth":null}}}"#;
        assert!(evaluate_json(input).is_err());
        let result = run(
            json!({"overlays": [{"routeId": "example", "costEstimate": {"tuition": {"$serde_json::private::Number": "1"}, "housing": 0, "food": 0, "insurance": 0, "other": 0, "coverage": 0}}]}),
        );
        assert_eq!(result[0]["budget"]["status"], "UNKNOWN");
    }

    #[test]
    fn sat_word_boundaries_match_python_for_combining_marks() {
        for note in ["1500\u{0301}", "\u{0301}1500"] {
            let result = run(
                json!({"sat": 1550, "routes": [{"id": "example", "suggestedSatBenchmark": note}]}),
            );
            assert_eq!(result[0]["sat"]["target"], 1500);
            assert_eq!(result[0]["sat"]["status"], "TARGET_MET");
        }
    }
}
