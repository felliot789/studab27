import Workspace from "@/components/workspace";
import { loadDashboard } from "@/lib/storage";
export const dynamic = "force-dynamic";
export const metadata = { title: "Document readiness" };
export default async function Page() { return <Workspace view="bricks" initial={await loadDashboard()} />; }
