import Workspace from "@/components/workspace";
import { loadDashboard } from "@/lib/storage";
import { projectDashboard } from "@/lib/dashboard-view";
export const dynamic = "force-dynamic";
export const metadata = { title: "Today's tasks" };
export default async function Page() { return <Workspace view="briefing" initial={projectDashboard(await loadDashboard(), "briefing")} />; }
