
export interface PipelineStep {
  id: string;
  label: string;
  status: "idle" | "active" | "done";
}

export interface SourceItem {
  index: number;
  fileName: string;
}

export interface TableAttachment {
  index: number;
  source?: string | null;
  markdown: string;
  summary?: string | null;
}

export interface ImageAttachment {
  index: number;
  source?: string | null;
  url: string;
  caption?: string | null;
}

export interface QueryMeta {
  question: string;
  answer: string;
  tools_used?: string[] | null;
  sources_used?: string | null;
  tables?: TableAttachment[] | null;
  images?: ImageAttachment[] | null;
}

export function parseSources(raw?: string | null): SourceItem[] {
  if (!raw) return [];
  const items: SourceItem[] = [];
  for (const line of raw.split("\n")) {
    const m = line.match(/^\s*\[(\d+)\]\s*(.+?)\s*$/);
    if (m) items.push({ index: Number(m[1]), fileName: m[2] });
  }
  return items;
}
