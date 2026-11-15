import Workspace from "@/components/workspace";
import { loadDashboard } from "@/lib/storage";
import { projectDashboard } from "@/lib/dashboard-view";
export const dynamic = "force-dynamic";
export const metadata = { title: "Source updates" };
export default async function Page() { return <Workspace view="watchtower" initial={projectDashboard(await loadDashboard(), "watchtower")} />; }
