import Workspace from "@/components/workspace";
import { loadDashboard } from "@/lib/storage";
export const dynamic = "force-dynamic";
export const metadata = { title: "Calendar" };
export default async function Page({ searchParams }: { searchParams: Promise<{ route?: string }> }) {
  const [query, data] = await Promise.all([searchParams, loadDashboard()]);
  return <Workspace view="calendar" calendarRouteId={typeof query.route === "string" ? query.route : undefined} initial={data} />;
}
