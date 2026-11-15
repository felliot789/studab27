import Workspace from "@/components/workspace";
import { loadDashboard } from "@/lib/storage";
import { projectDashboard } from "@/lib/dashboard-view";
export const dynamic = "force-dynamic";
export default async function Page() { return <Workspace view="tracker" initial={projectDashboard(await loadDashboard(), "tracker")} />; }
