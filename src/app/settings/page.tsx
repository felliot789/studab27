import Workspace from "@/components/workspace";
import { loadDashboard } from "@/lib/storage";
import { projectDashboard } from "@/lib/dashboard-view";
export const dynamic = "force-dynamic";
export const metadata = { title: "Settings" };
export default async function Page() { return <Workspace view="settings" initial={projectDashboard(await loadDashboard(), "settings")} />; }
