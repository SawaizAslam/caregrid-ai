import { useEffect, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AlertTriangle, MapPinned, Search as SearchIcon } from "lucide-react";

import AppHeader from "@/components/AppHeader";
import SearchPage from "@/pages/SearchPage";
import MapPage from "@/pages/MapPage";
import AuditPage from "@/pages/AuditPage";

const VALID = ["search", "map", "audit"] as const;
type TabKey = (typeof VALID)[number];

function readHash(): TabKey {
  const h = window.location.hash.replace(/^#/, "") as TabKey;
  return (VALID as readonly string[]).includes(h) ? h : "search";
}

const Index = () => {
  const [tab, setTab] = useState<TabKey>(() =>
    typeof window !== "undefined" ? readHash() : "search",
  );

  useEffect(() => {
    const onHash = () => setTab(readHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  function handleChange(v: string) {
    if ((VALID as readonly string[]).includes(v)) {
      setTab(v as TabKey);
      window.location.hash = v;
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <AppHeader />
      <main className="mx-auto max-w-7xl px-4 sm:px-6 py-6">
        <Tabs value={tab} onValueChange={handleChange} className="space-y-6">
          <TabsList className="w-full sm:w-auto grid grid-cols-3 sm:inline-grid sm:grid-cols-3">
            <TabsTrigger value="search" className="gap-1.5">
              <SearchIcon className="h-4 w-4" />
              <span>Search</span>
            </TabsTrigger>
            <TabsTrigger value="map" className="gap-1.5">
              <MapPinned className="h-4 w-4" />
              <span className="hidden xs:inline sm:inline">Crisis Map</span>
              <span className="xs:hidden sm:hidden">Map</span>
            </TabsTrigger>
            <TabsTrigger value="audit" className="gap-1.5">
              <AlertTriangle className="h-4 w-4" />
              <span>Audit</span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="search" className="mt-0">
            <SearchPage />
          </TabsContent>
          <TabsContent value="map" className="mt-0">
            <MapPage />
          </TabsContent>
          <TabsContent value="audit" className="mt-0">
            <AuditPage />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
};

export default Index;
