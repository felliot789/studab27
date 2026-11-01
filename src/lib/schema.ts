export type GateStatus = "PASS" | "FAIL" | "UNKNOWN";
export type ApplicationStatus = "NOT_STARTED" | "RESEARCHING" | "IN_PROGRESS" | "SUBMITTED" | "DEFER_TO_MAIN_ROUND" | "DROP";
export const APPLICATION_STATUSES: ApplicationStatus[] = ["NOT_STARTED", "RESEARCHING", "IN_PROGRESS", "SUBMITTED", "DEFER_TO_MAIN_ROUND", "DROP"];
export type Route = {
  id: string; country: string; institution: string; scholarshipName: string;
  fundingType: string; engineeringFit: string; benefitsCoverage: string; satRole: string;
  suggestedSatBenchmark: string; languageOrTestNotes: string; deadlineWindow2027: string;
  preGradApplyAllowed: string; separateScholarshipApp: string; renewalAndBondTerms: string;
  publicRiskOrCaveat: string; officialSourceUrl: string; secondarySourceUrl: string;
  seedStatus: string;
};
export type CostEstimate = { tuition: number; housing: number; food: number; insurance: number; other: number; coverage: number; upfront?: number };
export type Overlay = {
  routeId: string; personalStrategyTier: string; estimatedFamilyGapIdrMPerMonth: string;
  personalSatTargetNote: string; personalRiskNote: string; applicationStatus: ApplicationStatus;
  driveApplicationFolder?: string; costEstimate?: CostEstimate; notes?: string;
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
export type AppState = { tasks: Record<string, { status?: "DONE"; snoozedUntil?: string; replacedAt?: string }>; bricks: Record<string, boolean>; updatedAt?: string };
export type SourceNote = { id: string; routeId?: string; checkedAt: string; cycle: string; title: string; summary: string; sourceUrl: string; secondaryUrl?: string; deadlineAt?: string; deadlineDate?: string; deadlineLabel?: string; verifiedField: string };
export type WatchEvent = { id: string; at: string; url: string; kind: "BASELINE" | "CHANGED" | "ERROR"; summary: string; excerpt: string; routeIds: string[] };
export type WatchState = { lastRunAt: string | null; runStartedAt?: string; running?: boolean; runComplete?: boolean; scope?: string; progress?: { checked: number; total: number }; summary?: { checked: number; ok: number; errors: number }; sources: Record<string, { status: string; hash?: string; lastCheckedAt?: string; lastSuccessAt?: string; error?: string; routeIds?: string[] }>; events: WatchEvent[] };
export type Dashboard = { mode: "PRIVATE" | "DEMO"; profile: Profile; routes: Route[]; overlays: Overlay[]; evaluations: Evaluation[]; briefing: { cards: Task[]; remaining: number; completed: number; taskTitles: Record<string,string> }; bricks: Brick[]; state: AppState; milestones: Milestone[]; inbox: InboxItem[]; sourceNotes: SourceNote[]; watch: WatchState; schedule: { active: boolean; label: string; nextRunAt?: string } };

export function label(value: string) { return value.toLowerCase().replaceAll("_", " ").replace(/^\w/, c => c.toUpperCase()); }
export function safeUrl(value: string) { try { const u = new URL(value); return ["https:", "http:"].includes(u.protocol) && !u.username && !u.password ? value : undefined; } catch { return undefined; } }
export function gapText(e: Evaluation) { return e.budget.gapRange ? `${e.budget.gapRange[0]}${e.budget.gapRange[0] === e.budget.gapRange[1] ? "" : `–${e.budget.gapRange[1]}`}M / mo` : "Unestimated"; }
