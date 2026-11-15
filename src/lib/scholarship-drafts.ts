/** Public research fields only. Owner plans and priorities are separate records. */
export type DraftFields = {
  country: string;
  institution: string;
  scholarshipName: string;
  programAndLanguageNotes: string;
  benefitsCoverage: string;
  indonesianApplicantNotes: string;
  languageOrTestNotes: string;
  separateScholarshipApp: string;
  preGradApplyAllowed: string;
  renewalAndBondTerms: string;
  publicRiskOrCaveat: string;
  officialSourceUrl: string;
  unresolvedQuestions: string[];
};

export type DraftSource = { url: string; title?: string; finding?: string; checkedAt: string };
export type DraftMatch = { routeId: string; institution: string; scholarshipName: string; kind: "EXACT" | "POSSIBLE" };
export type ScholarshipDraft = {
  id: string;
  revision: number;
  status: "RESEARCHING" | "READY" | "FAILED" | "ACCEPTED";
  query: string;
  jobId: string;
  createdAt: string;
  updatedAt: string;
  fields: DraftFields;
  sources: DraftSource[];
  matches: DraftMatch[];
  acceptedRouteId?: string;
  error?: string;
};
