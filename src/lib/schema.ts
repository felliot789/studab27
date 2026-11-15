export type GateStatus = "PASS" | "FAIL" | "UNKNOWN";
export type ApplicationStatus = "NOT_STARTED" | "RESEARCHING" | "IN_PROGRESS" | "SUBMITTED" | "DEFER_TO_MAIN_ROUND" | "DROP";
export const APPLICATION_STATUSES: ApplicationStatus[] = ["NOT_STARTED", "RESEARCHING", "IN_PROGRESS", "SUBMITTED", "DEFER_TO_MAIN_ROUND", "DROP"];
export type Evidence = { url: string; checkedAt?: string; finding?: string; supportedFields?: string[]; scope?: string };
export type OutlookCategory = "REALISTIC" | "REACH" | "LOTTERY" | "UNKNOWN";
export type ScholarshipOutlook = {
  category: OutlookCategory; reason: string; scope: string; reviewedAt: string; evidence: Evidence[];
  publishedRate?: { outcome: "SCHOLARSHIP_AWARDED"; applicantStage: "ALL_APPLICANTS"; cycle: string; population: string; applicants: number; recipients: number; sourceUrl: string };
};
export type PursuitLevel = "FOCUS" | "SECONDARY" | "BACKUP";
export type RequirementStatus = "TODO" | "DOING" | "DONE" | "NOT_NEEDED";
export type ApplicationRequirement = {
  id: string; title: string; detail: string; kind: "DOCUMENT" | "TASK";
  basis: "CURRENT" | "GENERAL" | "RECHECK"; sourceIds: string[];
  sharedKey?: string; optional?: boolean;
};
export type ApplicationGuide = {
  cycle: string; reviewedAt: string; summary: string;
  sources: { id: string; title: string; url: string; scope: string }[];
  sections: { id: string; title: string; items: ApplicationRequirement[] }[];
};
export type RequirementProgress = { status: RequirementStatus; note?: string; updatedAt?: string };
export type CalendarEvent = {
  id: string; routeId: string; cycle: string; program: string; round: string | null;
  eventType: string; title: string; date: string | null; endDate?: string; time: string | null;
  timezone: string | null; windowText: string | null; dateStatus: string;
  prerequisiteEventIds: string[]; sourceUrl: string; sourceEvidence: string; checkedAt: string;
  calendarDateSupported: boolean; humanVerified: boolean; deadlineAtWib: string | null;
  candidateDate?: string; candidateTime?: string; candidateTimezone?: string;
  conditions?: string[] | string; cutoffTimeText?: string;
  sourceReview: { status: string; note: string; reviewedAt: string; scope: string; evidence: Evidence[] };
};
export type Route = {
  local?: boolean;
  id: string; country: string; institution: string; scholarshipName: string;
  fundingType: string; engineeringFit: string; benefitsCoverage: string; satRole: string;
  suggestedSatBenchmark: string; languageOrTestNotes: string; deadlineWindow2027: string;
  preGradApplyAllowed: string; separateScholarshipApp: string; renewalAndBondTerms: string;
  publicRiskOrCaveat: string; officialSourceUrl: string; secondarySourceUrl: string;
  seedStatus: string;
  currentCycleStatus?: string; currentCycleEvidenceSummary?: string; reviewedAt?: string;
  indonesianApplicantNotes?: string; programAndLanguageNotes?: string; aiContentPolicy?: string;
  unresolvedQuestions?: string[]; evidenceSources?: Evidence[];
  fieldReview?: Record<string, { status: string; evidence: Evidence[] }>;
  scholarshipOutlook?: ScholarshipOutlook;
  applicationGuide?: ApplicationGuide;
};
export type CostEstimate = { tuition: number; housing: number; food: number; insurance: number; other: number; coverage: number; upfront?: number };
export type Overlay = {
  routeId: string; personalStrategyTier: string; estimatedFamilyGapIdrMPerMonth: string;
  personalSatTargetNote: string; personalRiskNote: string; applicationStatus: ApplicationStatus;
  saved?: boolean; driveApplicationFolder?: string; costEstimate?: CostEstimate; notes?: string;
  tracked?: boolean; mainTarget?: boolean; pursuitLevel?: PursuitLevel;
  verifiedRules?: { cycle: string; program: string; sourceUrl: string; checkedAt: string; nationalCurriculumDirectEntry?: boolean; preGraduationApplicationAllowed?: boolean; finalDiplomaDeadline?: string };
};
export type Profile = {
  projectTitle: string; mission: string;
  snapshot: { school?: string; curriculum: string; citizenship: string; expectedGraduation: string;
    maxFamilyContributionIdrMPerMonth: number; ieltsAcademicOverall?: number; targetFields?: string[];
    satPlan?: { targetTotal: number; firstOfficialAttemptDate?: string; scoreReleaseDate?: string } };
};
export type Gate = { status: GateStatus; reason: string; basis: string };
export type Evaluation = {
  routeId: string; curriculum: Gate; graduation: Gate;
  budget: Gate & { gapRange: [number, number] | null; calculation?: { total: number; coverage: number; gap: number } | null };
  sat: { status: string; target: number | null; scenarioScore: number | null; basis: string };
  overall: "BLOCKED" | "GATES_MET" | "NEEDS_VERIFICATION";
};
export type Task = { id: string; category: "DECISION_GATE" | "VERIFY_RULE" | "DOC_BRICK_STEP"; title: string; description: string; minutes: number; priority: number; routeIds: string[]; sources: string[]; steps: string[]; brickId?: string; requiresActiveRoute?: boolean; generated?: boolean };
export type Brick = { id: string; folder: string; title: string; description: string; items: { id: string; label: string }[] };
export type Milestone = { date: string; title: string; timeWIB?: string; notes?: string; calendarUrl?: string };
export type InboxItem = { id: string; text: string; createdAt: string; status: "NEW" | "TRIAGED" };
export type AppState = { tasks: Record<string, { status?: "DONE"; snoozedUntil?: string; replacedAt?: string }>; bricks: Record<string, boolean>; requirements?: Record<string, Record<string, RequirementProgress>>; scholarshipDrafts?: Record<string, import("./scholarship-drafts").ScholarshipDraft>; localScholarships?: Record<string, Route>; updatedAt?: string };
export type SourceNote = { id: string; routeId?: string; checkedAt: string; cycle: string; title: string; summary: string; sourceUrl: string; secondaryUrl?: string; deadlineAt?: string; deadlineDate?: string; deadlineLabel?: string; verifiedField: string };
export type WatchEvent = { id: string; at: string; url: string; kind: "BASELINE" | "CHANGED" | "ERROR"; summary: string; excerpt: string; routeIds: string[] };
export type WatchState = { lastRunAt: string | null; runStartedAt?: string; running?: boolean; runComplete?: boolean; scope?: string; progress?: { checked: number; total: number }; summary?: { checked: number; ok: number; errors: number }; sources: Record<string, { status: string; hash?: string; lastCheckedAt?: string; lastSuccessAt?: string; error?: string; routeIds?: string[] }>; events: WatchEvent[] };
export type Dashboard = { mode: "PRIVATE" | "DEMO"; profile: Profile; routes: Route[]; calendarEvents: CalendarEvent[]; overlays: Overlay[]; evaluations: Evaluation[]; briefing: { cards: Task[]; remaining: number; completed: number; taskTitles: Record<string,string> }; bricks: Brick[]; state: AppState; milestones: Milestone[]; inbox: InboxItem[]; sourceNotes: SourceNote[]; watch: WatchState; schedule: { active: boolean; label: string; nextRunAt?: string } };

export function label(value: string) { return value.toLowerCase().replaceAll("_", " ").replace(/^\w/, c => c.toUpperCase()); }
export function safeUrl(value: string) { try { const u = new URL(value); return ["https:", "http:"].includes(u.protocol) && !u.username && !u.password ? value : undefined; } catch { return undefined; } }
export function gapText(e: Evaluation) { return e.budget.gapRange ? `${e.budget.gapRange[0]}${e.budget.gapRange[0] === e.budget.gapRange[1] ? "" : `–${e.budget.gapRange[1]}`}M / mo` : "Unestimated"; }
