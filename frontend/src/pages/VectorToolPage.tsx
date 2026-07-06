import React, { useState } from "react";
import { Boxes, Gauge, HardDriveIcon, Network, Search, Timer } from "lucide-react";
import Sidebar, { Document } from "../components/Sidebar";
import RightPanel from "../components/RightPanel";
import TopBar from "../components/TopBar";
import StringData from "../StringData";

const DOCS: Document[] = [
  { id: "1", name: "LangChain_Docs.pdf",    meta: "2.4 MB · 847 chunks", type: "pdf", status: "ready" },
  { id: "2", name: "RAG_Architecture.docx", meta: "1.1 MB · 312 chunks", type: "doc", status: "ready" },
  { id: "3", name: "pgvector_guide.txt",    meta: "Indexing... 68%",      type: "txt", status: "indexing" },
];

const CLUSTERS = [
  { cx: "25%", cy: "30%", color: "#22D3EE", label: "LangChain cluster",    dots: 8 },
  { cx: "55%", cy: "55%", color: "#8B5CF6", label: "Architecture cluster", dots: 6 },
  { cx: "72%", cy: "25%", color: "#22C55E", label: "pgvector cluster",     dots: 7 },
  { cx: "40%", cy: "65%", color: "#F59E0B", label: "Query vector",         dots: 1 },
];

const StatCard: React.FC<{
  icon: React.ReactNode;
  label: string;
  value: string;
  tint: string;
}> = ({ icon, label, value, tint }) => (
  <div className="ml-card ml-card-hover flex items-center gap-3 px-4 py-3.5">
    <span className={`flex h-9 w-9 items-center justify-center rounded-xl ${tint}`}>
      {icon}
    </span>
    <div className="min-w-0">
      <p className="truncate text-[15px] font-semibold tracking-tight text-txt-pri">{value}</p>
      <p className="text-[10.5px] font-medium text-txt-mut">{label}</p>
    </div>
  </div>
);

const VectorToolPage: React.FC = () => {
  const [query, setQuery]          = useState("");
  const [topK, setTopK]            = useState(5);
  const [activeDocId, setActive]   = useState<string | null>("1");

  return (
    <div className="flex h-screen overflow-hidden bg-ink font-sans text-txt-pri">
      <Sidebar
        documents={DOCS}
        activeDocId={activeDocId}
        evalScores={{ faithfulness: null, relevance: null }}
        onDocSelect={setActive}
        onUploadClick={() => {}}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <TopBar
          title={StringData.vectorTool.pageTitle}
          subtitle={StringData.vectorTool.pageTitleSuffix}
          modelName={StringData.vectorTool.dbBadge}
        />

        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4 sm:p-5">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <StatCard
              icon={<Boxes size={16} />}
              tint="bg-accent/10 text-accent"
              value={StringData.vectorTool.statsValues.totalVectors}
              label={StringData.vectorTool.statsKeys.totalVectors}
            />
            <StatCard
              icon={<Gauge size={16} />}
              tint="bg-violet/10 text-[#A78BFA]"
              value={StringData.vectorTool.statsValues.indexSize}
              label={StringData.vectorTool.statsKeys.indexSize}
            />
            <StatCard
              icon={<Timer size={16} />}
              tint="bg-success/10 text-[#4ADE80]"
              value={StringData.vectorTool.statsValues.avgQueryTime}
              label={StringData.vectorTool.statsKeys.avgQueryTime}
            />
          </div>

          <div>
            <p className="ml-label mb-2 inline-flex items-center gap-1.5">
              <Search size={11} className="text-accent" />
              {StringData.vectorTool.searchLabel}
            </p>
            <div className="flex flex-col gap-2 sm:flex-row">
              <div className="relative flex-1">
                <Search
                  size={14}
                  className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-txt-mut"
                />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={StringData.vectorTool.searchPlaceholder}
                  className="ml-input !py-2 pl-10 text-[12px]"
                />
              </div>
              <div className="flex items-center gap-1.5 rounded-xl border border-line bg-card px-3 py-2 text-[11px] text-txt-sec">
                <span className="text-txt-mut">{StringData.vectorTool.topKLabel}</span>
                <input
                  type="number"
                  value={topK}
                  min={1}
                  max={20}
                  onChange={(e) => setTopK(Number(e.target.value))}
                  className="w-9 bg-transparent text-center font-medium text-txt-pri outline-none"
                />
              </div>
              <button className="btn-primary !py-2 !text-[12px]">
                <Search size={12} />
                {StringData.vectorTool.searchBtn}
              </button>
            </div>
          </div>

          <div>
            <p className="ml-label mb-2 inline-flex items-center gap-1.5">
              <Network size={11} className="text-accent" />
              {StringData.vectorTool.vizLabel}
            </p>
            <div
              className="ml-card relative animate-rise-in overflow-hidden !rounded-card"
              style={{ height: "300px" }}
            >
              <div
                className="pointer-events-none absolute -top-20 left-1/3 h-64 w-64 rounded-full opacity-[0.08] blur-3xl"
                style={{ background: "radial-gradient(circle, #22D3EE 0%, transparent 70%)" }}
              />

              <svg className="absolute inset-0 h-full w-full opacity-[0.07]" xmlns="http://www.w3.org/2000/svg">
                {[...Array(10)].map((_, i) => (
                  <React.Fragment key={i}>
                    <line x1={`${i * 10}%`} y1="0" x2={`${i * 10}%`} y2="100%" stroke="#22D3EE" strokeWidth="1" />
                    <line x1="0" y1={`${i * 10}%`} x2="100%" y2={`${i * 10}%`} stroke="#22D3EE" strokeWidth="1" />
                  </React.Fragment>
                ))}
              </svg>

              {CLUSTERS.map((cl) => (
                <div key={cl.label} className="absolute" style={{ left: cl.cx, top: cl.cy }}>
                  {[...Array(cl.dots)].map((_, i) => (
                    <div
                      key={i}
                      className="absolute rounded-full opacity-50"
                      style={{
                        width: 6, height: 6,
                        backgroundColor: cl.color,
                        boxShadow: `0 0 8px ${cl.color}55`,
                        left: Math.sin(i * (360 / cl.dots) * (Math.PI / 180)) * 24,
                        top:  Math.cos(i * (360 / cl.dots) * (Math.PI / 180)) * 18,
                      }}
                    />
                  ))}
                  <div
                    className="h-3 w-3 rounded-full border-2"
                    style={{
                      backgroundColor: cl.color,
                      borderColor: cl.color,
                      boxShadow: `0 0 14px ${cl.color}88`,
                    }}
                  />
                  <p
                    className="mt-1.5 whitespace-nowrap text-[9.5px] font-medium"
                    style={{ color: cl.color }}
                  >
                    {cl.label}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div>
            <p className="ml-label mb-2 inline-flex items-center gap-1.5">
              <HardDriveIcon size={11} className="text-accent" />
              {StringData.vectorTool.configLabel}
            </p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {(
                [
                  ["indexType", StringData.vectorTool.configKeys.indexType],
                  ["dimensions", StringData.vectorTool.configKeys.dimensions],
                  ["distance", StringData.vectorTool.configKeys.distance],
                  ["m", StringData.vectorTool.configKeys.m],
                  ["efSearch", StringData.vectorTool.configKeys.efSearch],
                ] as [keyof typeof StringData.vectorTool.configValues, string][]
              ).map(([key, label]) => (
                <div key={key} className="ml-card ml-card-hover px-3.5 py-3">
                  <p className="text-[13px] font-semibold tracking-tight text-txt-pri">
                    {StringData.vectorTool.configValues[key]}
                  </p>
                  <p className="mt-0.5 text-[10px] font-medium text-txt-mut">{label}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>

      <RightPanel />
    </div>
  );
};

export default VectorToolPage;
