import { HomePitch } from "@/components/home-pitch";
import { loadResearchSnapshot } from "@/lib/research-data";

export const dynamic = "force-dynamic";

export default async function Home() {
  return <HomePitch data={await loadResearchSnapshot()} />;
}
