import Workspace from "@/components/workspace";
import { loadDashboard } from "@/lib/storage";
export const dynamic = "force-dynamic";
export default async function Page() { return <Workspace view="tracker" initial={await loadDashboard()} />; }
