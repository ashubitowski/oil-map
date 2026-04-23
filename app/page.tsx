import MapWrapper from "@/components/MapWrapper";
import SiteHeader from "@/components/SiteHeader";

export default function Home() {
  return (
    <main className="w-full h-screen bg-gray-950 flex flex-col">
      <SiteHeader />
      <div className="flex-1 relative min-h-0">
        <MapWrapper />
      </div>
      {/* Server-rendered text for search crawlers — not visible to users */}
      <div className="sr-only" aria-hidden="true">
        <h1>US Oil Map — Interactive Oil &amp; Gas Well Map</h1>
        <p>
          Explore 4.4 million oil, gas, and water well locations across all 50 US states and
          federal offshore waters. Data is sourced from state regulatory agencies (Texas RRC,
          COGCC, PADEP, ODNR, and more) and the Bureau of Ocean Energy Management (BOEM).
        </p>
        <h2>Features</h2>
        <ul>
          <li>4.4 million wells colored by depth — shallow cyan to deep indigo</li>
          <li>3D depth columns: toggle cinematic extrusion by true vertical depth</li>
          <li>Shale play polygons: Permian Basin, Marcellus, Haynesville, Bakken, Eagle Ford, and 45 more</li>
          <li>Oil production timeline: 36-month EIA production data with basin-level bubbles</li>
          <li>Filter by well status: Active, Plugged &amp; Abandoned, Inactive, Unknown</li>
          <li>Filter by well type: Oil, Gas, Injection, Disposal, Water/Monitoring</li>
          <li>Shareable URLs encoding viewport, layers, and selected features</li>
          <li>Offshore Gulf of Mexico wells from BOEM with water depth</li>
        </ul>
        <h2>Data Sources</h2>
        <p>
          Well location data is collected from public regulatory sources including the Texas
          Railroad Commission, Colorado Oil &amp; Gas Conservation Commission, Pennsylvania DEP,
          Ohio DNR, West Virginia DEP, Montana BOGC, Utah DNR, and many more. Depth data for
          Pennsylvania Marcellus and Utica shale wells is sourced from FracFocus.
        </p>
        <h2>Major Basins Covered</h2>
        <p>
          Permian Basin (TX/NM), Marcellus Shale (PA/WV/OH), Haynesville Shale (LA/TX),
          Bakken Formation (ND/MT), Eagle Ford Shale (TX), Niobrara/DJ Basin (CO/WY),
          Anadarko Basin (OK/TX), Appalachian Basin, Uinta Basin (UT), Powder River Basin (WY).
        </p>
      </div>
    </main>
  );
}
