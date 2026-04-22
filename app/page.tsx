import MapWrapper from "@/components/MapWrapper";
import SiteHeader from "@/components/SiteHeader";

export default function Home() {
  return (
    <main className="w-full h-screen bg-gray-950 flex flex-col">
      <SiteHeader />
      <div className="flex-1 relative min-h-0">
        <MapWrapper />
      </div>
    </main>
  );
}
