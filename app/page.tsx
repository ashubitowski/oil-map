import MapWrapper from "@/components/MapWrapper";

export default function Home() {
  return (
    <main className="w-full h-screen bg-gray-950 flex flex-col">
      <header className="flex items-center gap-3 px-4 py-3 border-b border-gray-800 flex-shrink-0">
        <h1 className="text-white font-semibold text-sm tracking-wide">US Oil Map</h1>
        <span className="text-gray-600 text-xs">Wells · Plays · Probability · Production</span>
      </header>
      <div className="flex-1 relative">
        <MapWrapper />
      </div>
    </main>
  );
}
