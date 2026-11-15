import Workspace from "@/components/workspace";
import { loadDashboard } from "@/lib/storage";
import { projectDashboard } from "@/lib/dashboard-view";
export const dynamic = "force-dynamic";
export const metadata = { title: "Scholarship catalogue" };
export default async function Page() { return <Workspace view="catalogue" initial={projectDashboard(await loadDashboard(), "catalogue")} />; }
