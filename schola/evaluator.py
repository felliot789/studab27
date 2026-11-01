"""Deterministic planning gates. Missing evidence never means eligible."""
import calendar
import json
import math
import re
import sys
from datetime import date
from decimal import Decimal


def gate(status, reason, basis="UNKNOWN"):
    return {"status": status, "reason": reason, "basis": basis}


def numeric(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
        raise ValueError("Expected a finite, nonnegative number")
    return Decimal(str(value))


def estimate_range(value):
    """Only unambiguous ranges; do not turn '0 if funded, otherwise 20' into 0."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        n = numeric(value)
        return n, n
    text = str(value or "").strip().replace(",", ".")
    match = re.fullmatch(r"(?:~|≈)?\s*(\d+(?:\.\d+)?)\s*(?:[–—-]\s*(\d+(?:\.\d+)?))?", text)
    if not match:
        return None
    lo, hi = Decimal(match[1]), Decimal(match[2] or match[1])
    return (lo, hi) if lo <= hi else None


def verified_rule(overlay):
    rule = overlay.get("verifiedRules", {})
    # Verification explicitly describes the relevant program and cycle.
    if rule.get("cycle") == "2027" and rule.get("sourceUrl", "").startswith("https://") and rule.get("checkedAt") and rule.get("program"):
        return rule
    return {}


def budget_survivability_gate(overlay, cap):
    cap = numeric(cap)
    cost = overlay.get("costEstimate")
    if cost:
        try:
            keys = ("tuition", "housing", "food", "insurance", "other", "coverage")
            values = {k: numeric(cost[k]) for k in keys}
            total = sum(values[k] for k in keys if k != "coverage")
            gap = max(Decimal(0), total - values["coverage"])
            bounds = gap, gap
            detail = {"total": float(total), "coverage": float(values["coverage"]), "gap": float(gap)}
        except (KeyError, ValueError):
            return {**gate("UNKNOWN", "Cost estimate is incomplete or invalid."), "gapRange": None}
    else:
        bounds = estimate_range(overlay.get("estimatedFamilyGapIdrMPerMonth"))
        detail = None
    if bounds is None:
        return {**gate("UNKNOWN", "Add a monthly cost and coverage estimate; missing costs are not zero."), "gapRange": None}
    lo, hi = bounds
    if hi <= cap:
        result = gate("PASS", "Planning estimate fits the monthly family cap. Confirm actual costs and disbursement timing.", "ESTIMATE")
    elif lo > cap:
        result = gate("FAIL", "Even the low end exceeds the family cap. A tuition waiver alone may leave a living-cost gap.", "ESTIMATE")
    else:
        result = gate("UNKNOWN", "The estimated range crosses the family cap; get a firmer cost breakdown.", "ESTIMATE")
    return {**result, "gapRange": [float(lo), float(hi)], "calculation": detail}


def curriculum_gate(overlay):
    rule = verified_rule(overlay)
    accepted = rule.get("nationalCurriculumDirectEntry")
    if isinstance(accepted, bool):
        return gate("PASS" if accepted else "FAIL", "Direct-entry national-curriculum rule recorded for this program; other requirements still apply." if accepted else "Verified rule requires an additional qualification or foundation pathway.", "VERIFIED_RULE")
    return gate("UNKNOWN", "Confirm Indonesian national-diploma direct entry for the exact engineering program and 2027 cycle.")


def graduation_gate(overlay, profile):
    rule = verified_rule(overlay)
    if rule.get("preGraduationApplicationAllowed") is True:
        return gate("PASS", "A current program-specific source permits applying before graduation; final-document conditions still apply.", "VERIFIED_RULE")
    deadline = rule.get("finalDiplomaDeadline")
    if rule.get("preGraduationApplicationAllowed") is False and deadline:
        try:
            cutoff = date.fromisoformat(deadline)
            text = profile.get("snapshot", {}).get("expectedGraduation", "")
            try:
                earliest = latest = date.fromisoformat(text)
            except ValueError:
                match = re.fullmatch(r"([A-Za-z]+) (\d{4})", text)
                if not match:
                    raise ValueError("Missing graduation date")
                month = list(calendar.month_name).index(match[1])
                year = int(match[2])
                earliest = date(year, month, 1)
                latest = date(year, month, calendar.monthrange(year, month)[1])
            if earliest > cutoff:
                return gate("FAIL", "Final diploma is required before the earliest expected graduation date.", "VERIFIED_RULE")
            if latest <= cutoff:
                return gate("PASS", "Graduation is expected before the diploma cutoff; document issuance still needs confirmation.", "VERIFIED_RULE")
        except (ValueError, TypeError):
            pass
    return gate("UNKNOWN", "Verify expected-graduation/SKL acceptance and the final diploma deadline; seed wording is unverified.")


def evaluate(route, overlay, profile, sat=None, cap=None):
    snap = profile.get("snapshot", {})
    cap = snap.get("maxFamilyContributionIdrMPerMonth", 0) if cap is None else cap
    budget = budget_survivability_gate(overlay, cap)
    curriculum = curriculum_gate(overlay)
    graduation = graduation_gate(overlay, profile)
    target_text = overlay.get("personalSatTargetNote") or route.get("suggestedSatBenchmark", "")
    target_match = re.search(r"\b(1[3-5]\d{2}|1600)\b", target_text)
    target = int(target_match[1]) if target_match else None
    sat_result = {"status": "UNKNOWN", "target": target, "scenarioScore": sat, "basis": "ADVISORY_TARGET"}
    if sat is not None and target:
        numeric(sat)
        sat_result["status"] = "TARGET_MET" if sat >= target else "BELOW_TARGET"
    elif route.get("satRole") == "LOW":
        sat_result["status"] = "NOT_CENTRAL"
    statuses = [g["status"] for g in (budget, curriculum, graduation)]
    overall = "BLOCKED" if "FAIL" in statuses else "GATES_MET" if all(s == "PASS" for s in statuses) else "NEEDS_VERIFICATION"
    return {"routeId": route["id"], "budget": budget, "curriculum": curriculum, "graduation": graduation, "sat": sat_result, "overall": overall}


def evaluate_all(payload):
    overlays = {o["routeId"]: o for o in payload["overlays"]}
    return [evaluate(r, overlays.get(r["id"], {}), payload["profile"], payload.get("sat"), payload.get("cap")) for r in payload["routes"]]


if __name__ == "__main__":
    json.dump(evaluate_all(json.load(sys.stdin)), sys.stdout)
