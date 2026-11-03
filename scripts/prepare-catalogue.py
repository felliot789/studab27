"""Project reviewed research into public facts, without copying private review files.

Usage: python3 scripts/prepare-catalogue.py REVIEW_DIRECTORY
The review directory stays outside the public catalogue and client bundle.
"""
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
review = Path(sys.argv[1])
route_keys = "id country institution scholarshipName fundingType engineeringFit benefitsCoverage satRole suggestedSatBenchmark languageOrTestNotes deadlineWindow2027 preGradApplyAllowed separateScholarshipApp renewalAndBondTerms publicRiskOrCaveat officialSourceUrl secondarySourceUrl seedStatus currentCycleStatus currentCycleEvidenceSummary indonesianApplicantNotes programAndLanguageNotes aiContentPolicy unresolvedQuestions".split()
event_keys = "id routeId cycle program round eventType title date time timezone windowText dateStatus prerequisiteEventIds sourceUrl sourceEvidence checkedAt candidateDate candidateTime candidateTimezone calendarDateSupported humanVerified timezoneIana timezoneOffset timezoneInterpretation deadlineAtWib endDate conditions cutoffTimeText".split()


def evidence(items):
    return [{key: item[key] for key in ("url", "checkedAt", "finding", "supportedFields", "scope") if key in item} for item in items]


routes = []
for record in json.loads((review / "refreshed_routes.reviewed.json").read_text()):
    route = {key: record[key] for key in route_keys if key in record}
    route["programAndLanguageNotes"] = route["programAndLanguageNotes"].replace("Original claims remain in originalResearchRecord.", "Earlier claims still need programme-specific evidence.")
    route["currentCycleEvidenceSummary"] = route["currentCycleEvidenceSummary"].replace("unless fieldReview cites a source", "unless a specific source is shown")
    route["fieldReview"] = {key: {"status": item["status"], "evidence": evidence(item.get("evidence", []))} for key, item in record.get("fieldReview", {}).items()}
    route["evidenceSources"] = evidence(record.get("evidenceSources", []))
    route["reviewedAt"] = "2026-11-03"
    routes.append(route)

events = []
for record in json.loads((review / "calendar_events.reviewed.json").read_text()):
    event = {key: record[key] for key in event_keys if key in record}
    source = record["sourceReview"]
    event["sourceReview"] = {key: source[key] for key in ("status", "note", "reviewedAt", "scope")}
    event["sourceReview"]["evidence"] = evidence(source.get("evidence", []))
    events.append(event)

assert len(routes) == 57 and len(events) == 174
for filename, records in (("scholarships_2027.json", routes), ("calendar_events.json", events)):
    (root / "data/public" / filename).write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n")
print("Prepared 57 public route records and 174 calendar records; private review artifacts excluded.")
