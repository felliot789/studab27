import Workspace from "@/components/workspace";
import { loadDashboard } from "@/lib/storage";
export const dynamic = "force-dynamic";
export default async function Page() { return <Workspace view="briefing" initial={await loadDashboard()} />; }
