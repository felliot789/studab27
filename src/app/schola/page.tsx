import Workspace from "@/components/workspace";
import { loadDashboard } from "@/lib/storage";

export const dynamic = "force-dynamic";
export const metadata = { title: "Schola" };
export default async function Page() { return <Workspace view="schola" initial={await loadDashboard()} />; }
