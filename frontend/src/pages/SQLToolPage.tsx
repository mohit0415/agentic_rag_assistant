import React, { useState } from "react";
import { Database, Gauge, Layers, Play, Table2 } from "lucide-react";
import Sidebar, { Document } from "../components/Sidebar";
import RightPanel from "../components/RightPanel";
import TopBar from "../components/TopBar";
import StringData from "../StringData";

const DOCS: Document[] = [
  { id: "1", name: "LangChain_Docs.pdf",    meta: "2.4 MB · 847 chunks", type: "pdf", status: "ready" },
  { id: "2", name: "RAG_Architecture.docx", meta: "1.1 MB · 312 chunks", type: "doc", status: "ready" },
  { id: "3", name: "pgvector_guide.txt",    meta: "Indexing... 68%",      type: "txt", status: "indexing" },
];

const MOCK_RESULTS = [
  { doc_id: "langchain_docs",   chunk: "234", similarity: "0.94", page: "14", preview: "Naive RAG retrieves top-k docs..." },
  { doc_id: "rag_architecture", chunk: "48",  similarity: "0.91", page: "3",  preview: "Cross-encoder re-rankers score..."  },
  { doc_id: "langchain_docs",   chunk: "301", similarity: "0.88", page: "22", preview: "HyDE generates a hypothetical..."   },
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

const SQLToolPage: React.FC = () => {
  const [query, setQuery]         = useState(StringData.sqlTool.defaultQuery);
  const [results, setResults]     = useState<typeof MOCK_RESULTS>([]);
  const [ran, setRan]             = useState(false);
  const [activeDocId, setActive]  = useState<string | null>("1");

  const handleRun = () => {
    setResults(MOCK_RESULTS);
    setRan(true);
  };

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
          title={StringData.sqlTool.pageTitle}
          subtitle={StringData.sqlTool.pageTitleSuffix}
          modelName={StringData.sqlTool.dbBadge}
        />

        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4 sm:p-5">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <StatCard
              icon={<Database size={16} />}
              tint="bg-accent/10 text-accent"
              value="1,159"
              label="Indexed chunks"
            />
            <StatCard
              icon={<Layers size={16} />}
              tint="bg-violet/10 text-[#A78BFA]"
              value="3 tables"
              label="document_chunks · documents · queries"
            />
            <StatCard
              icon={<Gauge size={16} />}
              tint="bg-success/10 text-[#4ADE80]"
              value="4.2 ms"
              label="Avg query latency"
            />
          </div>

          <div className="ml-card animate-rise-in overflow-hidden !rounded-card">
            <div className="flex items-center justify-between border-b border-line bg-surface/70 px-4 py-2.5">
              <span className="ml-label inline-flex items-center gap-1.5">
                <Database size={11} className="text-accent" />
                SQL Editor
              </span>
              <button onClick={handleRun} className="btn-primary !px-3.5 !py-1.5 !text-[11px]">
                <Play size={11} fill="currentColor" />
                {StringData.sqlTool.runBtn.replace("▶", "").trim()}
              </button>
            </div>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              spellCheck={false}
              className="w-full resize-none bg-ink/40 p-4 font-mono text-[12px] leading-relaxed text-[#C9D4E3] caret-accent outline-none placeholder:text-txt-mut"
              style={{ minHeight: "180px" }}
            />
          </div>

          <div>
            <p className="ml-label mb-2 inline-flex items-center gap-1.5">
              <Table2 size={11} className="text-accent" />
              {StringData.sqlTool.resultsLabel}
            </p>
            {!ran ? (
              <div className="ml-card flex items-center justify-center py-10">
                <p className="text-[12px] text-txt-mut">{StringData.sqlTool.noResults}</p>
              </div>
            ) : (
              <div className="ml-card animate-rise-in overflow-hidden !rounded-card !p-0">
                <div className="max-h-[340px] overflow-y-auto">
                  <div
                    className="sticky top-0 z-10 grid border-b border-line bg-surface px-4 py-2.5"
                    style={{ gridTemplateColumns: "repeat(5, 1fr)" }}
                  >
                    {StringData.sqlTool.tableHeaders.map((h: string) => (
                      <span
                        key={h}
                        className="text-[9.5px] font-semibold uppercase tracking-[0.12em] text-accent"
                      >
                        {h}
                      </span>
                    ))}
                  </div>
                  {results.map((row, i) => (
                    <div
                      key={i}
                      className="grid border-b border-line/50 px-4 py-2.5 text-[11.5px] transition-colors last:border-b-0 even:bg-white/[0.02] hover:bg-accent/[0.04]"
                      style={{ gridTemplateColumns: "repeat(5, 1fr)" }}
                    >
                      <span className="font-mono text-txt-mut">{row.doc_id}</span>
                      <span className="text-txt-sec">{row.chunk}</span>
                      <span className="inline-flex">
                        <span className="rounded-md bg-success/10 px-1.5 py-0.5 font-mono text-[10.5px] font-medium text-[#4ADE80]">
                          {row.similarity}
                        </span>
                      </span>
                      <span className="text-txt-sec">{row.page}</span>
                      <span className="truncate text-txt-mut">{row.preview}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      <RightPanel />
    </div>
  );
};

export default SQLToolPage;
