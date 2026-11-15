import Workspace from "@/components/workspace";
import { loadDashboard } from "@/lib/storage";
import { projectDashboard } from "@/lib/dashboard-view";
export const dynamic = "force-dynamic";
export const metadata = { title: "Scholarship tracker" };
export default async function Page({ searchParams }: { searchParams: Promise<{ browse?: string }> }) {
  const { browse } = await searchParams;
  const view = browse === "1" ? "catalogue" : "tracker";
  return <Workspace view={view} initial={projectDashboard(await loadDashboard(), view)} />;
}
