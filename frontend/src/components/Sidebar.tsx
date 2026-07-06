import React from "react";
import { FileText, FileCode2, FileScan, HeartPulse, Loader2, RefreshCw, Upload } from "lucide-react";
import StringData from "../StringData";
import EvalScorePanel, { EvalScores } from "./EvalScorePanel";

export type DocStatus = "ready" | "indexing";
export type DocType = "pdf" | "doc" | "txt" | "md";

export interface Document {
  id: string;
  name: string;
  meta: string;
  type: DocType;
  status: DocStatus;
}

interface SidebarProps {
  documents: Document[];
  activeDocId: string | null;
  evalScores: EvalScores;
  isThinking?: boolean;
  uploading?: boolean;
  onDocSelect: (id: string) => void;
  onUploadClick: () => void;
  onResetDocs?: () => void;
}

const SHOW_DOCS_RESET =
  (import.meta.env.VITE_SHOW_DOCS_RESET as string | undefined) !== "false";

const iconStyles: Record<DocType, string> = {
  pdf: "bg-danger/10 text-[#F87171]",
  doc: "bg-accent-2/10 text-[#60A5FA]",
  txt: "bg-success/10 text-[#4ADE80]",
  md:  "bg-violet/10 text-[#A78BFA]",
};

const iconGlyph: Record<DocType, React.ReactNode> = {
  pdf: <FileText size={15} />,
  doc: <FileScan size={15} />,
  txt: <FileCode2 size={15} />,
  md:  <FileCode2 size={15} />,
};

const Sidebar: React.FC<SidebarProps> = ({
  documents,
  activeDocId,
  evalScores,
  isThinking = false,
  uploading = false,
  onDocSelect,
  onUploadClick,
  onResetDocs,
}) => {
  return (
    <aside
      className="flex h-full w-[236px] min-w-[236px] flex-col overflow-hidden border-r border-line bg-surface/80 backdrop-blur-xl"
      aria-label={StringData.aria.sidebar}
    >
      <div className="flex items-center gap-2.5 border-b border-line px-4 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-[#22D3EE] to-[#3B82F6] text-[#04121A] shadow-glow-soft">
          <HeartPulse size={16} strokeWidth={2.2} />
        </div>
        <div className="min-w-0">
          <span className="block truncate font-display text-[14.5px] font-semibold tracking-tight text-txt-pri">
            Med
            <span className="bg-gradient-to-r from-[#22D3EE] to-[#3B82F6] bg-clip-text text-transparent">
              {StringData.app.nameHighlight}
            </span>
          </span>
          <span className="block text-[9.5px] font-medium uppercase tracking-[0.14em] text-txt-mut">
            Assistant
          </span>
        </div>
      </div>

      <div className="flex items-center justify-between px-4 pb-2 pt-4">
        <p className="ml-label">{StringData.nav.sectionDocuments}</p>
        {SHOW_DOCS_RESET && onResetDocs && (
          <button
            onClick={onResetDocs}
            title={StringData.nav.resetDocsTooltip}
            aria-label={StringData.aria.resetDocsButton}
            className="group flex h-6 w-6 items-center justify-center rounded-md text-txt-mut transition-colors duration-200 hover:bg-card-hover hover:text-accent"
          >
            <RefreshCw
              size={12}
              className="transition-transform duration-300 group-hover:rotate-180"
            />
          </button>
        )}
      </div>

      <button
        onClick={onUploadClick}
        disabled={uploading}
        aria-label={StringData.aria.uploadButton}
        aria-busy={uploading}
        className="group mx-3 mb-2.5 flex items-center justify-center gap-2 rounded-xl border border-dashed border-accent/25 bg-accent/[0.04] px-3 py-2.5 text-[12px] font-medium text-accent transition-all duration-200 hover:border-accent/50 hover:bg-accent/[0.09] hover:shadow-glow-soft disabled:cursor-not-allowed disabled:opacity-60"
      >
        {uploading ? (
          <>
            <Loader2 size={13} className="animate-spin" />
            {StringData.docStatus.indexingLabel}
          </>
        ) : (
          <>
            <Upload size={13} className="transition-transform duration-200 group-hover:-translate-y-0.5" />
            {StringData.nav.uploadBtn}
          </>
        )}
      </button>

      <div className="min-h-0 flex-1 space-y-1 overflow-y-auto px-2.5 pb-2">
        {documents.map((doc) => {
          const active = activeDocId === doc.id;
          return (
            <button
              key={doc.id}
              onClick={() => onDocSelect(doc.id)}
              className={`group w-full cursor-pointer rounded-xl border px-2.5 py-2.5 text-left transition-all duration-200 ${
                active
                  ? "border-accent/30 bg-accent/[0.07] shadow-glow-soft"
                  : "border-transparent hover:border-line hover:bg-card-hover"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <div
                  className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg ${iconStyles[doc.type]}`}
                >
                  {iconGlyph[doc.type]}
                </div>
                <div className="min-w-0 flex-1">
                  <p className={`truncate text-[12px] font-medium ${active ? "text-txt-pri" : "text-txt-sec"}`}>
                    {doc.name}
                  </p>
                  <p className="mt-0.5 truncate text-[10px] text-txt-mut">{doc.meta}</p>
                </div>
                <span
                  className={`inline-flex flex-shrink-0 items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] font-medium ${
                    doc.status === "ready"
                      ? "bg-success/10 text-[#4ADE80]"
                      : "bg-warning/10 text-[#FBBF24]"
                  }`}
                >
                  <span
                    className={`h-1 w-1 rounded-full ${
                      doc.status === "ready" ? "bg-success" : "animate-pulse-soft bg-warning"
                    }`}
                  />
                  {doc.status === "ready" ? "Ready" : "Indexing"}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      <EvalScorePanel scores={evalScores} isThinking={isThinking} />
    </aside>
  );
};

export default Sidebar;
