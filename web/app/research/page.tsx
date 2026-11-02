import { ResearchDashboard } from "@/components/research-dashboard";
import { loadResearchSnapshot } from "@/lib/research-data";
export const dynamic = "force-dynamic";
export default async function Research() { return <ResearchDashboard initialData={await loadResearchSnapshot()}/>; }
