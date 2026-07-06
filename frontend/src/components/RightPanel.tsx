import React, { useState } from "react";
import { Check, CircleDot, FileText, Loader2, Wrench } from "lucide-react";
import StringData from "../StringData";
import { PipelineStep, SourceItem } from "../types";

type PanelTab = "sources" | "pipeline";

interface RightPanelProps {
  pipelineSteps?: PipelineStep[];
  sources?: SourceItem[];
  toolsUsed?: string[];
  isThinking?: boolean;
}

const TabButton: React.FC<{
  label: string;
  active: boolean;
  onClick: () => void;
}> = ({ label, active, onClick }) => (
  <button
    onClick={onClick}
    className={`relative flex-1 py-2.5 text-center text-[11px] font-medium transition-colors duration-200 ${
      active ? "text-accent" : "text-txt-mut hover:text-txt-sec"
    }`}
  >
    {label}
    {active && (
      <span className="absolute inset-x-4 -bottom-px h-[2px] rounded-full bg-gradient-to-r from-[#22D3EE] to-[#3B82F6] shadow-glow-soft" />
    )}
  </button>
);

const SourcesPanel: React.FC<{ sources: SourceItem[]; toolsUsed: string[] }> = ({
  sources,
  toolsUsed,
}) => (
  <div className="flex flex-col overflow-hidden flex-1">
    <div className="flex items-center justify-between border-b border-line px-3.5 py-3">
      <span className="text-[11px] font-medium text-txt-sec">
        {StringData.rightPanel.sourcesHeader}
      </span>
      <span className="rounded-full border border-accent/20 bg-accent/[0.07] px-2 py-0.5 text-[10px] font-medium text-accent">
        {StringData.rightPanel.chunkCountBadge.replace("{count}", String(sources.length))}
      </span>
    </div>

    <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-3">
      {toolsUsed.length > 0 && (
        <div>
          <p className="ml-label mb-1.5">Tools used</p>
          <div className="flex flex-wrap gap-1.5">
            {toolsUsed.map((tool) => (
              <span
                key={tool}
                className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-card px-2 py-1 text-[10px] font-medium text-accent"
              >
                <Wrench size={9} className="text-success" />
                {tool}
              </span>
            ))}
          </div>
        </div>
      )}

      {sources.length > 0 ? (
        <div className="flex flex-col gap-2">
          {sources.map((s) => (
            <div
              key={`${s.index}-${s.fileName}`}
              className="w-full rounded-xl border border-line bg-card/60 p-2.5 text-left transition-all duration-200 hover:border-accent/25 hover:bg-card-hover"
            >
              <div className="flex items-center gap-2">
                <span className="flex-shrink-0 rounded-md border border-accent/25 bg-accent/[0.07] px-1.5 py-0.5 text-[10px] font-semibold text-accent">
                  [{s.index}]
                </span>
                <FileText size={11} className="flex-shrink-0 text-txt-mut" />
                <span className="break-all text-[11px] font-medium text-txt-sec">
                  {s.fileName}
                </span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        toolsUsed.length === 0 && (
          <p className="px-3 py-8 text-center text-[11px] leading-relaxed text-txt-mut">
            Ask a question to see the sources and tools that produced the answer.
          </p>
        )
      )}
    </div>
  </div>
);

const StepCard: React.FC<{ step: PipelineStep; isLast: boolean }> = ({ step, isLast }) => {
  const done = step.status === "done";
  const active = step.status === "active";

  return (
    <div className="relative pl-8">
      {!isLast && (
        <span
          className={`absolute left-[11px] top-6 h-[calc(100%-8px)] w-px ${
            done
              ? "bg-gradient-to-b from-success/60 to-success/10"
              : active
              ? "bg-gradient-to-b from-accent/60 to-transparent"
              : "bg-line"
          }`}
        />
      )}

      <span
        className={`absolute left-0 top-1.5 flex h-[23px] w-[23px] items-center justify-center rounded-full border transition-all duration-300 ${
          done
            ? "border-success/40 bg-success/10 text-[#4ADE80]"
            : active
            ? "border-accent/50 bg-accent/10 text-accent shadow-glow-cyan"
            : "border-line bg-card text-txt-mut/60"
        }`}
      >
        {done ? (
          <Check size={11} strokeWidth={3} />
        ) : active ? (
          <Loader2 size={11} className="animate-spin" />
        ) : (
          <CircleDot size={9} />
        )}
      </span>

      <div
        className={`mb-2 rounded-xl border px-3 py-2 transition-all duration-300 ${
          active
            ? "border-accent/30 bg-accent/[0.05]"
            : done
            ? "border-line bg-card/50"
            : "border-line/60 bg-transparent"
        }`}
      >
        <p
          className={`text-[11px] font-medium ${
            active ? "text-txt-pri" : done ? "text-txt-sec" : "text-txt-mut/70"
          }`}
        >
          {step.label}
        </p>
        {active && (
          <p className="mt-0.5 flex items-center gap-1 text-[9.5px] text-accent/80">
            <span className="h-1 w-1 animate-pulse-soft rounded-full bg-accent" />
            processing…
          </p>
        )}
      </div>
    </div>
  );
};

const PipelinePanel: React.FC<{ steps: PipelineStep[]; isThinking?: boolean }> = ({
  steps,
  isThinking,
}) => (
  <div className="flex-1 overflow-y-auto p-3">
    <div className="mb-3 flex items-center justify-between">
      <p className="ml-label">{StringData.pipeline.lastQueryLabel}</p>
      {isThinking && (
        <span className="flex items-center gap-1.5 rounded-full border border-accent/25 bg-accent/[0.07] px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-accent">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
          live
        </span>
      )}
    </div>

    {steps.length === 0 ? (
      <p className="py-8 text-center text-[11px] leading-relaxed text-txt-mut">
        The retrieval pipeline will appear here, step by step, as you ask a question.
      </p>
    ) : (
      <div>
        {steps.map((step, i) => (
          <StepCard key={step.id} step={step} isLast={i === steps.length - 1} />
        ))}
      </div>
    )}

    <div className="mt-4 rounded-xl border border-line bg-card/40 p-3">
      <p className="ml-label mb-2.5">{StringData.rightPanel.pipelineConfigHeader}</p>
      {(Object.entries(StringData.pipeline.configKeys) as [string, string][]).map(
        ([key, label]) => (
          <div key={key} className="mb-1.5 flex justify-between text-[11px] last:mb-0">
            <span className="text-txt-mut">{label}</span>
            <span className="font-medium text-txt-sec">
              {
                StringData.pipeline.configValues[
                  key as keyof typeof StringData.pipeline.configValues
                ]
              }
            </span>
          </div>
        ),
      )}
    </div>
  </div>
);

const RightPanel: React.FC<RightPanelProps> = ({
  pipelineSteps = [],
  sources = [],
  toolsUsed = [],
  isThinking = false,
}) => {
  const [activeTab, setActiveTab] = useState<PanelTab>("pipeline");

  return (
    <div className="flex w-[272px] min-w-[272px] flex-col overflow-hidden border-l border-line bg-surface/80 backdrop-blur-xl">
      <div className="flex border-b border-line">
        {(
          [
            ["pipeline", StringData.rightPanel.tabPipeline],
            ["sources", StringData.rightPanel.tabSources],
          ] as [PanelTab, string][]
        ).map(([tab, label]) => (
          <TabButton
            key={tab}
            label={label}
            active={activeTab === tab}
            onClick={() => setActiveTab(tab)}
          />
        ))}
      </div>

      {activeTab === "sources" && (
        <SourcesPanel sources={sources} toolsUsed={toolsUsed} />
      )}
      {activeTab === "pipeline" && (
        <PipelinePanel steps={pipelineSteps} isThinking={isThinking} />
      )}
    </div>
  );
};

export default RightPanel;
