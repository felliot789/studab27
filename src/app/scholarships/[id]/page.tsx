import { notFound } from "next/navigation";
import Workspace from "@/components/workspace";
import { loadDashboard } from "@/lib/storage";
import { projectDashboard } from "@/lib/dashboard-view";
export const dynamic = "force-dynamic";
export const metadata = { title: "Scholarship details" };
export default async function Page({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ tab?: string }> }) {
  const [{ id }, query, data] = await Promise.all([params, searchParams, loadDashboard()]);
  if (!data.routes.some(r => r.id === id)) notFound();
  return <Workspace view="detail" routeId={id} initialTab={query.tab} initial={projectDashboard(data, "detail", id)} />;
}
