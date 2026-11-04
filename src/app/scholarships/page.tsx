import Workspace from "@/components/workspace";
import { loadDashboard } from "@/lib/storage";
export const dynamic = "force-dynamic";
export const metadata = { title: "Scholarship tracker" };
export default async function Page({ searchParams }: { searchParams: Promise<{ browse?: string }> }) {
  const { browse } = await searchParams;
  return <Workspace view={browse === "1" ? "catalogue" : "tracker"} initial={await loadDashboard()} />;
}
