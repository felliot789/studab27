import Workspace from "@/components/workspace";
import { loadDashboard } from "@/lib/storage";
export const dynamic = "force-dynamic";
export const metadata = { title: "Applications" };
export default async function Page() { return <Workspace view="applications" initial={await loadDashboard()} />; }
