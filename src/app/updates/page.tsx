import Workspace from "@/components/workspace";
import { loadDashboard } from "@/lib/storage";
export const dynamic = "force-dynamic";
export const metadata = { title: "Source updates" };
export default async function Page() { return <Workspace view="watchtower" initial={await loadDashboard()} />; }
