import type { OutlookCategory, Route } from "./schema";

export const OUTLOOK_CATEGORIES: OutlookCategory[] = ["REALISTIC", "REACH", "LOTTERY", "UNKNOWN"];
export const OUTLOOK_LABELS: Record<OutlookCategory, string> = { REALISTIC: "Realistic", REACH: "Reach", LOTTERY: "Lottery", UNKNOWN: "Unknown" };
export const OUTLOOK_EXPLANATIONS: Record<OutlookCategory, string> = {
  REALISTIC: "Evidence supports a more attainable path to the award. This is a planning assessment, not a guarantee or a 50% prediction.",
  REACH: "Competitive selection with demanding requirements. A credible application still needs strong evidence of fit.",
  LOTTERY: "An exceptionally limited or selective opportunity. Even strong applicants should treat the outcome as a long shot.",
  UNKNOWN: "There is not enough reviewed evidence to judge the outcome. Unknown does not mean unlikely or ineligible.",
};

// Priority labels, budget passes and SAT targets are not evidence of winning.
export function outlookCategory(route: Route): OutlookCategory {
  const review = route.scholarshipOutlook;
  return review?.reason && review.reviewedAt && review.evidence?.length && OUTLOOK_CATEGORIES.includes(review.category) ? review.category : "UNKNOWN";
}

export function matchesOutlook(route: Route, category: OutlookCategory | "ALL", hideLottery = false) {
  const current = outlookCategory(route);
  return (category === "ALL" || current === category) && (!hideLottery || current !== "LOTTERY");
}

export function publishedAwardRate(route: Route): string | null {
  const rate = route.scholarshipOutlook?.publishedRate;
  if (!rate || rate.outcome !== "SCHOLARSHIP_AWARDED" || rate.applicantStage !== "ALL_APPLICANTS" || !rate.cycle?.trim() || !rate.population?.trim()
    || !Number.isSafeInteger(rate.applicants) || rate.applicants <= 0
    || !Number.isSafeInteger(rate.recipients) || rate.recipients < 0 || rate.recipients > rate.applicants
    || !route.scholarshipOutlook?.evidence.some(source => source.url === rate.sourceUrl)) return null;
  // Only a matched award/applicant cohort can produce a percentage. Admission
  // rates and percentages of costs covered cannot become scholarship odds.
  const percent = rate.recipients / rate.applicants * 100;
  if (percent > 0 && percent < 0.1) return "<0.1%";
  if (percent < 100 && percent > 99.9) return ">99.9%";
  return `${Number(percent.toFixed(1))}%`;
}
