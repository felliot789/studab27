import Workspace from "@/components/workspace";
import { loadDashboard } from "@/lib/storage";
export const dynamic = "force-dynamic";
export const metadata = { title: "Today's tasks" };
export default async function Page() { return <Workspace view="briefing" initial={await loadDashboard()} />; }
